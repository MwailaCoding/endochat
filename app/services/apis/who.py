"""WHO Global Health Observatory API client."""

from typing import Dict, Any, List

from app.services.apis.base import BaseAPIClient
from app.services.cache.cache_service import CacheService
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class WHOAPIClient(BaseAPIClient):
    """Client for WHO Global Health Observatory API."""

    name = "who"
    base_url = "https://ghoapi.azureedge.net/api"
    cache_ttl = 86400  # 24 hours

    ENDOMETRIOSIS_KEYWORDS = [
        "endometriosis",
        "reproductive health",
        "women's health",
        "gynecological",
        "pelvic pain",
        "menstrual",
        "fertility",
    ]

    def __init__(self, cache_service: CacheService, **kwargs):
        super().__init__(cache_service, **kwargs)

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search WHO for relevant health information."""
        results = []

        # Search indicators related to women's health and endometriosis
        indicators = await self._search_indicators(query)
        results.extend(indicators)

        # Also fetch relevant fact sheet content via dimension data
        dimension_data = await self._search_dimensions(query)
        results.extend(dimension_data)

        return results

    async def _search_indicators(self, query: str) -> List[Dict[str, Any]]:
        """Search WHO indicators."""
        try:
            url = f"{self.base_url}/Indicator"

            # Build OData filter for relevant indicators
            keywords = self._get_relevant_keywords(query)
            filter_parts = []
            for kw in keywords[:3]:
                filter_parts.append(f"contains(tolower(IndicatorName), '{kw.lower()}')")

            params = {}
            if filter_parts:
                params["$filter"] = " or ".join(filter_parts)

            response = await self._make_request(url, params)
            return self.parse_response(response)

        except Exception as e:
            logger.warning("who_indicator_search_failed", error=str(e))
            return []

    async def _search_dimensions(self, query: str) -> List[Dict[str, Any]]:
        """Search WHO dimension values for relevant data."""
        try:
            url = f"{self.base_url}/DIMENSION/COUNTRY/DimensionValues"
            response = await self._make_request(url)

            # Filter for relevant data
            return self._filter_dimension_data(response, query)

        except Exception as e:
            logger.warning("who_dimension_search_failed", error=str(e))
            return []

    def parse_response(self, response: Any) -> List[Dict[str, Any]]:
        """Parse WHO API response into standard format."""
        results = []

        if not isinstance(response, dict):
            return results

        items = response.get("value", [])
        for item in items[:10]:
            indicator_name = item.get("IndicatorName", "")
            indicator_code = item.get("IndicatorCode", "")

            if not indicator_name:
                continue

            results.append(
                self._standardize_result(
                    title=indicator_name,
                    content=item.get("IndicatorDefinition", indicator_name),
                    url=f"https://www.who.int/data/gho/data/indicators/indicator-details/GHO/{indicator_code}",
                    publication_date=item.get("DateModified"),
                    indicator_code=indicator_code,
                    organization="World Health Organization",
                )
            )

        return results

    def _filter_dimension_data(
        self, response: Any, query: str
    ) -> List[Dict[str, Any]]:
        """Filter dimension data for relevant results."""
        results = []

        if not isinstance(response, dict):
            return results

        items = response.get("value", [])
        query_lower = query.lower()

        for item in items:
            title = item.get("Title", "")
            if any(kw in title.lower() for kw in self.ENDOMETRIOSIS_KEYWORDS):
                results.append(
                    self._standardize_result(
                        title=title,
                        content=item.get("Value", title),
                        url="https://www.who.int/data/gho",
                        organization="World Health Organization",
                    )
                )

        return results[:5]

    def _get_relevant_keywords(self, query: str) -> List[str]:
        """Extract relevant keywords from query."""
        query_words = query.lower().split()
        keywords = []

        for word in query_words:
            if len(word) > 3:
                keywords.append(word)

        # Always include endometriosis-related terms
        keywords.extend(["reproductive", "women", "health"])
        return list(set(keywords))[:5]

    async def get_fact_sheet(self, topic: str = "endometriosis") -> Dict[str, Any]:
        """Get WHO fact sheet content for a topic."""
        try:
            # WHO fact sheets are typically available via their web content
            url = f"{self.base_url}/Indicator"
            params = {
                "$filter": f"contains(tolower(IndicatorName), '{topic.lower()}')",
                "$top": 5,
            }

            response = await self._make_request(url, params)
            parsed = self.parse_response(response)

            if parsed:
                return {
                    "found": True,
                    "results": parsed,
                    "source": "WHO Global Health Observatory",
                }

            return {
                "found": False,
                "results": [],
                "source": "WHO Global Health Observatory",
            }

        except Exception as e:
            logger.error("who_fact_sheet_failed", topic=topic, error=str(e))
            return {"found": False, "error": str(e)}
