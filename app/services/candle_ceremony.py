"""Candle ceremony service for community awareness events."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, date
from dataclasses import dataclass

from app.services.utils.logging import get_logger
from app.core.exceptions import EndoChatException

logger = get_logger(__name__)


class CandleCeremonyError(EndoChatException):
    """Candle ceremony service error."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message=message, detail=detail, error_code="CANDLE_ERROR")


@dataclass
class Candle:
    """Candle data model."""

    id: UUID
    session_id: str
    message: Optional[str]
    dedication: Optional[str]
    location: Optional[str]
    color: str
    lit_at: datetime


@dataclass
class CandleMessage:
    """Message associated with a candle."""

    id: UUID
    candle_id: UUID
    message: str
    created_at: datetime


CANDLE_COLORS = [
    "yellow",
    "gold",
    "amber",
    "orange",
    "white",
    "cream",
]

AWARENESS_TARGET = 10000


class CandleCeremonyService:
    """Service for virtual candle lighting ceremony."""

    def __init__(self, db_pool, cache_service=None):
        """Initialize with database pool and optional cache."""
        self.db_pool = db_pool
        self.cache = cache_service

    async def get_candle_count(self) -> dict:
        """
        Get the current candle count.

        Returns count and progress towards target.
        """
        cache_key = "candles:count"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

        query = "SELECT COUNT(*) FROM candles"
        async with self.db_pool.pool.acquire() as conn:
            count = await conn.fetchval(query) or 0

        today_query = "SELECT COUNT(*) FROM candles WHERE lit_date = $1"
        async with self.db_pool.pool.acquire() as conn:
            today_count = await conn.fetchval(today_query, date.today()) or 0

        result = {
            "total": count,
            "today": today_count,
            "target": AWARENESS_TARGET,
            "progress_percent": round(count / AWARENESS_TARGET * 100, 1),
            "remaining": max(0, AWARENESS_TARGET - count),
        }

        if self.cache:
            await self.cache.set(cache_key, result, ttl=60)

        return result

    async def can_light_today(self, session_id: str) -> bool:
        """Check if a session can light a candle today."""
        query = """
            SELECT EXISTS(
                SELECT 1 FROM candles
                WHERE session_id = $1 AND lit_date = $2
            )
        """
        async with self.db_pool.pool.acquire() as conn:
            exists = await conn.fetchval(query, session_id, date.today())
        return not exists

    async def light_candle(
        self,
        session_id: str,
        message: Optional[str] = None,
        dedication: Optional[str] = None,
        location: Optional[str] = None,
        color: str = "yellow",
    ) -> UUID:
        """
        Light a virtual candle.

        Args:
            session_id: User's session ID
            message: Optional message of hope/support
            dedication: Optional dedication (e.g., "For my sister")
            location: Optional location
            color: Candle color

        Returns:
            Candle ID

        Raises:
            CandleCeremonyError: If user already lit today
        """
        if not await self.can_light_today(session_id):
            raise CandleCeremonyError(
                message="Already lit a candle today",
                detail="You can light one candle per day. Come back tomorrow!",
            )

        if color not in CANDLE_COLORS:
            color = "yellow"

        if message and len(message) > 500:
            message = message[:500]

        if dedication and len(dedication) > 200:
            dedication = dedication[:200]

        query = """
            INSERT INTO candles (session_id, message, dedication, location, color)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """
        async with self.db_pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                query, session_id, message, dedication, location, color
            )

        if self.cache:
            await self.cache.delete("candles:count")

        logger.info(
            "Candle lit",
            candle_id=str(row["id"]),
            location=location,
        )
        return row["id"]

    async def get_recent_candles(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Candle]:
        """Get recently lit candles with messages."""
        query = """
            SELECT id, session_id, message, dedication, location, color, lit_at
            FROM candles
            WHERE message IS NOT NULL AND message != ''
            ORDER BY lit_at DESC
            LIMIT $1 OFFSET $2
        """
        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)

        return [
            Candle(
                id=row["id"],
                session_id=row["session_id"][:8] + "...",
                message=row["message"],
                dedication=row["dedication"],
                location=row["location"],
                color=row["color"],
                lit_at=row["lit_at"],
            )
            for row in rows
        ]

    async def get_candle(self, candle_id: UUID) -> Optional[Candle]:
        """Get a single candle by ID."""
        query = """
            SELECT id, session_id, message, dedication, location, color, lit_at
            FROM candles
            WHERE id = $1
        """
        async with self.db_pool.pool.acquire() as conn:
            row = await conn.fetchrow(query, candle_id)

        if not row:
            return None

        return Candle(
            id=row["id"],
            session_id=row["session_id"][:8] + "...",
            message=row["message"],
            dedication=row["dedication"],
            location=row["location"],
            color=row["color"],
            lit_at=row["lit_at"],
        )

    async def get_my_candles(
        self,
        session_id: str,
        limit: int = 20,
    ) -> List[Candle]:
        """Get candles lit by a session."""
        query = """
            SELECT id, session_id, message, dedication, location, color, lit_at
            FROM candles
            WHERE session_id = $1
            ORDER BY lit_at DESC
            LIMIT $2
        """
        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, session_id, limit)

        return [
            Candle(
                id=row["id"],
                session_id=row["session_id"],
                message=row["message"],
                dedication=row["dedication"],
                location=row["location"],
                color=row["color"],
                lit_at=row["lit_at"],
            )
            for row in rows
        ]

    async def get_locations(self) -> List[dict]:
        """Get aggregated candle locations for visualization."""
        cache_key = "candles:locations"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

        query = """
            SELECT location, COUNT(*) as count
            FROM candles
            WHERE location IS NOT NULL AND location != ''
            GROUP BY location
            ORDER BY count DESC
            LIMIT 50
        """
        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query)

        locations = [
            {"location": row["location"], "count": row["count"]}
            for row in rows
        ]

        if self.cache:
            await self.cache.set(cache_key, locations, ttl=300)

        return locations

    async def get_stats(self) -> dict:
        """Get ceremony statistics."""
        cache_key = "candles:stats"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

        async with self.db_pool.pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM candles") or 0

            unique_participants = await conn.fetchval(
                "SELECT COUNT(DISTINCT session_id) FROM candles"
            ) or 0

            with_messages = await conn.fetchval(
                "SELECT COUNT(*) FROM candles WHERE message IS NOT NULL AND message != ''"
            ) or 0

            unique_locations = await conn.fetchval(
                "SELECT COUNT(DISTINCT location) FROM candles WHERE location IS NOT NULL"
            ) or 0

        stats = {
            "total_candles": total,
            "unique_participants": unique_participants,
            "candles_with_messages": with_messages,
            "unique_locations": unique_locations,
            "target": AWARENESS_TARGET,
            "progress_percent": round(total / AWARENESS_TARGET * 100, 1),
        }

        if self.cache:
            await self.cache.set(cache_key, stats, ttl=300)

        return stats

    async def add_message_to_candle(
        self,
        candle_id: UUID,
        message: str,
        from_session: Optional[str] = None,
    ) -> UUID:
        """Add a supportive message to someone's candle."""
        if len(message) > 500:
            message = message[:500]

        query = """
            INSERT INTO candle_messages (candle_id, message, from_session)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        async with self.db_pool.pool.acquire() as conn:
            row = await conn.fetchrow(query, candle_id, message, from_session)
        return row["id"]

    async def get_candle_messages(
        self,
        candle_id: UUID,
        limit: int = 20,
    ) -> List[CandleMessage]:
        """Get messages for a candle."""
        query = """
            SELECT id, candle_id, message, created_at
            FROM candle_messages
            WHERE candle_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, candle_id, limit)

        return [
            CandleMessage(
                id=row["id"],
                candle_id=row["candle_id"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
