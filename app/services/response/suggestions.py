"""Generate follow-up question suggestions."""

from typing import List, Optional

from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class SuggestionGenerator:
    """Generate contextual follow-up question suggestions."""

    # Category-based suggestions
    CATEGORY_SUGGESTIONS = {
        "symptoms": [
            "What causes endometriosis pain?",
            "How can I manage endometriosis symptoms?",
            "When should I see a doctor about my symptoms?",
            "Are there natural remedies for symptom relief?",
        ],
        "treatment": [
            "What are the side effects of endometriosis treatment?",
            "How long does endometriosis treatment take?",
            "Are there surgical options for endometriosis?",
            "What are the latest treatment advances?",
        ],
        "diagnosis": [
            "How is endometriosis diagnosed?",
            "What happens during a laparoscopy?",
            "How long does diagnosis typically take?",
            "What tests are used to diagnose endometriosis?",
        ],
        "causes": [
            "What are the risk factors for endometriosis?",
            "Is endometriosis hereditary?",
            "Can endometriosis be prevented?",
            "What causes endometriosis to develop?",
        ],
        "fertility": [
            "How does endometriosis affect fertility?",
            "What fertility treatments work for endometriosis patients?",
            "Can I get pregnant with endometriosis?",
            "Should I freeze my eggs if I have endometriosis?",
        ],
        "lifestyle": [
            "What diet changes help with endometriosis?",
            "Does exercise help manage endometriosis?",
            "How does stress affect endometriosis?",
            "What lifestyle modifications are recommended?",
        ],
        "support": [
            "How do I explain endometriosis to others?",
            "Are there support groups for endometriosis?",
            "How can I cope with chronic pain?",
            "What resources are available for patients?",
        ],
    }

    # Question pattern mappings for context-aware suggestions
    PATTERN_SUGGESTIONS = {
        "pain": [
            "What medications help with endometriosis pain?",
            "Are there non-drug pain management options?",
            "How can I track my pain patterns?",
        ],
        "surgery": [
            "What types of surgery treat endometriosis?",
            "What is the recovery time after surgery?",
            "How effective is surgery for endometriosis?",
        ],
        "medication": [
            "What are the side effects of hormonal treatment?",
            "How long should I take medication?",
            "Are there alternative medications available?",
        ],
        "doctor": [
            "What questions should I ask my doctor?",
            "How do I find an endometriosis specialist?",
            "What should I expect at my appointment?",
        ],
    }

    def generate(
        self,
        question: str,
        category: Optional[str] = None,
        count: int = 3,
    ) -> List[str]:
        """Generate follow-up suggestions."""
        suggestions = []

        # Get category-based suggestions
        if category and category in self.CATEGORY_SUGGESTIONS:
            suggestions.extend(self.CATEGORY_SUGGESTIONS[category])

        # Get pattern-based suggestions
        pattern_suggestions = self._get_pattern_suggestions(question)
        suggestions.extend(pattern_suggestions)

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for s in suggestions:
            normalized = s.lower()
            if normalized not in seen:
                seen.add(normalized)
                unique.append(s)

        # Filter out suggestions too similar to the original question
        filtered = [
            s for s in unique
            if not self._is_similar_question(question, s)
        ]

        # Add general suggestions if needed
        if len(filtered) < count:
            general = self._get_general_suggestions()
            for s in general:
                if s.lower() not in seen and not self._is_similar_question(question, s):
                    filtered.append(s)
                    if len(filtered) >= count:
                        break

        return filtered[:count]

    def _get_pattern_suggestions(self, question: str) -> List[str]:
        """Get suggestions based on question patterns."""
        question_lower = question.lower()
        suggestions = []

        for pattern, pattern_suggestions in self.PATTERN_SUGGESTIONS.items():
            if pattern in question_lower:
                suggestions.extend(pattern_suggestions)

        return suggestions

    def _get_general_suggestions(self) -> List[str]:
        """Get general follow-up suggestions."""
        return [
            "What are the stages of endometriosis?",
            "How common is endometriosis?",
            "What ongoing research exists for endometriosis?",
            "How does endometriosis affect daily life?",
            "What complications can endometriosis cause?",
        ]

    def _is_similar_question(
        self,
        original: str,
        suggested: str,
        threshold: float = 0.6,
    ) -> bool:
        """Check if suggested question is too similar to original."""
        orig_words = set(original.lower().split())
        sugg_words = set(suggested.lower().split())

        # Remove common words
        stop_words = {
            "what", "how", "is", "are", "can", "does", "do",
            "the", "a", "an", "for", "with", "of", "to", "in",
            "endometriosis", "i", "my", "about"
        }
        orig_words -= stop_words
        sugg_words -= stop_words

        if not orig_words or not sugg_words:
            return False

        intersection = len(orig_words & sugg_words)
        smaller = min(len(orig_words), len(sugg_words))

        similarity = intersection / smaller if smaller > 0 else 0
        return similarity >= threshold

    def get_starter_questions(self) -> List[str]:
        """Get starter questions for new users."""
        return [
            "What is endometriosis?",
            "What are the symptoms of endometriosis?",
            "How is endometriosis diagnosed?",
            "What treatments are available?",
            "How does endometriosis affect fertility?",
        ]

    def get_category_questions(self, category: str, count: int = 5) -> List[str]:
        """Get questions for a specific category."""
        questions = self.CATEGORY_SUGGESTIONS.get(category, [])
        return questions[:count]
