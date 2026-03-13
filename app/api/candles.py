"""API routes for virtual candle lighting ceremony."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Header

from app.config import settings
from app.models.candles import (
    CandleLightRequest,
    CandleResponse,
    CandleCountResponse,
    CandleListResponse,
    CandleMessageCreate,
    CandleMessageResponse,
    CandleStatsResponse,
    LocationCountResponse,
    CanLightResponse,
)
from app.services.candle_ceremony import CandleCeremonyService, CandleCeremonyError
from app.core.dependencies import get_database_pool, get_cache_service
from app.services.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/candles", tags=["candles"])


def get_candle_service(
    db_pool=Depends(get_database_pool),
    cache=Depends(get_cache_service),
) -> CandleCeremonyService:
    """Get candle ceremony service instance."""
    return CandleCeremonyService(db_pool, cache)


@router.get("/count", response_model=CandleCountResponse)
async def get_candle_count(
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """
    Get the current candle count and progress.

    Returns total candles, today's count, and progress towards target.
    """
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    count_data = await service.get_candle_count()
    return CandleCountResponse(**count_data)


@router.get("/can-light", response_model=CanLightResponse)
async def can_light_today(
    x_session_id: str = Header(..., alias="X-Session-ID"),
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """Check if the current session can light a candle today."""
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    can_light = await service.can_light_today(x_session_id)

    if can_light:
        return CanLightResponse(
            can_light=True,
            message="You can light a candle today!",
        )
    else:
        return CanLightResponse(
            can_light=False,
            message="You've already lit your candle today. Come back tomorrow!",
        )


@router.post("/light", response_model=CandleResponse, status_code=201)
async def light_candle(
    request: CandleLightRequest,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """
    Light a virtual candle.

    Each user can light one candle per day.
    Optionally include a message of hope or dedication.
    """
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    try:
        candle_id = await service.light_candle(
            session_id=x_session_id,
            message=request.message,
            dedication=request.dedication,
            location=request.location,
            color=request.color,
        )
    except CandleCeremonyError as e:
        raise HTTPException(status_code=429, detail=e.detail or e.message)

    candle = await service.get_candle(candle_id)
    if not candle:
        raise HTTPException(status_code=500, detail="Failed to light candle")

    logger.info("Candle lit", candle_id=str(candle_id))

    return CandleResponse(
        id=candle.id,
        message=candle.message,
        dedication=candle.dedication,
        location=candle.location,
        color=candle.color,
        lit_at=candle.lit_at,
    )


@router.get("/messages", response_model=CandleListResponse)
async def get_recent_candles(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """
    Get recently lit candles with messages.

    Returns candles that have attached messages.
    """
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    candles = await service.get_recent_candles(limit=limit, offset=offset)

    return CandleListResponse(
        candles=[
            CandleResponse(
                id=c.id,
                message=c.message,
                dedication=c.dedication,
                location=c.location,
                color=c.color,
                lit_at=c.lit_at,
            )
            for c in candles
        ],
        total=len(candles),
    )


@router.get("/mine", response_model=CandleListResponse)
async def get_my_candles(
    limit: int = Query(default=20, ge=1, le=100),
    x_session_id: str = Header(..., alias="X-Session-ID"),
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """Get candles lit by the current session."""
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    candles = await service.get_my_candles(session_id=x_session_id, limit=limit)

    return CandleListResponse(
        candles=[
            CandleResponse(
                id=c.id,
                message=c.message,
                dedication=c.dedication,
                location=c.location,
                color=c.color,
                lit_at=c.lit_at,
            )
            for c in candles
        ],
        total=len(candles),
    )


@router.get("/stats", response_model=CandleStatsResponse)
async def get_stats(
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """Get ceremony statistics."""
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    stats = await service.get_stats()
    return CandleStatsResponse(**stats)


@router.get("/locations", response_model=List[LocationCountResponse])
async def get_locations(
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """Get candle counts by location for visualization."""
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    locations = await service.get_locations()

    return [
        LocationCountResponse(location=loc["location"], count=loc["count"])
        for loc in locations
    ]


@router.get("/{candle_id}", response_model=CandleResponse)
async def get_candle(
    candle_id: UUID,
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """Get a specific candle by ID."""
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    candle = await service.get_candle(candle_id)
    if not candle:
        raise HTTPException(status_code=404, detail="Candle not found")

    return CandleResponse(
        id=candle.id,
        message=candle.message,
        dedication=candle.dedication,
        location=candle.location,
        color=candle.color,
        lit_at=candle.lit_at,
    )


@router.post("/{candle_id}/message", response_model=CandleMessageResponse, status_code=201)
async def add_message(
    candle_id: UUID,
    request: CandleMessageCreate,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """Add a supportive message to someone's candle."""
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    candle = await service.get_candle(candle_id)
    if not candle:
        raise HTTPException(status_code=404, detail="Candle not found")

    message_id = await service.add_message_to_candle(
        candle_id=candle_id,
        message=request.message,
        from_session=x_session_id,
    )

    from datetime import datetime

    return CandleMessageResponse(
        id=message_id,
        message=request.message,
        created_at=datetime.utcnow(),
    )


@router.get("/{candle_id}/messages", response_model=List[CandleMessageResponse])
async def get_candle_messages(
    candle_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    service: CandleCeremonyService = Depends(get_candle_service),
):
    """Get messages for a specific candle."""
    if not settings.enable_candles:
        raise HTTPException(status_code=403, detail="Candles feature is disabled")

    messages = await service.get_candle_messages(candle_id, limit=limit)

    return [
        CandleMessageResponse(
            id=m.id,
            message=m.message,
            created_at=m.created_at,
        )
        for m in messages
    ]
