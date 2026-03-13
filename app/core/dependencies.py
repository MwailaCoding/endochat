"""Dependency injection for FastAPI."""

from typing import Optional, AsyncGenerator
from functools import lru_cache

from app.config import Settings, get_settings
from app.services.cache.redis_client import RedisCache
from app.services.cache.cache_service import CacheService
from app.services.database.postgres import DatabasePool
from app.services.database.repositories.conversation import ConversationRepository
from app.services.database.repositories.feedback import FeedbackRepository
from app.services.database.repositories.popular import PopularRepository
from app.services.apis.factory import APIClientFactory
from app.services.llm.client import LLMClient
from app.services.orchestrator import ChatOrchestrator

# Global instances
_db_pool: Optional[DatabasePool] = None
_redis_cache: Optional[RedisCache] = None
_cache_service: Optional[CacheService] = None
_api_factory: Optional[APIClientFactory] = None
_llm_client: Optional[LLMClient] = None
_orchestrator: Optional[ChatOrchestrator] = None


async def init_services(settings: Settings) -> None:
    """Initialize all services on startup."""
    global _db_pool, _redis_cache, _cache_service, _api_factory, _llm_client, _orchestrator

    # Database pool
    _db_pool = DatabasePool(settings.database_url)
    await _db_pool.connect()

    # Redis cache (optional)
    if settings.is_redis_available:
        _redis_cache = RedisCache(settings.redis_url)
        await _redis_cache.connect()
        _cache_service = CacheService(_redis_cache)
    else:
        _cache_service = CacheService(None)  # In-memory fallback

    # API client factory
    _api_factory = APIClientFactory(_cache_service, settings)

    # LLM client (optional)
    if settings.is_openai_available:
        _llm_client = LLMClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    # Main orchestrator
    _orchestrator = ChatOrchestrator(
        cache_service=_cache_service,
        api_factory=_api_factory,
        llm_client=_llm_client,
        db_pool=_db_pool,
    )


async def shutdown_services() -> None:
    """Cleanup services on shutdown."""
    global _db_pool, _redis_cache, _api_factory

    if _api_factory:
        await _api_factory.close()

    if _redis_cache:
        await _redis_cache.close()

    if _db_pool:
        await _db_pool.close()


def get_db_pool() -> DatabasePool:
    """Get database pool instance."""
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return _db_pool


# Alias for consistency with API routes
def get_database_pool() -> DatabasePool:
    """Get database pool instance (alias for get_db_pool)."""
    return get_db_pool()


def get_cache_service() -> CacheService:
    """Get cache service instance."""
    if _cache_service is None:
        raise RuntimeError("Cache service not initialized")
    return _cache_service


def get_api_factory() -> APIClientFactory:
    """Get API client factory instance."""
    if _api_factory is None:
        raise RuntimeError("API factory not initialized")
    return _api_factory


def get_llm_client() -> Optional[LLMClient]:
    """Get LLM client instance (may be None if not configured)."""
    return _llm_client


def get_orchestrator() -> ChatOrchestrator:
    """Get chat orchestrator instance."""
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return _orchestrator


async def get_conversation_repo() -> AsyncGenerator[ConversationRepository, None]:
    """Get conversation repository."""
    db = get_db_pool()
    yield ConversationRepository(db)


async def get_feedback_repo() -> AsyncGenerator[FeedbackRepository, None]:
    """Get feedback repository."""
    db = get_db_pool()
    yield FeedbackRepository(db)


async def get_popular_repo() -> AsyncGenerator[PopularRepository, None]:
    """Get popular questions repository."""
    db = get_db_pool()
    yield PopularRepository(db)
