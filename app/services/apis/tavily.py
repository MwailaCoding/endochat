"""Tavily web search API client for live internet search."""

from typing import Dict, Any, List, Optional

from app.services.apis.base import BaseAPIClient
from app.services.cache.cache_service import CacheService
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class TavilyAPIClient(BaseAPIClient):
    """Client for Tavily Search API (web search for chat context)."""

    name = "web"
    base_url = "https://api.tavily.com"
    cache_ttl = 3600  # 1 hour for web results

    def __init__(
        self,
        cache_service: CacheService,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(cache_service, **kwargs)
        self.api_key = api_key or ""

    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Search the web via Tavily. Query is scoped to endometriosis."""
        if not self.api_key:
            logger.debug("tavily_skipped", reason="no_api_key")
            return []

        # Scope query to endometriosis for on-topic results
        scoped_query = f"endometriosis {query}" if "endometriosis" not in query.lower() else query

        try:
            url = f"{self.base_url}/search"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            body = {
                "query": scoped_query,
                "search_depth": "basic",
                "max_results": min(max_results, 20),
                "topic": "general",
            }

            response = await self.client.post(url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
            return self.parse_response(data)
        except Exception as e:
            logger.warning("tavily_search_failed", error=str(e))
            return []

    def parse_response(self, response: Any) -> List[Dict[str, Any]]:
        """Parse Tavily response into standardized source format."""
        if not isinstance(response, dict):
            return []

        results = response.get("results") or []
        out = []
        for r in results:
            title = r.get("title") or ""
            content = r.get("content") or ""
            url = r.get("url")
            if not title and not content:
                continue
            out.append(
                self._standardize_result(
                    title=title or "(Web result)",
                    content=content[:600] if content else "",
                    url=url,
                )
            )
        return out
