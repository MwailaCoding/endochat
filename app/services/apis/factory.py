"""Factory for creating and managing API clients."""

from typing import Dict, List, Any, Optional
import asyncio

from app.config import Settings
from app.services.cache.cache_service import CacheService
from app.services.apis.base import BaseAPIClient
from app.services.apis.who import WHOAPIClient
from app.services.apis.pubmed import PubMedAPIClient
from app.services.apis.openfda import OpenFDAClient
from app.services.apis.drugbank import DrugBankClient
from app.services.apis.tavily import TavilyAPIClient
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class APIClientFactory:
    """Factory for creating and managing API clients."""

    def __init__(self, cache_service: CacheService, settings: Settings):
        self.cache = cache_service
        self.settings = settings
        self._clients: Dict[str, BaseAPIClient] = {}

    def get_client(self, name: str) -> Optional[BaseAPIClient]:
        """Get or create an API client by name."""
        if name not in self._clients:
            self._clients[name] = self._create_client(name)
        return self._clients.get(name)

    def _create_client(self, name: str) -> Optional[BaseAPIClient]:
        """Create a new API client."""
        timeout = self.settings.api_timeout
        max_retries = self.settings.api_max_retries

        if name == "who":
            return WHOAPIClient(
                self.cache,
                timeout=timeout,
                max_retries=max_retries,
            )

        elif name == "pubmed":
            return PubMedAPIClient(
                self.cache,
                api_key=self.settings.pubmed_api_key,
                email=self.settings.pubmed_email,
                timeout=timeout,
                max_retries=max_retries,
            )

        elif name == "openfda":
            return OpenFDAClient(
                self.cache,
                api_key=self.settings.openfda_api_key,
                timeout=timeout,
                max_retries=max_retries,
            )

        elif name == "drugbank":
            return DrugBankClient(
                self.cache,
                api_key=self.settings.drugbank_api_key,
                timeout=timeout,
                max_retries=max_retries,
            )

        elif name == "web" and self.settings.is_web_search_available:
            return TavilyAPIClient(
                self.cache,
                api_key=self.settings.web_search_api_key,
                timeout=timeout,
                max_retries=max_retries,
            )

        else:
            logger.warning("unknown_api_client", name=name)
            return None

    async def search_all(
        self,
        query: str,
        apis: Optional[List[str]] = None,
        max_results_per_api: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search all APIs in parallel (including web search when enabled)."""
        if apis is None:
            apis = ["who", "pubmed", "openfda", "drugbank"]
            if self.settings.is_web_search_available:
                apis = apis + ["web"]

        tasks = {}
        for api_name in apis:
            client = self.get_client(api_name)
            if client:
                max_results = (
                    self.settings.web_search_max_results
                    if api_name == "web"
                    else max_results_per_api
                )
                tasks[api_name] = client.search_with_cache(
                    query, max_results=max_results
                )

        if not tasks:
            return {}

        # Execute all searches in parallel
        results_list = await asyncio.gather(
            *tasks.values(),
            return_exceptions=True,
        )

        # Map results back to API names
        results = {}
        for api_name, result in zip(tasks.keys(), results_list):
            if isinstance(result, Exception):
                logger.warning(
                    "api_search_exception",
                    api=api_name,
                    error=str(result),
                )
                results[api_name] = []
            else:
                results[api_name] = result
                logger.info(
                    "api_search_completed",
                    api=api_name,
                    results_count=len(result),
                )

        return results

    async def search_single(
        self,
        api_name: str,
        query: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search a single API."""
        client = self.get_client(api_name)
        if not client:
            logger.warning("api_client_not_found", api=api_name)
            return []

        return await client.search_with_cache(query, max_results=max_results)

    async def close(self) -> None:
        """Close all API clients."""
        for name, client in self._clients.items():
            try:
                await client.close()
                logger.debug("api_client_closed", api=name)
            except Exception as e:
                logger.warning("api_client_close_error", api=name, error=str(e))

        self._clients.clear()

    def get_available_apis(self) -> List[str]:
        """Get list of available API names."""
        apis = ["who", "pubmed", "openfda", "drugbank"]
        if self.settings.is_web_search_available:
            apis = apis + ["web"]
        return apis

    def get_api_status(self) -> Dict[str, bool]:
        """Get status of each API (whether configured)."""
        return {
            "who": True,  # Always available (no key required)
            "pubmed": True,  # Works without key (with limits)
            "openfda": True,  # Works without key (with limits)
            "drugbank": bool(self.settings.drugbank_api_key),
            "web": self.settings.is_web_search_available,
        }
