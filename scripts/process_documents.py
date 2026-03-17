"""CLI to process PDF documents into the vector database."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from tqdm import tqdm

from app.config import settings
from app.services.database.postgres import DatabasePool
from app.services.document_processor import DocumentProcessor, DocumentProcessingError
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessResult:
    path: str
    status: str
    details: Dict[str, Any]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process PDF documents for EndoChat.")
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Root folder to scan for PDFs (defaults to DOCUMENTS_PATH).",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Process a single PDF file.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all PDFs under --path (or DOCUMENTS_PATH).",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Reprocess documents even if already processed (by clearing processed flag).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="How many documents to process concurrently.",
    )
    return parser.parse_args()


async def _clear_processed_flag(db: DatabasePool, file_path: str) -> None:
    query = """
        UPDATE documents
        SET processed = FALSE,
            metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{stage}', to_jsonb('queued'::text), TRUE),
            updated_at = NOW()
        WHERE file_path = $1
    """
    await db.execute(query, file_path)


async def _process_one(
    processor: DocumentProcessor,
    db: DatabasePool,
    file_path: str,
    *,
    reprocess: bool,
) -> ProcessResult:
    try:
        if reprocess:
            await _clear_processed_flag(db, file_path)

        details = await processor.process_document(file_path)
        return ProcessResult(path=file_path, status=details.get("status", "unknown"), details=details)
    except DocumentProcessingError as e:
        logger.warning("document_processing_error", file=file_path, error=str(e))
        return ProcessResult(path=file_path, status="failed", details={"error": str(e)})
    except Exception as e:
        logger.error("document_processing_failed", file=file_path, error=str(e))
        return ProcessResult(path=file_path, status="failed", details={"error": str(e)})


async def main_async() -> int:
    args = _parse_args()

    if not args.file and not args.all:
        raise SystemExit("You must provide either --file or --all (with optional --path).")

    docs_root = args.path or getattr(settings, "documents_path", None) or "./data/documents"

    # Setup DB + OpenAI
    db = DatabasePool(settings.database_url, settings.db_pool_min_size, settings.db_pool_max_size)
    await db.connect()

    if not settings.is_openai_available:
        await db.close()
        raise SystemExit("OPENAI_API_KEY not configured or OPENAI_ENABLED=false.")

    openai = AsyncOpenAI(api_key=settings.openai_api_key)
    embedding_model = getattr(settings, "openai_embedding_model", None) or "text-embedding-ada-002"
    processor = DocumentProcessor(openai, db, embedding_model=embedding_model)

    try:
        files: List[str] = []
        if args.file:
            files = [str(Path(args.file))]
        else:
            root = Path(docs_root)
            if not root.exists():
                raise SystemExit(f"Documents path not found: {root}")
            files = [str(p) for p in sorted(root.rglob("*.pdf"))]

        if not files:
            logger.info("no_documents_found", path=str(docs_root))
            return 0

        sem = asyncio.Semaphore(max(1, int(args.concurrency)))
        results: List[ProcessResult] = []

        async def run(file_path: str) -> None:
            async with sem:
                res = await _process_one(processor, db, file_path, reprocess=bool(args.reprocess))
                results.append(res)

        with tqdm(total=len(files), desc="Processing PDFs", unit="doc") as bar:
            tasks = []
            for f in files:
                tasks.append(asyncio.create_task(run(f)))
                tasks[-1].add_done_callback(lambda _t: bar.update(1))
            await asyncio.gather(*tasks)

        processed = sum(1 for r in results if r.status in ("processed", "partial"))
        skipped = sum(1 for r in results if r.status == "skipped")
        failed = sum(1 for r in results if r.status == "failed")

        logger.info(
            "document_processing_summary",
            processed=processed,
            skipped=skipped,
            failed=failed,
            total=len(results),
        )

        # Emit a human-friendly summary to stdout
        print("\nSummary:")
        print(f"  processed: {processed}")
        print(f"  skipped:   {skipped}")
        print(f"  failed:    {failed}")

        if failed:
            print("\nFailures:")
            for r in results:
                if r.status == "failed":
                    print(f"  - {r.path}: {r.details.get('error')}")

        return 0 if failed == 0 else 2

    finally:
        await db.close()


def main() -> None:
    exit_code = asyncio.run(main_async())
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

