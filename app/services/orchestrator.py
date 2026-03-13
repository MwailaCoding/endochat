"""Main orchestrator service coordinating the chat flow."""

import asyncio
import time
import uuid
from typing import Optional, Dict, List, Any

from app.models.chat import ChatResponse, SourceCitation, ConfidenceModel
from app.services.apis.factory import APIClientFactory
from app.services.llm.client import LLMClient
from app.services.llm.fallback import FallbackAnswerGenerator
from app.services.cache.cache_service import CacheService
from app.services.database.postgres import DatabasePool
from app.services.database.repositories.conversation import ConversationRepository
from app.services.database.repositories.popular import PopularRepository
from app.services.response.confidence import ConfidenceCalculator
from app.services.response.sources import SourceFormatter
from app.services.response.suggestions import SuggestionGenerator
from app.services.utils.text import generate_cache_hash
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class ChatOrchestrator:
    """Orchestrates the entire chat flow from question to response."""

    def __init__(
        self,
        cache_service: CacheService,
        api_factory: APIClientFactory,
        llm_client: Optional[LLMClient],
        db_pool: DatabasePool,
    ):
        self.cache = cache_service
        self.api_factory = api_factory
        self.llm = llm_client
        self.db_pool = db_pool

        # Response processing components
        self.fallback = FallbackAnswerGenerator()
        self.confidence_calculator = ConfidenceCalculator()
        self.source_formatter = SourceFormatter()
        self.suggestion_generator = SuggestionGenerator()

        # Repositories
        self._conversation_repo: Optional[ConversationRepository] = None
        self._popular_repo: Optional[PopularRepository] = None

    @property
    def conversation_repo(self) -> ConversationRepository:
        if self._conversation_repo is None:
            self._conversation_repo = ConversationRepository(self.db_pool)
        return self._conversation_repo

    @property
    def popular_repo(self) -> PopularRepository:
        if self._popular_repo is None:
            self._popular_repo = PopularRepository(self.db_pool)
        return self._popular_repo

    async def process_question(
        self,
        question: str,
        session_id: Optional[str] = None,
        mode: str = "detailed",
        use_llm: bool = True,
    ) -> ChatResponse:
        """Process a question and return a complete response."""
        start_time = time.time()

        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(
            "processing_question",
            question=question[:50],
            session_id=session_id,
            mode=mode,
        )

        # 1. Check cache
        cached = await self._check_cache(question, mode)
        if cached:
            logger.info("cache_hit", question=question[:50])
            return self._create_cached_response(cached, start_time)

        # 2. Search all APIs in parallel
        api_results = await self._search_apis(question)

        # 3. Format sources
        sources = self.source_formatter.format_sources(api_results)
        sources_found = len(sources)

        logger.info(
            "sources_found",
            count=sources_found,
            apis=list(api_results.keys()),
        )

        # 4. Generate answer
        if use_llm and self.llm and sources:
            answer, suggestions = await self._generate_llm_answer(
                question, sources, mode
            )
        else:
            answer = self.fallback.generate_answer(question, self._sources_to_dicts(sources))
            suggestions = self.fallback.generate_suggestions(question)

        # 5. Calculate confidence
        confidence = self.confidence_calculator.calculate(
            self._sources_to_dicts(sources)
        )

        # 6. Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)

        # 7. Create response
        conversation_id = str(uuid.uuid4())

        response = ChatResponse(
            answer=answer,
            sources=sources,
            confidence=confidence,
            response_time_ms=response_time_ms,
            from_cache=False,
            conversation_id=conversation_id,
            suggested_questions=suggestions,
        )

        # 8. Cache response (async)
        asyncio.create_task(
            self._cache_response(question, mode, response)
        )

        # 9. Save to database (async)
        asyncio.create_task(
            self._save_conversation(
                session_id=session_id,
                question=question,
                response=response,
            )
        )

        # 10. Track popular question (async)
        asyncio.create_task(
            self._track_popular(question)
        )

        logger.info(
            "question_processed",
            conversation_id=conversation_id,
            sources=sources_found,
            confidence=confidence.score,
            response_time_ms=response_time_ms,
        )

        return response

    async def _check_cache(
        self,
        question: str,
        mode: str,
    ) -> Optional[Dict[str, Any]]:
        """Check if response is cached."""
        try:
            return await self.cache.get_chat_response(question, mode)
        except Exception as e:
            logger.warning("cache_check_failed", error=str(e))
            return None

    async def _search_apis(
        self,
        question: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search all APIs for relevant information."""
        try:
            return await self.api_factory.search_all(question)
        except Exception as e:
            logger.error("api_search_failed", error=str(e))
            return {}

    async def _generate_llm_answer(
        self,
        question: str,
        sources: List[SourceCitation],
        mode: str,
    ) -> tuple[str, List[str]]:
        """Generate answer using LLM."""
        try:
            sources_dict = self._sources_to_dicts(sources)
            answer, suggestions = await self.llm.generate_answer_and_suggestions(
                question, sources_dict, mode
            )
            return answer, suggestions
        except Exception as e:
            logger.warning("llm_generation_failed", error=str(e))
            sources_dict = self._sources_to_dicts(sources)
            return (
                self.fallback.generate_answer(question, sources_dict),
                self.fallback.generate_suggestions(question),
            )

    async def _cache_response(
        self,
        question: str,
        mode: str,
        response: ChatResponse,
    ) -> None:
        """Cache the response."""
        try:
            response_dict = {
                "answer": response.answer,
                "sources": [s.model_dump() for s in response.sources],
                "confidence": response.confidence.model_dump(),
                "suggested_questions": response.suggested_questions,
            }
            await self.cache.set_chat_response(question, mode, response_dict)
        except Exception as e:
            logger.warning("cache_save_failed", error=str(e))

    async def _save_conversation(
        self,
        session_id: str,
        question: str,
        response: ChatResponse,
    ) -> None:
        """Save conversation to database."""
        try:
            sources_list = [s.model_dump() for s in response.sources]
            await self.conversation_repo.create(
                session_id=session_id,
                question=question,
                answer=response.answer,
                sources=sources_list,
                confidence=response.confidence.score,
                response_time_ms=response.response_time_ms,
            )
        except Exception as e:
            logger.warning("conversation_save_failed", error=str(e))

    async def _track_popular(self, question: str) -> None:
        """Track question popularity."""
        try:
            await self.popular_repo.increment_count(question)
        except Exception as e:
            logger.debug("popular_tracking_failed", error=str(e))

    def _create_cached_response(
        self,
        cached: Dict[str, Any],
        start_time: float,
    ) -> ChatResponse:
        """Create response from cached data."""
        sources = [
            SourceCitation(**s) for s in cached.get("sources", [])
        ]
        confidence = ConfidenceModel(**cached.get("confidence", {
            "score": 50, "level": "medium", "badge": "MEDIUM", "reason": "From cache"
        }))

        return ChatResponse(
            answer=cached.get("answer", ""),
            sources=sources,
            confidence=confidence,
            response_time_ms=int((time.time() - start_time) * 1000),
            from_cache=True,
            conversation_id=str(uuid.uuid4()),
            suggested_questions=cached.get("suggested_questions", []),
        )

    def _sources_to_dicts(
        self,
        sources: List[SourceCitation],
    ) -> List[Dict[str, Any]]:
        """Convert SourceCitation list to dicts for processing."""
        return [s.model_dump() for s in sources]

    async def process_simple(
        self,
        question: str,
        session_id: Optional[str] = None,
    ) -> ChatResponse:
        """Process question without LLM (faster, cheaper)."""
        return await self.process_question(
            question=question,
            session_id=session_id,
            mode="simple",
            use_llm=False,
        )

    async def get_suggestions(
        self,
        question: str,
        category: Optional[str] = None,
    ) -> List[str]:
        """Get follow-up suggestions for a question."""
        return self.suggestion_generator.generate(question, category)
