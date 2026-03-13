"""PubMed E-utilities API client."""

from typing import Dict, Any, List, Optional
import xml.etree.ElementTree as ET

from app.services.apis.base import BaseAPIClient
from app.services.cache.cache_service import CacheService
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class PubMedAPIClient(BaseAPIClient):
    """Client for NCBI PubMed E-utilities API."""

    name = "pubmed"
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    cache_ttl = 604800  # 7 days for research articles

    def __init__(
        self,
        cache_service: CacheService,
        api_key: Optional[str] = None,
        email: str = "developer@endochat.org",
        **kwargs,
    ):
        super().__init__(cache_service, **kwargs)
        self.api_key = api_key
        self.email = email

    def _get_base_params(self) -> Dict[str, str]:
        """Get base parameters for all requests."""
        params = {"email": self.email, "tool": "EndoChat"}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Search PubMed for research articles."""
        # Step 1: Search for article IDs
        ids = await self._search_ids(query, max_results)
        if not ids:
            return []

        # Step 2: Fetch article details
        articles = await self._fetch_articles(ids)
        return articles

    async def _search_ids(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[str]:
        """Search for PubMed article IDs."""
        try:
            url = f"{self.base_url}/esearch.fcgi"

            # Build search query focused on endometriosis
            search_query = f"endometriosis AND ({query})"

            params = {
                **self._get_base_params(),
                "db": "pubmed",
                "term": search_query,
                "retmax": max_results,
                "retmode": "json",
                "sort": "relevance",
            }

            response = await self._make_request(url, params)

            if isinstance(response, dict):
                return response.get("esearchresult", {}).get("idlist", [])
            return []

        except Exception as e:
            logger.warning("pubmed_search_failed", error=str(e))
            return []

    async def _fetch_articles(self, ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch article details by IDs."""
        if not ids:
            return []

        try:
            url = f"{self.base_url}/efetch.fcgi"
            params = {
                **self._get_base_params(),
                "db": "pubmed",
                "id": ",".join(ids),
                "retmode": "xml",
            }

            xml_response = await self._make_request(url, params)
            return self.parse_response(xml_response)

        except Exception as e:
            logger.warning("pubmed_fetch_failed", error=str(e))
            return []

    def parse_response(self, response: Any) -> List[Dict[str, Any]]:
        """Parse PubMed XML response into standard format."""
        results = []

        if not isinstance(response, str):
            return results

        try:
            root = ET.fromstring(response)

            for article in root.findall(".//PubmedArticle"):
                parsed = self._parse_article(article)
                if parsed:
                    results.append(parsed)

        except ET.ParseError as e:
            logger.warning("pubmed_xml_parse_error", error=str(e))

        return results

    def _parse_article(self, article: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse a single PubMed article element."""
        try:
            # Get PMID
            pmid = article.findtext(".//PMID", "")
            if not pmid:
                return None

            # Get title
            title = article.findtext(".//ArticleTitle", "")

            # Get abstract
            abstract_parts = []
            for abstract_text in article.findall(".//AbstractText"):
                label = abstract_text.get("Label", "")
                text = abstract_text.text or ""
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)

            # Get authors
            authors = []
            for author in article.findall(".//Author"):
                last_name = author.findtext("LastName", "")
                fore_name = author.findtext("ForeName", "")
                if last_name:
                    authors.append(f"{fore_name} {last_name}".strip())

            # Get journal
            journal = article.findtext(".//Journal/Title", "")

            # Get publication date
            pub_date = self._extract_pub_date(article)

            # Get MeSH terms
            mesh_terms = [
                term.findtext("DescriptorName", "")
                for term in article.findall(".//MeshHeading")
            ]

            content = abstract if abstract else title

            return self._standardize_result(
                title=title,
                content=content[:1000],  # Limit content length
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                publication_date=pub_date,
                pmid=pmid,
                authors=authors[:5],  # Limit authors
                journal=journal,
                mesh_terms=mesh_terms[:10],
                organization="PubMed/NCBI",
            )

        except Exception as e:
            logger.warning("pubmed_article_parse_error", error=str(e))
            return None

    def _extract_pub_date(self, article: ET.Element) -> Optional[str]:
        """Extract publication date from article."""
        # Try PubDate first
        year = article.findtext(".//PubDate/Year")
        month = article.findtext(".//PubDate/Month", "01")
        day = article.findtext(".//PubDate/Day", "01")

        if year:
            try:
                month_num = self._month_to_num(month)
                return f"{year}-{month_num:02d}-{int(day):02d}"
            except (ValueError, TypeError):
                return year

        # Try ArticleDate
        article_date = article.find(".//ArticleDate")
        if article_date is not None:
            year = article_date.findtext("Year")
            month = article_date.findtext("Month", "01")
            day = article_date.findtext("Day", "01")
            if year:
                return f"{year}-{month}-{day}"

        return None

    def _month_to_num(self, month: str) -> int:
        """Convert month name or number to integer."""
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        try:
            return int(month)
        except ValueError:
            return month_map.get(month.lower()[:3], 1)

    async def get_article_by_pmid(self, pmid: str) -> Optional[Dict[str, Any]]:
        """Get a specific article by PMID."""
        articles = await self._fetch_articles([pmid])
        return articles[0] if articles else None
