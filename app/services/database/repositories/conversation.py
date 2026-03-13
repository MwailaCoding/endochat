"""Repository for conversation data access."""

from typing import Optional, List, Dict, Any
from uuid import UUID
import json

from app.services.database.postgres import DatabasePool
from app.services.database.models import Conversation
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class ConversationRepository:
    """Data access layer for conversations."""

    def __init__(self, db: DatabasePool):
        self.db = db

    async def create(
        self,
        session_id: str,
        question: str,
        answer: str,
        sources: List[Dict[str, Any]],
        confidence: Optional[int] = None,
        response_time_ms: Optional[int] = None,
    ) -> Conversation:
        """Create a new conversation record."""
        query = """
            INSERT INTO conversations (
                session_id, question, answer, sources, confidence, response_time_ms
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6)
            RETURNING *
        """
        record = await self.db.fetchrow(
            query,
            session_id,
            question,
            answer,
            json.dumps(sources),
            confidence,
            response_time_ms,
        )
        logger.info(
            "conversation_created",
            conversation_id=str(record["id"]),
            session_id=session_id,
        )
        return Conversation.from_record(record)

    async def get_by_id(self, conversation_id: UUID) -> Optional[Conversation]:
        """Get a conversation by ID."""
        query = "SELECT * FROM conversations WHERE id = $1"
        record = await self.db.fetchrow(query, conversation_id)
        return Conversation.from_record(record) if record else None

    async def get_by_session(
        self, session_id: str, limit: int = 100
    ) -> List[Conversation]:
        """Get conversations for a session."""
        query = """
            SELECT * FROM conversations
            WHERE session_id = $1
            ORDER BY created_at ASC
            LIMIT $2
        """
        records = await self.db.fetch(query, session_id, limit)
        return [Conversation.from_record(r) for r in records]

    async def get_recent(self, limit: int = 100) -> List[Conversation]:
        """Get most recent conversations."""
        query = """
            SELECT * FROM conversations
            ORDER BY created_at DESC
            LIMIT $1
        """
        records = await self.db.fetch(query, limit)
        return [Conversation.from_record(r) for r in records]

    async def get_by_confidence_range(
        self, min_conf: int, max_conf: int, limit: int = 100
    ) -> List[Conversation]:
        """Get conversations within a confidence range."""
        query = """
            SELECT * FROM conversations
            WHERE confidence >= $1 AND confidence <= $2
            ORDER BY created_at DESC
            LIMIT $3
        """
        records = await self.db.fetch(query, min_conf, max_conf, limit)
        return [Conversation.from_record(r) for r in records]

    async def count_by_session(self, session_id: str) -> int:
        """Count conversations in a session."""
        query = "SELECT COUNT(*) FROM conversations WHERE session_id = $1"
        return await self.db.fetchval(query, session_id)

    async def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily conversation statistics."""
        query = """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as conversations,
                ROUND(AVG(confidence), 1) as avg_confidence,
                ROUND(AVG(response_time_ms), 0) as avg_response_time_ms
            FROM conversations
            WHERE created_at > NOW() - INTERVAL '1 day' * $1
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """
        records = await self.db.fetch(query, days)
        return [dict(r) for r in records]
