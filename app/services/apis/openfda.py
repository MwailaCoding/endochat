"""OpenFDA API client for drug information."""

from typing import Dict, Any, List, Optional

from app.services.apis.base import BaseAPIClient
from app.services.cache.cache_service import CacheService
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class OpenFDAClient(BaseAPIClient):
    """Client for OpenFDA Drug API."""

    name = "openfda"
    base_url = "https://api.fda.gov/drug"
    cache_ttl = 604800  # 7 days

    # Common endometriosis treatments to search for
    ENDO_TREATMENTS = [
        "dienogest",
        "leuprolide",
        "goserelin",
        "nafarelin",
        "danazol",
        "norethindrone",
        "medroxyprogesterone",
        "elagolix",
    ]

    def __init__(
        self,
        cache_service: CacheService,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(cache_service, **kwargs)
        self.api_key = api_key

    def _get_params(self, additional: Dict = None) -> Dict[str, Any]:
        """Get request parameters including API key if available."""
        params = additional or {}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Search OpenFDA for drug information."""
        results = []

        # Search drug labels
        label_results = await self._search_labels(query, max_results)
        results.extend(label_results)

        # If query mentions treatment, also search for known endo treatments
        if any(term in query.lower() for term in ["treatment", "medication", "drug"]):
            treatment_results = await self._search_endo_treatments(max_results)
            results.extend(treatment_results)

        # Deduplicate
        seen = set()
        unique_results = []
        for r in results:
            key = r.get("title", "").lower()
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        return unique_results[:max_results]

    async def _search_labels(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search drug labels for endometriosis-related information."""
        try:
            url = f"{self.base_url}/label.json"

            # Search for endometriosis in indications
            search_query = f'indications_and_usage:"endometriosis" AND ({query})'

            params = self._get_params({
                "search": search_query,
                "limit": max_results,
            })

            response = await self._make_request(url, params)
            return self.parse_response(response)

        except Exception as e:
            logger.warning("openfda_label_search_failed", error=str(e))
            return []

    async def _search_endo_treatments(
        self,
        max_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """Search for known endometriosis treatments."""
        results = []

        for treatment in self.ENDO_TREATMENTS[:max_results]:
            try:
                drug_info = await self._get_drug_info(treatment)
                if drug_info:
                    results.append(drug_info)
            except Exception:
                continue

        return results

    async def _get_drug_info(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """Get information for a specific drug."""
        try:
            url = f"{self.base_url}/label.json"
            params = self._get_params({
                "search": f'openfda.generic_name:"{drug_name}"',
                "limit": 1,
            })

            response = await self._make_request(url, params)
            parsed = self.parse_response(response)
            return parsed[0] if parsed else None

        except Exception as e:
            logger.debug("openfda_drug_lookup_failed", drug=drug_name, error=str(e))
            return None

    def parse_response(self, response: Any) -> List[Dict[str, Any]]:
        """Parse OpenFDA response into standard format."""
        results = []

        if not isinstance(response, dict):
            return results

        items = response.get("results", [])
        for item in items:
            parsed = self._parse_drug_label(item)
            if parsed:
                results.append(parsed)

        return results

    def _parse_drug_label(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a drug label into standard format."""
        try:
            openfda = item.get("openfda", {})

            # Get drug name
            brand_names = openfda.get("brand_name", [])
            generic_names = openfda.get("generic_name", [])

            drug_name = (
                brand_names[0] if brand_names
                else generic_names[0] if generic_names
                else "Unknown Drug"
            )

            # Get indications (focus on endometriosis)
            indications = item.get("indications_and_usage", [])
            indication_text = " ".join(indications)[:500] if indications else ""

            # Get warnings
            warnings = item.get("warnings", [])
            warnings_text = warnings[0][:300] if warnings else ""

            # Get adverse reactions
            adverse = item.get("adverse_reactions", [])
            adverse_text = adverse[0][:300] if adverse else ""

            # Build content
            content_parts = []
            if indication_text:
                content_parts.append(f"Indications: {indication_text}")
            if warnings_text:
                content_parts.append(f"Warnings: {warnings_text}")
            if adverse_text:
                content_parts.append(f"Side Effects: {adverse_text}")

            content = " | ".join(content_parts) if content_parts else drug_name

            # Get application number for URL
            app_number = openfda.get("application_number", [""])[0]
            url = f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={drug_name.replace(' ', '+')}"

            return self._standardize_result(
                title=drug_name,
                content=content[:1000],
                url=url,
                generic_name=generic_names[0] if generic_names else None,
                brand_names=brand_names[:3],
                indications=indications[:2],
                warnings=warnings[:2],
                organization="FDA/OpenFDA",
            )

        except Exception as e:
            logger.warning("openfda_parse_error", error=str(e))
            return None

    async def search_adverse_events(
        self,
        drug_name: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for adverse event reports."""
        try:
            url = f"{self.base_url}/event.json"
            params = self._get_params({
                "search": f'patient.drug.medicinalproduct:"{drug_name}"',
                "limit": limit,
            })

            response = await self._make_request(url, params)
            return response.get("results", []) if isinstance(response, dict) else []

        except Exception as e:
            logger.warning("openfda_adverse_search_failed", error=str(e))
            return []
