"""High-level cache service with namespacing and fallback."""

from typing import Optional, Any, Dict
from datetime import datetime

from app.services.cache.redis_client import RedisCache
from app.services.utils.text import generate_cache_hash
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class InMemoryCache:
    """Simple in-memory cache fallback when Redis is unavailable."""

    def __init__(self):
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._max_size = 1000

    async def get(self, key: str) -> Optional[Any]:
        """Get value from in-memory cache."""
        if key in self._cache:
            value, expires_at = self._cache[key]
            if datetime.now() < expires_at:
                return value
            del self._cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in in-memory cache."""
        if len(self._cache) >= self._max_size:
            self._cleanup()
        from datetime import timedelta
        expires_at = datetime.now() + timedelta(seconds=ttl)
        self._cache[key] = (value, expires_at)
        return True

    async def delete(self, key: str) -> bool:
        """Delete from in-memory cache."""
        if key in self._cache:
            del self._cache[key]
        return True

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.get(key) is not None

    def _cleanup(self) -> None:
        """Remove expired entries."""
        now = datetime.now()
        expired = [k for k, (_, exp) in self._cache.items() if exp < now]
        for key in expired:
            del self._cache[key]
        if len(self._cache) >= self._max_size:
            oldest = sorted(self._cache.items(), key=lambda x: x[1][1])
            for key, _ in oldest[:len(oldest) // 2]:
                del self._cache[key]


class CacheService:
    """High-level cache service with namespacing."""

    def __init__(self, redis_cache: Optional[RedisCache]):
        self.redis = redis_cache
        self.fallback = InMemoryCache()
        self._use_redis = redis_cache is not None

    @property
    def cache(self):
        """Get the active cache implementation."""
        return self.redis if self._use_redis else self.fallback

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return await self.cache.get(key)

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache."""
        return await self.cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete from cache."""
        return await self.cache.delete(key)

    async def get_api_response(
        self,
        api_name: str,
        query: str,
    ) -> Optional[Any]:
        """Get cached API response."""
        key = f"api:{api_name}:{generate_cache_hash(query, api_name)}"
        result = await self.get(key)
        if result:
            logger.debug("cache_hit", cache_type="api", api=api_name)
        return result

    async def set_api_response(
        self,
        api_name: str,
        query: str,
        response: Any,
        ttl: int = 86400,
    ) -> bool:
        """Cache API response."""
        key = f"api:{api_name}:{generate_cache_hash(query, api_name)}"
        return await self.set(key, response, ttl)

    async def get_chat_response(
        self,
        question: str,
        mode: str,
    ) -> Optional[Any]:
        """Get cached chat response."""
        key = f"chat:{generate_cache_hash(question, mode)}:{mode}"
        result = await self.get(key)
        if result:
            logger.debug("cache_hit", cache_type="chat", mode=mode)
        return result

    async def set_chat_response(
        self,
        question: str,
        mode: str,
        response: Any,
        ttl: int = 86400,
    ) -> bool:
        """Cache chat response."""
        key = f"chat:{generate_cache_hash(question, mode)}:{mode}"
        return await self.set(key, response, ttl)

    async def track_popular_question(
        self,
        question: str,
        threshold: int = 10,
    ) -> int:
        """Track question popularity in cache."""
        key = f"popular:{generate_cache_hash(question, 'count')}"
        if self._use_redis and self.redis:
            count = await self.redis.increment(key)
            await self.redis.expire(key, 2592000)  # 30 days
            return count
        return 1

    async def health_check(self) -> dict:
        """Check cache health."""
        if self._use_redis and self.redis:
            return await self.redis.health_check()
        return {
            "healthy": True,
            "status": "in-memory fallback",
            "type": "memory",
        }
