"""Pydantic models for shareable cards."""

from typing import Optional, Literal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ShareCardRequest(BaseModel):
    """Request to generate a shareable card."""

    card_type: Literal["fact", "stat", "candle"] = Field(
        default="fact",
        description="Type of card to generate",
    )
    title: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Card title (for fact cards)",
    )
    content: str = Field(
        ...,
        max_length=500,
        description="Main content or fact",
    )
    stat_value: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Statistic value (for stat cards)",
    )
    stat_label: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Statistic label (for stat cards)",
    )
    source: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Source citation",
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="Associated conversation ID",
    )


class ShareCardResponse(BaseModel):
    """Response with generated card details."""

    id: UUID
    card_type: str
    image_url: str
    qr_code_url: Optional[str] = None
    tracking_code: str
    share_url: str
    created_at: datetime


class ShareStats(BaseModel):
    """Statistics for a shared card."""

    card_id: UUID
    tracking_code: str
    clicks: int = 0
    platform_shares: dict = Field(default_factory=dict)
    created_at: datetime


class TrackClickRequest(BaseModel):
    """Request to track a card click."""

    platform: Optional[str] = Field(
        default=None,
        description="Platform where the link was shared",
    )
    referrer: Optional[str] = Field(
        default=None,
        description="Referrer URL",
    )
