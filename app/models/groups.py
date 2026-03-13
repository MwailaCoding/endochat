"""Pydantic models for support groups."""

from typing import Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    """Contact information for a group."""

    email: Optional[str] = None
    phone: Optional[str] = None
    social_media: Optional[dict] = None


class SupportGroupBase(BaseModel):
    """Base model for support group."""

    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    group_types: List[str] = Field(
        default=["in-person"],
        description="Types: in-person, online, hybrid",
    )
    country: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = Field(default=None, max_length=500)
    website: Optional[str] = Field(default=None, max_length=500)
    meeting_schedule: Optional[str] = Field(default=None, max_length=500)


class SupportGroupCreate(SupportGroupBase):
    """Request to create a support group."""

    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    contact_info: ContactInfo = Field(default_factory=ContactInfo)


class SupportGroupResponse(SupportGroupBase):
    """Response model for a support group."""

    id: UUID
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contact_info: dict = Field(default_factory=dict)
    member_count: int = 0
    verified: bool = False
    distance_km: Optional[float] = None
    created_at: datetime


class SupportGroupList(BaseModel):
    """Paginated list of support groups."""

    groups: List[SupportGroupResponse]
    total: int
    limit: int
    offset: int


class GroupSearchParams(BaseModel):
    """Parameters for searching groups."""

    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    location: Optional[str] = Field(default=None, max_length=200)
    radius_km: float = Field(default=50.0, ge=1, le=500)
    group_types: Optional[List[str]] = None
    verified_only: bool = False


class ReviewCreate(BaseModel):
    """Request to create a review."""

    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = Field(default=None, max_length=1000)


class ReviewResponse(BaseModel):
    """Response model for a review."""

    rating: int
    review_text: Optional[str] = None
    created_at: datetime


class JoinGroupResponse(BaseModel):
    """Response when joining a group."""

    success: bool
    is_new_join: bool
    message: str
