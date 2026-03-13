"""SQLAlchemy-style models matching the database schema."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


@dataclass
class Conversation:
    """Represents a conversation record."""

    id: UUID
    session_id: str
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    confidence: Optional[int]
    response_time_ms: Optional[int]
    created_at: datetime

    @classmethod
    def from_record(cls, record: dict) -> "Conversation":
        """Create from database record."""
        return cls(
            id=record["id"],
            session_id=record["session_id"],
            question=record["question"],
            answer=record["answer"],
            sources=record["sources"] if record["sources"] else [],
            confidence=record["confidence"],
            response_time_ms=record["response_time_ms"],
            created_at=record["created_at"],
        )


@dataclass
class Feedback:
    """Represents a feedback record."""

    id: UUID
    conversation_id: UUID
    message_id: Optional[str]
    rating: int
    reason: Optional[str]
    comment: Optional[str]
    created_at: datetime

    @classmethod
    def from_record(cls, record: dict) -> "Feedback":
        """Create from database record."""
        return cls(
            id=record["id"],
            conversation_id=record["conversation_id"],
            message_id=record["message_id"],
            rating=record["rating"],
            reason=record["reason"],
            comment=record["comment"],
            created_at=record["created_at"],
        )


@dataclass
class PopularQuestion:
    """Represents a popular question record."""

    id: UUID
    question: str
    normalized_question: str
    category: Optional[str]
    ask_count: int
    last_asked: datetime
    created_at: datetime

    @classmethod
    def from_record(cls, record: dict) -> "PopularQuestion":
        """Create from database record."""
        return cls(
            id=record["id"],
            question=record["question"],
            normalized_question=record["normalized_question"],
            category=record["category"],
            ask_count=record["ask_count"],
            last_asked=record["last_asked"],
            created_at=record["created_at"],
        )


@dataclass
class ApiCache:
    """Represents an API cache record."""

    id: UUID
    api_name: str
    endpoint: str
    query_hash: str
    question: str
    response: Dict[str, Any]
    created_at: datetime
    expires_at: datetime

    @classmethod
    def from_record(cls, record: dict) -> "ApiCache":
        """Create from database record."""
        return cls(
            id=record["id"],
            api_name=record["api_name"],
            endpoint=record["endpoint"],
            query_hash=record["query_hash"],
            question=record["question"],
            response=record["response"],
            created_at=record["created_at"],
            expires_at=record["expires_at"],
        )

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now(self.expires_at.tzinfo) > self.expires_at


@dataclass
class SourceDocument:
    """Represents a source document record."""

    id: UUID
    title: str
    source_organization: str
    document_type: Optional[str]
    url: Optional[str]
    last_updated: Optional[datetime]
    topics: Optional[List[str]]
    created_at: datetime

    @classmethod
    def from_record(cls, record: dict) -> "SourceDocument":
        """Create from database record."""
        return cls(
            id=record["id"],
            title=record["title"],
            source_organization=record["source_organization"],
            document_type=record["document_type"],
            url=record["url"],
            last_updated=record["last_updated"],
            topics=record["topics"],
            created_at=record["created_at"],
        )
