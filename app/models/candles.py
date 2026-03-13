"""Pydantic models for virtual candle ceremony."""

from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


CANDLE_COLORS = Literal["yellow", "gold", "amber", "orange", "white", "cream"]


class CandleLightRequest(BaseModel):
    """Request to light a candle."""

    message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Message of hope or support",
    )
    dedication: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Who the candle is dedicated to",
    )
    location: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Your location (city, country)",
    )
    color: CANDLE_COLORS = Field(
        default="yellow",
        description="Candle color",
    )


class CandleResponse(BaseModel):
    """Response model for a candle."""

    id: UUID
    message: Optional[str] = None
    dedication: Optional[str] = None
    location: Optional[str] = None
    color: str
    lit_at: datetime


class CandleCountResponse(BaseModel):
    """Response for candle count."""

    total: int
    today: int
    target: int
    progress_percent: float
    remaining: int


class CandleListResponse(BaseModel):
    """Paginated list of candles."""

    candles: List[CandleResponse]
    total: int


class CandleMessageCreate(BaseModel):
    """Request to add a message to a candle."""

    message: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Supportive message",
    )


class CandleMessageResponse(BaseModel):
    """Response for a candle message."""

    id: UUID
    message: str
    created_at: datetime


class CandleStatsResponse(BaseModel):
    """Ceremony statistics."""

    total_candles: int
    unique_participants: int
    candles_with_messages: int
    unique_locations: int
    target: int
    progress_percent: float


class LocationCountResponse(BaseModel):
    """Location with candle count."""

    location: str
    count: int


class CanLightResponse(BaseModel):
    """Response for checking if can light today."""

    can_light: bool
    message: str
