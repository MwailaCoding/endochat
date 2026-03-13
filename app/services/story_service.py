"""Story sharing service for anonymous community stories."""

import re
from typing import Optional, List, Literal
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass

from app.services.utils.logging import get_logger
from app.core.exceptions import EndoChatException

logger = get_logger(__name__)


class StoryServiceError(EndoChatException):
    """Story service error."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message=message, detail=detail, error_code="STORY_ERROR")


@dataclass
class Story:
    """Story data model."""

    id: UUID
    content: str
    title: Optional[str]
    author_name: str
    location: Optional[str]
    tags: List[str]
    supports: int
    views: int
    featured: bool
    created_at: datetime
    has_supported: bool = False


@dataclass
class StoryMessage:
    """Encouragement message data model."""

    id: UUID
    story_id: UUID
    message: str
    created_at: datetime


BLOCKED_WORDS = [
    "spam",
    "advertisement",
    "buy now",
    "click here",
    "http://",
    "https://",
    "www.",
]

SENSITIVE_INFO_PATTERNS = [
    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    r"\b\d{3}[-]?\d{2}[-]?\d{4}\b",
]


class StoryService:
    """Service for anonymous story sharing."""

    def __init__(self, db_pool):
        """Initialize with database pool."""
        self.db_pool = db_pool

    def _moderate_content(self, content: str) -> tuple[bool, Optional[str]]:
        """
        Basic content moderation.

        Returns (is_safe, reason) tuple.
        """
        content_lower = content.lower()

        for word in BLOCKED_WORDS:
            if word in content_lower:
                return False, f"Content contains blocked term: {word}"

        for pattern in SENSITIVE_INFO_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False, "Content appears to contain sensitive personal information"

        if len(content) < 20:
            return False, "Content is too short (minimum 20 characters)"

        if len(content) > 5000:
            return False, "Content is too long (maximum 5000 characters)"

        return True, None

    async def create_story(
        self,
        content: str,
        session_id: str,
        title: Optional[str] = None,
        author_name: Optional[str] = None,
        location: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> UUID:
        """
        Create a new story.

        Args:
            content: Story content
            session_id: Creator's session ID
            title: Optional title
            author_name: Display name (default: Anonymous Warrior)
            location: Optional location
            tags: Optional tags

        Returns:
            Created story ID
        """
        is_safe, reason = self._moderate_content(content)
        if not is_safe:
            raise StoryServiceError(
                message="Content moderation failed",
                detail=reason,
            )

        if title:
            is_safe, reason = self._moderate_content(title)
            if not is_safe:
                raise StoryServiceError(
                    message="Title moderation failed",
                    detail=reason,
                )

        clean_tags = []
        if tags:
            clean_tags = [t.strip().lower()[:50] for t in tags[:10]]

        query = """
            INSERT INTO stories (
                content, title, author_name, location, tags,
                session_id, moderated
            )
            VALUES ($1, $2, $3, $4, $5, $6, TRUE)
            RETURNING id
        """
        async with self.db_pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                content,
                title,
                author_name or "Anonymous Warrior",
                location,
                clean_tags,
                session_id,
            )

        logger.info("Story created", story_id=str(row["id"]))
        return row["id"]

    async def get_stories(
        self,
        filter_type: Literal["recent", "popular", "featured"] = "recent",
        tags: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0,
        viewer_session_id: Optional[str] = None,
    ) -> tuple[List[Story], int]:
        """
        Get stories with filtering and pagination.

        Args:
            filter_type: Sort order - recent, popular, or featured
            tags: Filter by tags
            limit: Maximum results
            offset: Pagination offset
            viewer_session_id: Session ID for tracking support status

        Returns:
            Tuple of (stories list, total count)
        """
        base_query = """
            WITH filtered_stories AS (
                SELECT 
                    s.id, s.content, s.title, s.author_name, s.location,
                    s.tags, s.supports, s.views, s.featured, s.created_at,
                    EXISTS(
                        SELECT 1 FROM story_supports ss
                        WHERE ss.story_id = s.id AND ss.session_id = $1
                    ) as has_supported
                FROM stories s
                WHERE s.moderated = TRUE AND s.hidden = FALSE
        """
        params = [viewer_session_id or ""]
        param_idx = 2

        if tags:
            base_query += f" AND s.tags && ${param_idx}::text[]"
            params.append(tags)
            param_idx += 1

        if filter_type == "featured":
            base_query += " AND s.featured = TRUE"

        base_query += """
            )
            SELECT *, COUNT(*) OVER() as total_count
            FROM filtered_stories
        """

        if filter_type == "popular":
            base_query += " ORDER BY supports DESC, created_at DESC"
        elif filter_type == "featured":
            base_query += " ORDER BY created_at DESC"
        else:
            base_query += " ORDER BY created_at DESC"

        base_query += f" LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(base_query, *params)

        if not rows:
            return [], 0

        total = rows[0]["total_count"] if rows else 0
        stories = [self._row_to_story(row) for row in rows]

        return stories, total

    async def get_story(
        self,
        story_id: UUID,
        viewer_session_id: Optional[str] = None,
        track_view: bool = True,
    ) -> Optional[Story]:
        """Get a single story by ID."""
        query = """
            SELECT 
                s.id, s.content, s.title, s.author_name, s.location,
                s.tags, s.supports, s.views, s.featured, s.created_at,
                EXISTS(
                    SELECT 1 FROM story_supports ss
                    WHERE ss.story_id = s.id AND ss.session_id = $2
                ) as has_supported
            FROM stories s
            WHERE s.id = $1 AND s.moderated = TRUE AND s.hidden = FALSE
        """
        async with self.db_pool.pool.acquire() as conn:
            row = await conn.fetchrow(query, story_id, viewer_session_id or "")

        if not row:
            return None

        if track_view:
            await self._increment_views(story_id)

        return self._row_to_story(row)

    async def add_support(self, story_id: UUID, session_id: str) -> bool:
        """
        Add a support reaction to a story.

        Returns True if this is a new support, False if already supported.
        """
        query = """
            INSERT INTO story_supports (story_id, session_id)
            VALUES ($1, $2)
            ON CONFLICT (story_id, session_id) DO NOTHING
            RETURNING story_id
        """
        async with self.db_pool.pool.acquire() as conn:
            result = await conn.fetchrow(query, story_id, session_id)

        if result:
            await self._increment_supports(story_id)
            logger.info("Support added", story_id=str(story_id))
            return True
        return False

    async def remove_support(self, story_id: UUID, session_id: str) -> bool:
        """Remove a support reaction from a story."""
        query = """
            DELETE FROM story_supports
            WHERE story_id = $1 AND session_id = $2
            RETURNING story_id
        """
        async with self.db_pool.pool.acquire() as conn:
            result = await conn.fetchrow(query, story_id, session_id)

        if result:
            await self._decrement_supports(story_id)
            return True
        return False

    async def send_encouragement(
        self,
        story_id: UUID,
        message: str,
        from_session: Optional[str] = None,
    ) -> UUID:
        """
        Send an encouragement message to a story author.

        Args:
            story_id: Target story
            message: Encouragement message
            from_session: Sender's session (optional, for de-anonymized replies)

        Returns:
            Message ID
        """
        is_safe, reason = self._moderate_content(message)
        if not is_safe:
            raise StoryServiceError(
                message="Message moderation failed",
                detail=reason,
            )

        query = """
            INSERT INTO story_messages (story_id, from_session, message)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        async with self.db_pool.pool.acquire() as conn:
            row = await conn.fetchrow(query, story_id, from_session, message)

        logger.info("Encouragement sent", story_id=str(story_id), message_id=str(row["id"]))
        return row["id"]

    async def get_messages_for_story(
        self,
        story_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[StoryMessage]:
        """Get encouragement messages for a story."""
        query = """
            SELECT id, story_id, message, created_at
            FROM story_messages
            WHERE story_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, story_id, limit, offset)

        return [
            StoryMessage(
                id=row["id"],
                story_id=row["story_id"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def get_my_stories(
        self,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[Story], int]:
        """Get stories created by a session."""
        query = """
            WITH my_stories AS (
                SELECT 
                    id, content, title, author_name, location,
                    tags, supports, views, featured, created_at,
                    FALSE as has_supported
                FROM stories
                WHERE session_id = $1 AND hidden = FALSE
            )
            SELECT *, COUNT(*) OVER() as total_count
            FROM my_stories
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, session_id, limit, offset)

        if not rows:
            return [], 0

        total = rows[0]["total_count"] if rows else 0
        stories = [self._row_to_story(row) for row in rows]

        return stories, total

    async def hide_story(self, story_id: UUID, session_id: str) -> bool:
        """Hide a story (soft delete). Only owner can hide."""
        query = """
            UPDATE stories
            SET hidden = TRUE
            WHERE id = $1 AND session_id = $2
            RETURNING id
        """
        async with self.db_pool.pool.acquire() as conn:
            result = await conn.fetchrow(query, story_id, session_id)
        return result is not None

    async def _increment_views(self, story_id: UUID):
        """Increment view count."""
        query = "UPDATE stories SET views = views + 1 WHERE id = $1"
        async with self.db_pool.pool.acquire() as conn:
            await conn.execute(query, story_id)

    async def _increment_supports(self, story_id: UUID):
        """Increment support count."""
        query = "UPDATE stories SET supports = supports + 1 WHERE id = $1"
        async with self.db_pool.pool.acquire() as conn:
            await conn.execute(query, story_id)

    async def _decrement_supports(self, story_id: UUID):
        """Decrement support count."""
        query = "UPDATE stories SET supports = GREATEST(supports - 1, 0) WHERE id = $1"
        async with self.db_pool.pool.acquire() as conn:
            await conn.execute(query, story_id)

    def _row_to_story(self, row) -> Story:
        """Convert database row to Story object."""
        return Story(
            id=row["id"],
            content=row["content"],
            title=row["title"],
            author_name=row["author_name"],
            location=row["location"],
            tags=row["tags"] or [],
            supports=row["supports"] or 0,
            views=row["views"] or 0,
            featured=row["featured"],
            created_at=row["created_at"],
            has_supported=row["has_supported"],
        )
