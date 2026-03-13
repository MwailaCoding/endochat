"""Repository for popular questions data access."""

from typing import Optional, List
from uuid import UUID

from app.services.database.postgres import DatabasePool
from app.services.database.models import PopularQuestion
from app.services.utils.text import normalize_question
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class PopularRepository:
    """Data access layer for popular questions."""

    def __init__(self, db: DatabasePool):
        self.db = db

    async def increment_count(
        self,
        question: str,
        category: Optional[str] = None,
    ) -> PopularQuestion:
        """Increment count for a question, creating if not exists."""
        normalized = normalize_question(question)

        query = """
            INSERT INTO popular_questions (
                question, normalized_question, category, ask_count, last_asked
            ) VALUES ($1, $2, $3, 1, NOW())
            ON CONFLICT (normalized_question)
            DO UPDATE SET
                ask_count = popular_questions.ask_count + 1,
                last_asked = NOW(),
                category = COALESCE($3, popular_questions.category)
            RETURNING *
        """
        record = await self.db.fetchrow(query, question, normalized, category)
        return PopularQuestion.from_record(record)

    async def get_top(
        self,
        limit: int = 10,
        category: Optional[str] = None,
    ) -> List[PopularQuestion]:
        """Get top popular questions."""
        if category:
            query = """
                SELECT * FROM popular_questions
                WHERE category = $1
                ORDER BY ask_count DESC
                LIMIT $2
            """
            records = await self.db.fetch(query, category, limit)
        else:
            query = """
                SELECT * FROM popular_questions
                ORDER BY ask_count DESC
                LIMIT $1
            """
            records = await self.db.fetch(query, limit)

        return [PopularQuestion.from_record(r) for r in records]

    async def get_trending(
        self,
        limit: int = 5,
        within_hours: int = 24,
    ) -> List[PopularQuestion]:
        """Get trending questions from recent period."""
        query = """
            SELECT * FROM popular_questions
            WHERE last_asked > NOW() - INTERVAL '1 hour' * $1
            ORDER BY ask_count DESC
            LIMIT $2
        """
        records = await self.db.fetch(query, within_hours, limit)
        return [PopularQuestion.from_record(r) for r in records]

    async def get_by_category(
        self,
        category: str,
        limit: int = 10,
    ) -> List[PopularQuestion]:
        """Get questions by category."""
        query = """
            SELECT * FROM popular_questions
            WHERE category = $1
            ORDER BY ask_count DESC
            LIMIT $2
        """
        records = await self.db.fetch(query, category, limit)
        return [PopularQuestion.from_record(r) for r in records]

    async def search(
        self,
        search_term: str,
        limit: int = 10,
    ) -> List[PopularQuestion]:
        """Search questions by text."""
        query = """
            SELECT * FROM popular_questions
            WHERE normalized_question ILIKE $1
            ORDER BY ask_count DESC
            LIMIT $2
        """
        records = await self.db.fetch(query, f"%{search_term.lower()}%", limit)
        return [PopularQuestion.from_record(r) for r in records]

    async def get_categories(self) -> List[dict]:
        """Get all categories with question counts."""
        query = """
            SELECT category, COUNT(*) as count, SUM(ask_count) as total_asks
            FROM popular_questions
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY total_asks DESC
        """
        records = await self.db.fetch(query)
        return [dict(r) for r in records]

    async def total_count(self) -> int:
        """Get total number of unique questions."""
        query = "SELECT COUNT(*) FROM popular_questions"
        return await self.db.fetchval(query)
