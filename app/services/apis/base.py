"""Base API client with retry logic and error handling."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import asyncio

import httpx

from app.services.cache.cache_service import CacheService
from app.services.utils.logging import get_logger
from app.core.exceptions import APIClientError

logger = get_logger(__name__)


class BaseAPIClient(ABC):
    """Base class for all external API clients."""

    name: str = "base"
    base_url: str = ""
    cache_ttl: int = 86400  # 24 hours default

    def __init__(
        self,
        cache_service: CacheService,
        timeout: int = 10,
        max_retries: int = 3,
    ):
        self.cache = cache_service
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search the API for relevant information."""
        pass

    @abstractmethod
    def parse_response(self, response: Any) -> List[Dict[str, Any]]:
        """Parse API response into standardized format."""
        pass

    async def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        method: str = "GET",
    ) -> Any:
        """Make HTTP request with retry logic."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    "api_request",
                    api=self.name,
                    url=url,
                    attempt=attempt + 1,
                )

                if method.upper() == "GET":
                    response = await self.client.get(
                        url, params=params, headers=headers
                    )
                else:
                    response = await self.client.post(
                        url, params=params, headers=headers
                    )

                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    return response.json()
                elif "xml" in content_type:
                    return response.text
                else:
                    return response.text

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "api_http_error",
                    api=self.name,
                    status=e.response.status_code,
                    attempt=attempt + 1,
                )
                if e.response.status_code in (429, 503):
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise APIClientError(
                        f"HTTP {e.response.status_code} from {self.name}",
                        api_name=self.name,
                        status_code=e.response.status_code,
                    )

            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    "api_request_error",
                    api=self.name,
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

            except Exception as e:
                last_error = e
                logger.error(
                    "api_unexpected_error",
                    api=self.name,
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        raise APIClientError(
            f"Failed to fetch from {self.name} after {self.max_retries} attempts: {last_error}",
            api_name=self.name,
        )

    async def search_with_cache(
        self,
        query: str,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Search with caching support."""
        cached = await self.cache.get_api_response(self.name, query)
        if cached:
            logger.info("api_cache_hit", api=self.name, query=query[:50])
            return cached

        try:
            results = await self.search(query, **kwargs)
            if results:
                await self.cache.set_api_response(
                    self.name, query, results, self.cache_ttl
                )
            return results
        except APIClientError:
            raise
        except Exception as e:
            logger.error("api_search_failed", api=self.name, error=str(e))
            return []

    def _standardize_result(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        publication_date: Optional[str] = None,
        **extra,
    ) -> Dict[str, Any]:
        """Create standardized result format."""
        return {
            "source": self.name,
            "title": title,
            "content": content,
            "url": url,
            "publication_date": publication_date,
            **extra,
        }
