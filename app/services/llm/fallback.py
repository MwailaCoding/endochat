"""Fallback answer generator when OpenAI is unavailable."""

from typing import List, Dict, Any, Optional
import re

from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class FallbackAnswerGenerator:
    """Generate answers without LLM using templates and source content."""

    # Default suggestions by category
    DEFAULT_SUGGESTIONS = {
        "symptoms": [
            "What causes these symptoms?",
            "When should I see a doctor?",
            "What treatments help with symptoms?",
        ],
        "treatment": [
            "What are the side effects of treatment?",
            "How long does treatment typically take?",
            "Are there alternative treatments available?",
        ],
        "diagnosis": [
            "What tests are used for diagnosis?",
            "How long does diagnosis typically take?",
            "What should I expect during an examination?",
        ],
        "causes": [
            "What are the risk factors?",
            "Is endometriosis hereditary?",
            "Can it be prevented?",
        ],
        "fertility": [
            "What fertility treatments are available?",
            "How does treatment affect fertility?",
            "What are my options for having children?",
        ],
        "general": [
            "What are the common symptoms of endometriosis?",
            "How is endometriosis treated?",
            "Can endometriosis affect fertility?",
        ],
    }

    def generate_answer(
        self,
        question: str,
        sources: List[Dict[str, Any]],
    ) -> str:
        """Generate answer from sources without LLM."""
        if not sources:
            return self._no_sources_response()

        # Extract key information from sources
        key_points = self._extract_key_points(sources)

        if not key_points:
            return self._limited_info_response(sources)

        # Build response
        response_parts = [
            "Based on the information I found from trusted health sources:\n"
        ]

        for i, point in enumerate(key_points[:3], 1):
            response_parts.append(f"\n{point}")

        response_parts.append(
            "\n\nFor more detailed information, please review the sources provided below. "
            "Always consult with a healthcare provider for personalized medical advice."
        )

        return "".join(response_parts)

    def _extract_key_points(
        self,
        sources: List[Dict[str, Any]],
    ) -> List[str]:
        """Extract key points from sources."""
        points = []

        for i, source in enumerate(sources[:3], 1):
            content = source.get("content", "")
            source_name = source.get("organization", source.get("source", "source"))

            if content:
                # Get first meaningful sentence or paragraph
                excerpt = self._get_excerpt(content)
                if excerpt:
                    points.append(f"According to {source_name} [{i}]: {excerpt}")

        return points

    def _get_excerpt(self, content: str, max_length: int = 200) -> str:
        """Extract a meaningful excerpt from content."""
        content = content.strip()

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', content)

        excerpt = ""
        for sentence in sentences:
            if len(excerpt) + len(sentence) < max_length:
                excerpt += sentence + " "
            else:
                break

        return excerpt.strip()

    def _no_sources_response(self) -> str:
        """Response when no sources are found."""
        return (
            "I couldn't find specific information about that in my current sources. "
            "Please try:\n"
            "- Rephrasing your question\n"
            "- Asking about a specific aspect of endometriosis\n"
            "- Consulting with a healthcare provider for personalized information\n\n"
            "Some topics I can help with include symptoms, diagnosis, treatment options, "
            "and impact on fertility."
        )

    def _limited_info_response(self, sources: List[Dict[str, Any]]) -> str:
        """Response when sources have limited relevant content."""
        source_names = [
            s.get("organization", s.get("source", "source"))
            for s in sources[:3]
        ]
        unique_sources = list(set(source_names))

        return (
            f"I found some related information from {', '.join(unique_sources)}, "
            "but it may not fully answer your specific question. "
            "Please review the sources below for details, and consider consulting "
            "with a healthcare provider for more specific guidance."
        )

    def generate_suggestions(
        self,
        question: str,
        category: Optional[str] = None,
    ) -> List[str]:
        """Generate follow-up suggestions based on question category."""
        if category is None:
            category = self._classify_question(question)

        return self.DEFAULT_SUGGESTIONS.get(
            category,
            self.DEFAULT_SUGGESTIONS["general"]
        )

    def _classify_question(self, question: str) -> str:
        """Simple keyword-based question classification."""
        question_lower = question.lower()

        keyword_categories = {
            "symptoms": ["symptom", "pain", "cramp", "bleed", "period", "feel"],
            "treatment": ["treat", "medication", "medicine", "surgery", "therapy", "cure"],
            "diagnosis": ["diagnos", "test", "exam", "doctor", "find out", "how know"],
            "causes": ["cause", "why", "reason", "develop", "get", "risk"],
            "fertility": ["fertil", "pregnant", "baby", "conceive", "child", "ivf"],
        }

        for category, keywords in keyword_categories.items():
            if any(kw in question_lower for kw in keywords):
                return category

        return "general"

    def generate_simple_answer(
        self,
        question: str,
        sources: List[Dict[str, Any]],
    ) -> str:
        """Generate a simplified answer from sources."""
        if not sources:
            return self._no_sources_response()

        # Use simpler language
        response_parts = ["Here's what I found:\n"]

        for i, source in enumerate(sources[:2], 1):
            content = source.get("content", "")
            if content:
                # Simplify the excerpt
                excerpt = self._get_excerpt(content, max_length=150)
                excerpt = self._simplify_text(excerpt)
                response_parts.append(f"\n• {excerpt} [{i}]")

        response_parts.append(
            "\n\nPlease check with a doctor for advice about your specific situation."
        )

        return "".join(response_parts)

    def _simplify_text(self, text: str) -> str:
        """Basic text simplification (remove complex terms)."""
        # Replace some medical terms with simpler alternatives
        replacements = {
            "pathophysiology": "how it develops",
            "etiology": "causes",
            "manifestations": "symptoms",
            "therapeutic": "treatment",
            "pharmacological": "medication",
            "surgical intervention": "surgery",
        }

        result = text
        for complex_term, simple_term in replacements.items():
            result = re.sub(
                rf'\b{complex_term}\b',
                simple_term,
                result,
                flags=re.IGNORECASE
            )

        return result
