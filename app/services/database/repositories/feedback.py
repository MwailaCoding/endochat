"""Repository for feedback data access."""

from typing import Optional, List, Dict, Any
from uuid import UUID

from app.services.database.postgres import DatabasePool
from app.services.database.models import Feedback
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class FeedbackRepository:
    """Data access layer for feedback."""

    def __init__(self, db: DatabasePool):
        self.db = db

    async def create(
        self,
        conversation_id: UUID,
        rating: int,
        message_id: Optional[str] = None,
        reason: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Feedback:
        """Create a new feedback record."""
        query = """
            INSERT INTO feedback (
                conversation_id, message_id, rating, reason, comment
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """
        record = await self.db.fetchrow(
            query,
            conversation_id,
            message_id,
            rating,
            reason,
            comment,
        )
        logger.info(
            "feedback_created",
            feedback_id=str(record["id"]),
            conversation_id=str(conversation_id),
            rating=rating,
        )
        return Feedback.from_record(record)

    async def get_by_id(self, feedback_id: UUID) -> Optional[Feedback]:
        """Get feedback by ID."""
        query = "SELECT * FROM feedback WHERE id = $1"
        record = await self.db.fetchrow(query, feedback_id)
        return Feedback.from_record(record) if record else None

    async def get_by_conversation(self, conversation_id: UUID) -> List[Feedback]:
        """Get all feedback for a conversation."""
        query = """
            SELECT * FROM feedback
            WHERE conversation_id = $1
            ORDER BY created_at DESC
        """
        records = await self.db.fetch(query, conversation_id)
        return [Feedback.from_record(r) for r in records]

    async def get_stats(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        query = """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE rating = 1) as positive,
                COUNT(*) FILTER (WHERE rating = -1) as negative
            FROM feedback
        """
        record = await self.db.fetchrow(query)
        total = record["total"]
        positive = record["positive"]
        negative = record["negative"]

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "satisfaction_rate": (positive / total * 100) if total > 0 else 0,
        }

    async def get_by_reason(
        self, reason: str, limit: int = 100
    ) -> List[Feedback]:
        """Get negative feedback by reason category."""
        query = """
            SELECT * FROM feedback
            WHERE reason = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        records = await self.db.fetch(query, reason, limit)
        return [Feedback.from_record(r) for r in records]

    async def get_recent_negative(self, limit: int = 50) -> List[Feedback]:
        """Get recent negative feedback for review."""
        query = """
            SELECT * FROM feedback
            WHERE rating = -1
            ORDER BY created_at DESC
            LIMIT $1
        """
        records = await self.db.fetch(query, limit)
        return [Feedback.from_record(r) for r in records]

    async def get_reason_breakdown(self) -> Dict[str, int]:
        """Get breakdown of negative feedback by reason."""
        query = """
            SELECT reason, COUNT(*) as count
            FROM feedback
            WHERE rating = -1 AND reason IS NOT NULL
            GROUP BY reason
            ORDER BY count DESC
        """
        records = await self.db.fetch(query)
        return {r["reason"]: r["count"] for r in records}
