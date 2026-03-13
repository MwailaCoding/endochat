"""Confidence scoring for answers."""

from typing import List, Dict, Any

from app.models.chat import ConfidenceModel
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class ConfidenceCalculator:
    """Calculate confidence scores for answers based on sources."""

    # Source weights
    SOURCE_WEIGHTS = {
        "who": 25,        # Authoritative international health organization
        "pubmed": 20,     # Peer-reviewed research
        "openfda": 15,    # Government drug information
        "drugbank": 15,   # Comprehensive drug database
        "medlineplus": 15,  # Consumer health information
    }

    # Confidence level thresholds
    HIGH_THRESHOLD = 80
    MEDIUM_THRESHOLD = 50

    def calculate(self, sources: List[Dict[str, Any]]) -> ConfidenceModel:
        """Calculate confidence score from sources."""
        if not sources:
            return ConfidenceModel(
                score=0,
                level="low",
                badge="LOW",
                reason="No sources found",
            )

        score = 0
        reasons = []

        # Source count bonus
        source_count = len(sources)
        if source_count >= 3:
            score += 30
            reasons.append("Multiple sources corroborate information")
        elif source_count >= 2:
            score += 20
            reasons.append("Information from multiple sources")
        else:
            score += 10
            reasons.append("Single source available")

        # Source type bonuses
        source_types = set(s.get("source", "").lower() for s in sources)

        for source_type, weight in self.SOURCE_WEIGHTS.items():
            if source_type in source_types:
                score += weight
                if source_type == "who":
                    reasons.append("WHO authoritative source")
                elif source_type == "pubmed":
                    reasons.append("Peer-reviewed research")
                elif source_type in ("openfda", "drugbank"):
                    reasons.append("Official drug information")

        # Content quality bonuses
        quality_score = self._assess_content_quality(sources)
        score += quality_score

        # Cap at 100
        score = min(100, score)

        # Determine level
        if score >= self.HIGH_THRESHOLD:
            level = "high"
            badge = "HIGH"
        elif score >= self.MEDIUM_THRESHOLD:
            level = "medium"
            badge = "MEDIUM"
        else:
            level = "low"
            badge = "LOW"

        # Build reason string
        reason = "; ".join(reasons[:3]) if reasons else "Based on available sources"

        logger.debug(
            "confidence_calculated",
            score=score,
            level=level,
            sources=source_count,
        )

        return ConfidenceModel(
            score=score,
            level=level,
            badge=badge,
            reason=reason,
        )

    def _assess_content_quality(self, sources: List[Dict[str, Any]]) -> int:
        """Assess quality of source content."""
        quality_score = 0

        for source in sources:
            content = source.get("content", "")

            # Check content length (substantial content)
            if len(content) > 200:
                quality_score += 2
            elif len(content) > 100:
                quality_score += 1

            # Check for publication date (recent is better)
            if source.get("publication_date"):
                quality_score += 2

            # Check for URL (verifiable source)
            if source.get("url"):
                quality_score += 1

        # Cap quality bonus
        return min(15, quality_score)

    def get_confidence_description(self, level: str) -> str:
        """Get human-readable confidence description."""
        descriptions = {
            "high": (
                "This information comes from multiple authoritative sources including "
                "peer-reviewed research and official health organizations."
            ),
            "medium": (
                "This information is supported by credible sources, but you may want "
                "to verify with additional research or healthcare providers."
            ),
            "low": (
                "Limited information available. Please consult healthcare providers "
                "or search for additional sources for more comprehensive information."
            ),
        }
        return descriptions.get(level, descriptions["low"])
