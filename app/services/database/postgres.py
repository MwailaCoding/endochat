"""PostgreSQL connection pool using asyncpg."""

from typing import Optional, Any, List, Dict
import asyncpg
from asyncpg import Pool, Connection

from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class DatabasePool:
    """Async PostgreSQL connection pool manager."""

    def __init__(
        self,
        database_url: str,
        min_size: int = 5,
        max_size: int = 20,
    ):
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size
        self._pool: Optional[Pool] = None

    async def connect(self) -> None:
        """Initialize the connection pool."""
        try:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
                command_timeout=60,
            )
            logger.info("database_connected", pool_size=self.max_size)
        except Exception as e:
            logger.error("database_connection_failed", error=str(e))
            raise

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("database_disconnected")

    @property
    def pool(self) -> Pool:
        """Get the connection pool."""
        if self._pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        return self._pool

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query that doesn't return rows."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> List[asyncpg.Record]:
        """Fetch multiple rows."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        """Fetch a single row."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Fetch a single value."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def health_check(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            result = await self.fetchrow(
                "UPDATE health_check SET last_check = NOW() WHERE id = 1 RETURNING status, last_check"
            )
            return {
                "healthy": True,
                "status": result["status"] if result else "healthy",
                "last_check": str(result["last_check"]) if result else None,
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "unhealthy",
                "error": str(e),
            }


async def get_db_pool(database_url: str) -> DatabasePool:
    """Create and connect a new database pool."""
    pool = DatabasePool(database_url)
    await pool.connect()
    return pool
