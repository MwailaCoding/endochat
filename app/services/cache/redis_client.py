"""Async Redis client for caching."""

from typing import Optional, Any
import json
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio import Redis

from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class RedisCache:
    """Async Redis cache client."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis: Optional[Redis] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info("redis_connected", url=self.redis_url.split("@")[-1])
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            raise

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            logger.info("redis_disconnected")

    @property
    def client(self) -> Redis:
        """Get Redis client."""
        if self._redis is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._redis

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning("redis_get_error", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
    ) -> bool:
        """Set value in cache with TTL."""
        try:
            serialized = json.dumps(value, default=str)
            await self.client.setex(key, timedelta(seconds=ttl), serialized)
            return True
        except Exception as e:
            logger.warning("redis_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning("redis_delete_error", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.warning("redis_exists_error", key=key, error=str(e))
            return False

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        try:
            return await self.client.incrby(key, amount)
        except Exception as e:
            logger.warning("redis_incr_error", key=key, error=str(e))
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on existing key."""
        try:
            await self.client.expire(key, ttl)
            return True
        except Exception as e:
            logger.warning("redis_expire_error", key=key, error=str(e))
            return False

    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
        try:
            return await self.client.keys(pattern)
        except Exception as e:
            logger.warning("redis_keys_error", pattern=pattern, error=str(e))
            return []

    async def health_check(self) -> dict:
        """Check Redis connectivity."""
        try:
            await self.client.ping()
            info = await self.client.info("memory")
            return {
                "healthy": True,
                "status": "connected",
                "used_memory": info.get("used_memory_human", "unknown"),
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "disconnected",
                "error": str(e),
            }
