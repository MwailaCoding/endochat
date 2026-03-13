"""DrugBank API client for drug information."""

from typing import Dict, Any, List, Optional

from app.services.apis.base import BaseAPIClient
from app.services.cache.cache_service import CacheService
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class DrugBankClient(BaseAPIClient):
    """Client for DrugBank API (Academic tier)."""

    name = "drugbank"
    base_url = "https://go.drugbank.com/api/v1"
    cache_ttl = 604800  # 7 days

    # Common endometriosis-related drugs in DrugBank
    ENDO_DRUG_IDS = {
        "dienogest": "DB09123",
        "leuprolide": "DB00007",
        "goserelin": "DB00014",
        "nafarelin": "DB00666",
        "danazol": "DB01406",
        "norethindrone": "DB00717",
        "medroxyprogesterone": "DB00603",
        "elagolix": "DB11979",
        "letrozole": "DB01006",
        "anastrozole": "DB01217",
    }

    def __init__(
        self,
        cache_service: CacheService,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(cache_service, **kwargs)
        self.api_key = api_key
        self._is_available = bool(api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API key."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Search DrugBank for drug information."""
        if not self._is_available:
            logger.debug("drugbank_not_configured")
            return self._get_static_drug_info(query, max_results)

        results = []

        # Try direct drug search
        try:
            search_results = await self._search_drugs(query, max_results)
            results.extend(search_results)
        except Exception as e:
            logger.warning("drugbank_search_failed", error=str(e))
            return self._get_static_drug_info(query, max_results)

        # If query mentions specific drug, get detailed info
        for drug_name, drug_id in self.ENDO_DRUG_IDS.items():
            if drug_name in query.lower():
                drug_info = await self._get_drug_by_id(drug_id)
                if drug_info:
                    results.insert(0, drug_info)
                    break

        return results[:max_results]

    async def _search_drugs(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search DrugBank for drugs."""
        try:
            url = f"{self.base_url}/drugs"
            params = {
                "q": query,
                "per_page": max_results,
            }

            response = await self._make_request(
                url, params, headers=self._get_headers()
            )
            return self.parse_response(response)

        except Exception as e:
            logger.warning("drugbank_api_search_failed", error=str(e))
            return []

    async def _get_drug_by_id(
        self,
        drug_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get drug information by DrugBank ID."""
        try:
            url = f"{self.base_url}/drugs/{drug_id}"

            response = await self._make_request(
                url, headers=self._get_headers()
            )

            if isinstance(response, dict):
                return self._parse_drug(response)
            return None

        except Exception as e:
            logger.debug("drugbank_drug_fetch_failed", drug_id=drug_id, error=str(e))
            return None

    def parse_response(self, response: Any) -> List[Dict[str, Any]]:
        """Parse DrugBank response into standard format."""
        results = []

        if isinstance(response, list):
            for item in response:
                parsed = self._parse_drug(item)
                if parsed:
                    results.append(parsed)
        elif isinstance(response, dict):
            parsed = self._parse_drug(response)
            if parsed:
                results.append(parsed)

        return results

    def _parse_drug(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single drug entry."""
        try:
            drugbank_id = item.get("drugbank_id", "")
            name = item.get("name", "")

            if not name:
                return None

            # Build content from available fields
            description = item.get("description", "")
            indication = item.get("indication", "")
            pharmacodynamics = item.get("pharmacodynamics", "")
            mechanism = item.get("mechanism_of_action", "")
            toxicity = item.get("toxicity", "")

            content_parts = []
            if indication:
                content_parts.append(f"Indication: {indication[:300]}")
            if description:
                content_parts.append(f"Description: {description[:200]}")
            if mechanism:
                content_parts.append(f"Mechanism: {mechanism[:200]}")

            content = " | ".join(content_parts) if content_parts else description[:500]

            # Get categories
            categories = [
                cat.get("name", "") for cat in item.get("categories", [])
            ]

            return self._standardize_result(
                title=name,
                content=content[:1000],
                url=f"https://go.drugbank.com/drugs/{drugbank_id}",
                drugbank_id=drugbank_id,
                indication=indication[:500] if indication else None,
                pharmacodynamics=pharmacodynamics[:300] if pharmacodynamics else None,
                mechanism_of_action=mechanism[:300] if mechanism else None,
                toxicity=toxicity[:300] if toxicity else None,
                categories=categories[:5],
                organization="DrugBank",
            )

        except Exception as e:
            logger.warning("drugbank_parse_error", error=str(e))
            return None

    def _get_static_drug_info(
        self,
        query: str,
        max_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """Return static drug information when API is not available."""
        # Provide basic information for common endometriosis drugs
        static_drugs = {
            "dienogest": {
                "title": "Dienogest",
                "content": "Dienogest is a synthetic progestogen used for treating endometriosis. It reduces endometrial lesion size and alleviates pain. Common side effects include headache, breast discomfort, and irregular bleeding.",
                "url": "https://go.drugbank.com/drugs/DB09123",
                "indication": "Treatment of endometriosis",
            },
            "leuprolide": {
                "title": "Leuprolide",
                "content": "Leuprolide is a GnRH agonist used to treat endometriosis by suppressing estrogen production. It can cause menopausal symptoms and is typically used for 6 months or less.",
                "url": "https://go.drugbank.com/drugs/DB00007",
                "indication": "Management of endometriosis, including pain relief",
            },
            "elagolix": {
                "title": "Elagolix (Orilissa)",
                "content": "Elagolix is an oral GnRH antagonist approved for moderate to severe endometriosis pain. It provides dose-dependent estrogen suppression with a more favorable side effect profile than GnRH agonists.",
                "url": "https://go.drugbank.com/drugs/DB11979",
                "indication": "Management of moderate to severe pain associated with endometriosis",
            },
        }

        results = []
        query_lower = query.lower()

        for drug_name, info in static_drugs.items():
            if drug_name in query_lower or any(
                term in query_lower for term in ["treatment", "medication", "drug", "pain"]
            ):
                results.append(
                    self._standardize_result(
                        title=info["title"],
                        content=info["content"],
                        url=info["url"],
                        indication=info["indication"],
                        organization="DrugBank",
                    )
                )

        return results[:max_results]
