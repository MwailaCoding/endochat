"""OpenAI client for answer generation."""

from typing import List, Dict, Any, Optional
import asyncio

from openai import AsyncOpenAI

from app.services.llm.prompts import PromptTemplates
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Async OpenAI client for generating answers."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.templates = PromptTemplates()

    async def generate_answer(
        self,
        question: str,
        sources: List[Dict[str, Any]],
        mode: str = "detailed",
    ) -> str:
        """Generate an answer using retrieved sources."""
        if not sources:
            return "I couldn't find relevant information to answer your question. Please try rephrasing or ask about a different aspect of endometriosis."

        # Format context from sources
        context = self.templates.format_context(sources)

        # Select prompt template based on mode
        if mode == "simple":
            prompt = self.templates.simple_answer(question, context)
        else:
            prompt = self.templates.detailed_answer(question, context)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PromptTemplates.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            answer = response.choices[0].message.content
            logger.info(
                "llm_answer_generated",
                model=self.model,
                tokens=response.usage.total_tokens if response.usage else 0,
            )
            return answer.strip()

        except Exception as e:
            logger.error("llm_generation_failed", error=str(e))
            raise

    async def generate_suggestions(
        self,
        question: str,
        answer: str,
        count: int = 3,
    ) -> List[str]:
        """Generate follow-up question suggestions."""
        prompt = self.templates.suggestions(question, answer, count)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=200,
            )

            suggestions_text = response.choices[0].message.content
            suggestions = [
                s.strip().lstrip("-•").strip()
                for s in suggestions_text.split("\n")
                if s.strip() and len(s.strip()) > 10
            ]

            return suggestions[:count]

        except Exception as e:
            logger.warning("llm_suggestions_failed", error=str(e))
            return []

    async def simplify_text(self, complex_text: str) -> str:
        """Simplify medical text for patients."""
        prompt = self.templates.simplify(complex_text)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=400,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning("llm_simplify_failed", error=str(e))
            return complex_text

    async def classify_question(self, question: str) -> Optional[str]:
        """Classify question into a category."""
        prompt = self.templates.classify_question(question)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=20,
            )

            category = response.choices[0].message.content.strip().lower()

            valid_categories = [
                "symptoms", "treatment", "diagnosis", "causes",
                "fertility", "lifestyle", "support", "general", "off-topic"
            ]

            return category if category in valid_categories else "general"

        except Exception as e:
            logger.debug("llm_classify_failed", error=str(e))
            return None

    async def generate_answer_and_suggestions(
        self,
        question: str,
        sources: List[Dict[str, Any]],
        mode: str = "detailed",
    ) -> tuple[str, List[str]]:
        """Generate answer and suggestions in parallel."""
        answer = await self.generate_answer(question, sources, mode)

        # Generate suggestions after we have the answer
        suggestions = await self.generate_suggestions(question, answer)

        return answer, suggestions
