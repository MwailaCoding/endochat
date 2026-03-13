"""Pydantic models for anonymous story sharing."""

from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StoryCreate(BaseModel):
    """Request to create a story."""

    content: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Story content",
    )
    title: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional story title",
    )
    author_name: Optional[str] = Field(
        default="Anonymous Warrior",
        max_length=50,
        description="Display name",
    )
    location: Optional[str] = Field(
        default=None,
        max_length=100,
        description="General location (e.g., 'California, USA')",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        max_length=10,
        description="Tags for categorization",
    )


class StoryResponse(BaseModel):
    """Response model for a story."""

    id: UUID
    content: str
    title: Optional[str] = None
    author_name: str
    location: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    supports: int = 0
    views: int = 0
    featured: bool = False
    has_supported: bool = False
    created_at: datetime


class StoryList(BaseModel):
    """Paginated list of stories."""

    stories: List[StoryResponse]
    total: int
    limit: int
    offset: int
    filter_type: str


class SupportResponse(BaseModel):
    """Response when supporting a story."""

    success: bool
    is_new_support: bool
    total_supports: int


class EncouragementCreate(BaseModel):
    """Request to send encouragement."""

    message: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Encouragement message",
    )


class EncouragementResponse(BaseModel):
    """Response for an encouragement message."""

    id: UUID
    message: str
    created_at: datetime


class EncouragementList(BaseModel):
    """List of encouragement messages."""

    messages: List[EncouragementResponse]
    total: int
