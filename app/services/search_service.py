"""Hybrid search over external health APIs and curated document chunks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openai import AsyncOpenAI

from app.services.apis.factory import APIClientFactory
from app.services.database.postgres import DatabasePool
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class HybridSearchConfig:
    max_api_results_per_api: int = 5
    max_doc_results: int = 8
    dedupe_max_results: int = 20


class HybridSearchService:
    """Search both APIs and document chunks concurrently."""

    def __init__(
        self,
        *,
        api_factory: APIClientFactory,
        db_pool: DatabasePool,
        openai_client: Optional[AsyncOpenAI],
        embedding_model: str = "text-embedding-ada-002",
        config: Optional[HybridSearchConfig] = None,
    ):
        self.apis = api_factory
        self.db = db_pool
        self.openai = openai_client
        self.embedding_model = embedding_model
        self.config = config or HybridSearchConfig()

    async def search_all(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search APIs and documents in parallel.

        Returns a dict keyed by source group name (API name or 'document').
        Each result is a dict with at minimum: title, content, source.
        """
        api_task = asyncio.create_task(self.search_apis(query))
        doc_task = asyncio.create_task(self.search_documents(query))

        api_results, doc_results = await asyncio.gather(api_task, doc_task)
        combined: Dict[str, List[Dict[str, Any]]] = dict(api_results)
        combined["document"] = doc_results
        return combined

    async def search_apis(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """Search external APIs via APIClientFactory."""
        try:
            return await self.apis.search_all(
                query,
                max_results_per_api=self.config.max_api_results_per_api,
            )
        except Exception as e:
            logger.error("hybrid_api_search_failed", error=str(e))
            return {}

    async def search_documents(self, query: str) -> List[Dict[str, Any]]:
        """Vector-search ingested PDF chunks using pgvector cosine distance."""
        if not self.openai:
            logger.info("document_search_unavailable", reason="no_openai_client")
            return []

        try:
            embedding = await self._embed_query(query)
            vector_literal = self._to_vector_literal(embedding)

            sql = """
                SELECT
                    dc.content,
                    dc.page_number,
                    dc.section_title,
                    dc.chunk_index,
                    d.id AS document_id,
                    d.filename,
                    d.title AS document_title,
                    d.source_type,
                    d.source_organization,
                    d.publication_date,
                    (1 - (dc.embedding <=> $1::vector)) AS score
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE d.processed = TRUE
                ORDER BY dc.embedding <=> $1::vector
                LIMIT $2
            """

            rows = await self.db.fetch(sql, vector_literal, self.config.max_doc_results)

            results: List[Dict[str, Any]] = []
            for r in rows:
                pub = r.get("publication_date")
                publication_date: Optional[str] = None
                if isinstance(pub, (date, datetime)):
                    publication_date = pub.date().isoformat() if isinstance(pub, datetime) else pub.isoformat()
                elif pub:
                    publication_date = str(pub)

                title = r.get("document_title") or r.get("filename") or "Medical document"
                content = (r.get("content") or "").strip()
                if not content:
                    continue

                results.append(
                    {
                        "source": "document",
                        "title": title,
                        "content": content,
                        "url": None,
                        "publication_date": publication_date,
                        "confidence": float(r.get("score") or 0.0),
                        "document": {
                            "document_id": str(r.get("document_id")),
                            "filename": r.get("filename"),
                            "source_type": r.get("source_type"),
                            "source_organization": r.get("source_organization"),
                        },
                        "page_number": r.get("page_number"),
                        "section_title": r.get("section_title"),
                        "chunk_index": r.get("chunk_index"),
                        "score": float(r.get("score") or 0.0),
                    }
                )

            return results

        except Exception as e:
            logger.error("document_search_failed", error=str(e))
            return []

    async def _embed_query(self, query: str) -> Sequence[float]:
        resp = await self.openai.embeddings.create(model=self.embedding_model, input=query)
        return resp.data[0].embedding

    def _to_vector_literal(self, embedding: Sequence[float]) -> str:
        # pgvector accepts a literal like: '[0.1, 0.2, ...]'.
        return "[" + ",".join(f"{float(x):.8f}" for x in embedding) + "]"

    def rank_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank results by confidence/score (descending)."""
        def key(r: Dict[str, Any]) -> Tuple[int, float]:
            # Prefer authoritative sources. Documents should be high priority.
            src = (r.get("source") or "").lower()
            priority = {
                "document": 0,
                "pubmed": 1,
                "who": 2,
                "openfda": 3,
                "drugbank": 4,
                "medlineplus": 5,
                "web": 6,
            }.get(src, 99)
            score = float(r.get("confidence") or r.get("score") or 0.0)
            return (priority, -score)

        return sorted(results, key=key)

    def dedupe_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate results by normalized title + snippet overlap."""
        seen: set[Tuple[str, str]] = set()
        out: List[Dict[str, Any]] = []
        for r in results:
            title = (r.get("title") or "").strip().lower()
            content = (r.get("content") or "").strip()
            snippet = content[:200].strip().lower()
            key = (title, snippet)
            if not title or not snippet:
                continue
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
            if len(out) >= self.config.dedupe_max_results:
                break
        return out

