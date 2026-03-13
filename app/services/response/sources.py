"""Source formatting and deduplication."""

from typing import List, Dict, Any, Optional
from datetime import datetime

from app.models.chat import SourceCitation
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class SourceFormatter:
    """Format and deduplicate sources from multiple APIs."""

    # Priority order for sources
    SOURCE_PRIORITY = ["who", "pubmed", "openfda", "drugbank", "medlineplus"]

    def format_sources(
        self,
        api_results: Dict[str, List[Dict[str, Any]]],
        max_sources: int = 10,
    ) -> List[SourceCitation]:
        """Format and deduplicate sources from all APIs."""
        all_sources = []

        # Flatten results from all APIs
        for api_name, results in api_results.items():
            for result in results:
                source = self._create_source_citation(result, api_name)
                if source:
                    all_sources.append(source)

        # Deduplicate
        unique_sources = self._deduplicate_sources(all_sources)

        # Sort by priority and relevance
        sorted_sources = self._sort_sources(unique_sources)

        # Limit results
        return sorted_sources[:max_sources]

    def _create_source_citation(
        self,
        result: Dict[str, Any],
        default_source: str,
    ) -> Optional[SourceCitation]:
        """Create a SourceCitation from API result."""
        try:
            source_type = result.get("source", default_source).lower()

            # Map to valid source types
            valid_sources = ["who", "pubmed", "openfda", "drugbank", "medlineplus"]
            if source_type not in valid_sources:
                source_type = "who"  # Default fallback

            title = result.get("title", "")
            if not title:
                return None

            # Extract snippet from content
            content = result.get("content", "")
            snippet = self._create_snippet(content)

            return SourceCitation(
                source=source_type,
                title=title[:200],  # Limit title length
                url=result.get("url"),
                snippet=snippet,
                publication_date=result.get("publication_date"),
                confidence=self._calculate_source_confidence(result),
            )

        except Exception as e:
            logger.warning("source_format_error", error=str(e))
            return None

    def _create_snippet(
        self,
        content: str,
        max_length: int = 200,
    ) -> Optional[str]:
        """Create a snippet from content."""
        if not content:
            return None

        content = content.strip()
        if len(content) <= max_length:
            return content

        # Find a good break point
        truncated = content[:max_length]
        last_period = truncated.rfind(".")
        last_space = truncated.rfind(" ")

        if last_period > max_length * 0.7:
            return content[: last_period + 1]
        elif last_space > max_length * 0.8:
            return content[:last_space] + "..."
        else:
            return truncated + "..."

    def _calculate_source_confidence(
        self,
        result: Dict[str, Any],
    ) -> float:
        """Calculate confidence score for a single source."""
        confidence = 0.5  # Base confidence

        # Boost for specific source types
        source_type = result.get("source", "").lower()
        source_boosts = {
            "who": 0.3,
            "pubmed": 0.25,
            "openfda": 0.15,
            "drugbank": 0.15,
        }
        confidence += source_boosts.get(source_type, 0)

        # Boost for having publication date
        if result.get("publication_date"):
            confidence += 0.1

        # Boost for having URL
        if result.get("url"):
            confidence += 0.05

        return min(1.0, confidence)

    def _deduplicate_sources(
        self,
        sources: List[SourceCitation],
    ) -> List[SourceCitation]:
        """Remove duplicate sources based on title similarity."""
        unique = []
        seen_titles = set()

        for source in sources:
            # Normalize title for comparison
            normalized = self._normalize_title(source.title)

            # Check for exact or similar matches
            is_duplicate = False
            for seen in seen_titles:
                if self._titles_similar(normalized, seen):
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen_titles.add(normalized)
                unique.append(source)

        return unique

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        return title.lower().strip()

    def _titles_similar(
        self,
        title1: str,
        title2: str,
        threshold: float = 0.8,
    ) -> bool:
        """Check if two titles are similar."""
        # Simple word overlap check
        words1 = set(title1.split())
        words2 = set(title2.split())

        if not words1 or not words2:
            return False

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold

    def _sort_sources(
        self,
        sources: List[SourceCitation],
    ) -> List[SourceCitation]:
        """Sort sources by priority and confidence."""
        def sort_key(source: SourceCitation) -> tuple:
            # Priority index (lower is better)
            try:
                priority = self.SOURCE_PRIORITY.index(source.source)
            except ValueError:
                priority = len(self.SOURCE_PRIORITY)

            # Confidence (higher is better, so negate)
            confidence = -(source.confidence or 0)

            return (priority, confidence)

        return sorted(sources, key=sort_key)

    def format_for_display(
        self,
        sources: List[SourceCitation],
    ) -> List[Dict[str, Any]]:
        """Format sources for display in response."""
        return [
            {
                "source": s.source,
                "title": s.title,
                "url": s.url,
                "snippet": s.snippet,
                "publication_date": s.publication_date,
                "confidence": s.confidence,
            }
            for s in sources
        ]
