"""PDF document processing for ingestion into pgvector-backed search."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Tuple

import filetype
import pdfplumber
from PyPDF2 import PdfReader
import tiktoken
from openai import AsyncOpenAI

from app.services.database.postgres import DatabasePool
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentProcessingError(Exception):
    """Raised when a document cannot be processed."""


@dataclass(frozen=True)
class ExtractedPage:
    """Represents extracted text from one PDF page."""

    page_number: int
    text: str


@dataclass(frozen=True)
class TextChunk:
    """A chunk of text with associated metadata."""

    chunk_index: int
    content: str
    page_number: Optional[int]
    section_title: Optional[str]
    metadata: Dict[str, Any]


class DocumentProcessor:
    """Process PDF documents into chunks + embeddings stored in Postgres/pgvector."""

    def __init__(
        self,
        openai_client: AsyncOpenAI,
        db_pool: DatabasePool,
        embedding_model: str = "text-embedding-ada-002",
        *,
        encoding_name: str = "cl100k_base",
        chunk_tokens: int = 500,
        overlap_tokens: int = 50,
        embed_concurrency: int = 8,
    ):
        self.openai = openai_client
        self.db = db_pool
        self.embedding_model = embedding_model
        self._encoding = tiktoken.get_encoding(encoding_name)
        self.chunk_tokens = chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.embed_concurrency = max(1, embed_concurrency)

    async def extract_text_from_pdf(self, file_path: str) -> List[ExtractedPage]:
        """
        Extract text from a PDF with page numbers.

        Tries `pdfplumber` first (better layout), falls back to `PyPDF2`.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(str(path))

        self._validate_pdf(path)

        # Prefer pdfplumber; it reads pages lazily from file.
        try:
            pages: List[ExtractedPage] = []
            with pdfplumber.open(str(path)) as pdf:
                for idx, page in enumerate(pdf.pages, start=1):
                    text = (page.extract_text() or "").strip()
                    if text:
                        pages.append(ExtractedPage(page_number=idx, text=text))
            return pages
        except Exception as e:
            logger.warning("pdfplumber_extract_failed", file=str(path), error=str(e))

        # Fallback to PyPDF2
        try:
            pages = []
            reader = PdfReader(str(path))
            for idx, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append(ExtractedPage(page_number=idx, text=text))
            return pages
        except Exception as e:
            raise DocumentProcessingError(f"Failed to extract text from PDF: {e}") from e

    def chunk_text(
        self,
        pages: Sequence[ExtractedPage],
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ) -> List[TextChunk]:
        """
        Split extracted pages into overlapping token chunks.

        - Uses `tiktoken` for token counting.
        - Associates each chunk with the first page number it appears on (best-effort).
        """
        chunk_tokens = chunk_size if chunk_size is not None else self.chunk_tokens
        overlap_tokens = overlap if overlap is not None else self.overlap_tokens
        overlap_tokens = min(overlap_tokens, max(0, chunk_tokens - 1))

        # Flatten into a token stream while retaining an approximate page mapping.
        token_stream: List[int] = []
        token_page_map: List[int] = []  # page number per token

        for p in pages:
            if not p.text:
                continue
            tokens = self._encoding.encode(p.text)
            token_stream.extend(tokens)
            token_page_map.extend([p.page_number] * len(tokens))

            # Add a separator between pages (helps reduce accidental joins)
            sep = self._encoding.encode("\n\n")
            token_stream.extend(sep)
            token_page_map.extend([p.page_number] * len(sep))

        if not token_stream:
            return []

        chunks: List[TextChunk] = []
        start = 0
        chunk_index = 0

        while start < len(token_stream):
            end = min(len(token_stream), start + chunk_tokens)
            chunk_tokens_slice = token_stream[start:end]
            content = self._encoding.decode(chunk_tokens_slice).strip()

            # Determine best-effort page number: first non-separator token mapping
            page_number: Optional[int] = None
            if start < len(token_page_map):
                page_number = token_page_map[start]

            section_title = self._infer_section_title(content)
            metadata: Dict[str, Any] = {
                "token_start": start,
                "token_end": end,
                "token_count": len(chunk_tokens_slice),
            }

            if content:
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_index,
                        content=content,
                        page_number=page_number,
                        section_title=section_title,
                        metadata=metadata,
                    )
                )
                chunk_index += 1

            if end >= len(token_stream):
                break
            start = max(0, end - overlap_tokens)

        return chunks

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate an OpenAI embedding for text."""
        if not text.strip():
            raise ValueError("Cannot embed empty text")

        resp = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return list(resp.data[0].embedding)

    async def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Main processing pipeline for a single document.

        Steps:
        - validate + hash
        - create/upsert document record
        - extract text per page
        - chunk
        - embed + store chunks (resumable)
        - mark processed
        """
        path = Path(file_path)
        self._validate_pdf(path)

        file_hash = await self._hash_file(path)
        filename = path.name
        source_type = self._infer_source_type(path)
        title, source_org, pub_date = self._infer_metadata_from_path(path)

        doc_row = await self._upsert_document(
            filename=filename,
            title=title,
            source_type=source_type,
            source_organization=source_org,
            publication_date=pub_date,
            file_hash=file_hash,
            file_path=str(path),
        )
        document_id = str(doc_row["id"])
        already_processed = bool(doc_row.get("processed"))

        if already_processed:
            return {
                "status": "skipped",
                "reason": "already_processed",
                "document_id": document_id,
                "file_hash": file_hash,
                "filename": filename,
            }

        # Resume point
        resume_from = await self._get_resume_chunk_index(doc_row)
        logger.info(
            "document_processing_started",
            document_id=document_id,
            filename=filename,
            file_hash=file_hash,
            resume_from_chunk=resume_from,
        )

        pages = await self.extract_text_from_pdf(str(path))
        total_pages = self._infer_total_pages(pages)
        await self._update_document_progress(
            document_id=document_id,
            total_pages=total_pages,
            processed=False,
            metadata_updates={"stage": "extracted", "total_pages": total_pages},
        )

        chunks = self.chunk_text(pages)
        if not chunks:
            await self._update_document_progress(
                document_id=document_id,
                processed=True,
                metadata_updates={"stage": "done", "note": "no_text_extracted"},
            )
            return {
                "status": "processed",
                "document_id": document_id,
                "filename": filename,
                "file_hash": file_hash,
                "total_pages": total_pages,
                "chunks_total": 0,
                "chunks_inserted": 0,
            }

        chunks_to_process = [c for c in chunks if c.chunk_index >= resume_from]

        # Embed with bounded concurrency; commit per chunk to enable resume.
        sem = asyncio.Semaphore(self.embed_concurrency)
        inserted = 0
        failed = 0

        async def embed_and_store(chunk: TextChunk) -> Tuple[int, bool, Optional[str]]:
            async with sem:
                try:
                    embedding = await self.generate_embedding(chunk.content)
                    await self._insert_chunk(
                        document_id=document_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        embedding=embedding,
                        page_number=chunk.page_number,
                        section_title=chunk.section_title,
                        metadata=chunk.metadata,
                    )
                    await self._set_resume_chunk_index(
                        document_id=document_id, last_chunk_index=chunk.chunk_index
                    )
                    return chunk.chunk_index, True, None
                except Exception as e:
                    return chunk.chunk_index, False, str(e)

        results = await asyncio.gather(
            *(embed_and_store(c) for c in chunks_to_process),
            return_exceptions=False,
        )

        for chunk_index, ok, err in results:
            if ok:
                inserted += 1
            else:
                failed += 1
                logger.warning(
                    "document_chunk_failed",
                    document_id=document_id,
                    chunk_index=chunk_index,
                    error=err,
                )

        processed_ok = failed == 0
        await self._update_document_progress(
            document_id=document_id,
            processed=processed_ok,
            metadata_updates={
                "stage": "done" if processed_ok else "partial",
                "chunks_total": len(chunks),
                "chunks_inserted": await self._count_chunks(document_id),
                "chunks_failed": failed,
            },
        )

        return {
            "status": "processed" if processed_ok else "partial",
            "document_id": document_id,
            "filename": filename,
            "file_hash": file_hash,
            "total_pages": total_pages,
            "chunks_total": len(chunks),
            "chunks_inserted": inserted,
            "chunks_failed": failed,
            "resumed_from_chunk": resume_from,
        }

    async def iter_pdf_files(self, root: str) -> AsyncIterator[str]:
        """Yield PDF file paths recursively under root."""
        base = Path(root)
        for p in sorted(base.rglob("*.pdf")):
            yield str(p)

    # -----------------------------
    # Internal helpers
    # -----------------------------

    def _validate_pdf(self, path: Path) -> None:
        """Validate that a path is a PDF file."""
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(str(path))

        kind = filetype.guess(str(path))
        if not kind or kind.extension.lower() != "pdf":
            raise DocumentProcessingError(f"Not a valid PDF: {path}")

    async def _hash_file(self, path: Path, chunk_size: int = 1024 * 1024) -> str:
        """Compute SHA-256 hash without loading full file into memory."""
        h = hashlib.sha256()

        def _read() -> str:
            with path.open("rb") as f:
                while True:
                    b = f.read(chunk_size)
                    if not b:
                        break
                    h.update(b)
            return h.hexdigest()

        return await asyncio.to_thread(_read)

    def _infer_source_type(self, path: Path) -> str:
        parts = {p.lower() for p in path.parts}
        if "medical_guidelines" in parts:
            return "medical_guideline"
        if "patient_resources" in parts:
            return "patient_resource"
        if "research" in parts:
            return "research"
        if "official_sources" in parts:
            return "official"
        return "official"

    def _infer_metadata_from_path(self, path: Path) -> Tuple[Optional[str], Optional[str], Optional[date]]:
        """Best-effort metadata extraction from filename/path."""
        name = path.stem.replace("_", " ").strip()
        title = " ".join([w for w in name.split() if w]).strip() or None

        org: Optional[str] = None
        lower = path.name.lower()
        if "eshre" in lower:
            org = "ESHRE"
        elif lower.startswith("who") or "who" in lower:
            org = "WHO"
        elif "ucsf" in lower:
            org = "UCSF"

        pub: Optional[date] = None
        # Simple year parse from filename (e.g., 2022, 2025)
        for token in path.stem.replace("_", " ").split():
            if token.isdigit() and len(token) == 4:
                year = int(token)
                if 1900 <= year <= 2100:
                    pub = date(year, 1, 1)
                    break

        return title, org, pub

    def _infer_total_pages(self, pages: Sequence[ExtractedPage]) -> Optional[int]:
        if not pages:
            return None
        return max(p.page_number for p in pages)

    def _infer_section_title(self, text: str) -> Optional[str]:
        """Heuristic to infer a section title from chunk text."""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return None
        first = lines[0]
        if 4 <= len(first) <= 120 and (first.isupper() or first.istitle()):
            return first[:120]
        return None

    async def _upsert_document(
        self,
        *,
        filename: str,
        title: Optional[str],
        source_type: str,
        source_organization: Optional[str],
        publication_date: Optional[date],
        file_hash: str,
        file_path: str,
    ) -> Dict[str, Any]:
        query = """
            INSERT INTO documents (
                filename, title, source_type, source_organization, publication_date,
                file_hash, file_path, processed, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, '{}'::jsonb)
            ON CONFLICT (file_hash) DO UPDATE SET
                filename = EXCLUDED.filename,
                title = COALESCE(EXCLUDED.title, documents.title),
                source_type = COALESCE(EXCLUDED.source_type, documents.source_type),
                source_organization = COALESCE(EXCLUDED.source_organization, documents.source_organization),
                publication_date = COALESCE(EXCLUDED.publication_date, documents.publication_date),
                file_path = EXCLUDED.file_path,
                updated_at = NOW()
            RETURNING *
        """
        rec = await self.db.fetchrow(
            query,
            filename,
            title,
            source_type,
            source_organization,
            publication_date,
            file_hash,
            file_path,
        )
        return dict(rec) if rec else {}

    async def _get_resume_chunk_index(self, doc_row: Dict[str, Any]) -> int:
        metadata = doc_row.get("metadata") or {}
        try:
            last = int(metadata.get("last_chunk_index", -1))
            return max(0, last + 1)
        except Exception:
            return 0

    async def _set_resume_chunk_index(self, *, document_id: str, last_chunk_index: int) -> None:
        query = """
            UPDATE documents
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{last_chunk_index}',
                to_jsonb($2::int),
                TRUE
            ),
            updated_at = NOW()
            WHERE id = $1
        """
        await self.db.execute(query, document_id, last_chunk_index)

    async def _update_document_progress(
        self,
        *,
        document_id: str,
        total_pages: Optional[int] = None,
        processed: Optional[bool] = None,
        metadata_updates: Optional[Dict[str, Any]] = None,
    ) -> None:
        sets = []
        args: List[Any] = [document_id]
        arg_i = 2

        if total_pages is not None:
            sets.append(f"total_pages = ${arg_i}")
            args.append(total_pages)
            arg_i += 1
        if processed is not None:
            sets.append(f"processed = ${arg_i}")
            args.append(processed)
            arg_i += 1

        # Merge metadata keys individually via jsonb_set chain
        metadata_expr = "COALESCE(metadata, '{}'::jsonb)"
        if metadata_updates:
            for k, v in metadata_updates.items():
                sets.append(
                    f"metadata = jsonb_set({metadata_expr}, '{{{k}}}', to_jsonb(${arg_i}::text), TRUE)"
                )
                # Store as text to keep simple/portable (can be enhanced later)
                args.append(str(v))
                metadata_expr = "metadata"  # subsequent sets apply to updated metadata
                arg_i += 1

        sets.append("updated_at = NOW()")

        query = f"UPDATE documents SET {', '.join(sets)} WHERE id = $1"
        await self.db.execute(query, *args)

    async def _insert_chunk(
        self,
        *,
        document_id: str,
        chunk_index: int,
        content: str,
        embedding: Sequence[float],
        page_number: Optional[int],
        section_title: Optional[str],
        metadata: Dict[str, Any],
    ) -> None:
        # asyncpg can pass python lists into vector if pgvector is installed; otherwise this will fail fast.
        query = """
            INSERT INTO document_chunks (
                document_id, chunk_index, content, embedding, page_number, section_title, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                page_number = EXCLUDED.page_number,
                section_title = EXCLUDED.section_title,
                metadata = EXCLUDED.metadata
        """
        import json

        await self.db.execute(
            query,
            document_id,
            chunk_index,
            content,
            list(embedding),
            page_number,
            section_title,
            json.dumps(metadata),
        )

    async def _count_chunks(self, document_id: str) -> int:
        query = "SELECT COUNT(*) FROM document_chunks WHERE document_id = $1"
        return int(await self.db.fetchval(query, document_id) or 0)

