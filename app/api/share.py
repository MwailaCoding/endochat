"""API routes for shareable answer cards."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.config import settings
from app.models.share import (
    ShareCardRequest,
    ShareCardResponse,
    ShareStats,
    TrackClickRequest,
)
from app.services.card_generator import CardGenerator
from app.services.storage.cloudinary_client import CloudinaryClient
from app.core.dependencies import get_database_pool
from app.services.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/share", tags=["share"])

_card_generator: Optional[CardGenerator] = None


def get_card_generator() -> CardGenerator:
    """Get or create card generator instance."""
    global _card_generator
    if _card_generator is None:
        _card_generator = CardGenerator()
    return _card_generator


@router.post("/generate-card", response_model=ShareCardResponse)
async def generate_card(
    request: ShareCardRequest,
    req: Request,
    db_pool=Depends(get_database_pool),
):
    """
    Generate a shareable card image.

    Creates an image card with the provided content, uploads it to Cloudinary,
    and returns the share URL with tracking.
    """
    if not settings.enable_sharing:
        raise HTTPException(status_code=403, detail="Sharing feature is disabled")

    generator = get_card_generator()

    base_url = str(req.base_url).rstrip("/")

    try:
        if request.card_type == "fact":
            result = await generator.generate_fact_card(
                title=request.title or "Did You Know?",
                content=request.content,
                source=request.source,
                share_url=f"{base_url}/api/share/redirect/PLACEHOLDER",
            )
        elif request.card_type == "stat":
            if not request.stat_value or not request.stat_label:
                raise HTTPException(
                    status_code=400,
                    detail="stat_value and stat_label required for stat cards",
                )
            result = await generator.generate_stat_card(
                stat_value=request.stat_value,
                stat_label=request.stat_label,
                description=request.content,
                source=request.source,
                share_url=f"{base_url}/api/share/redirect/PLACEHOLDER",
            )
        elif request.card_type == "candle":
            count = await _get_candle_count(db_pool)
            result = await generator.generate_candle_card(
                candle_count=count,
                message=request.content,
                share_url=f"{base_url}/api/share/redirect/PLACEHOLDER",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown card type: {request.card_type}")

        card_id = await _save_card(
            db_pool=db_pool,
            conversation_id=request.conversation_id,
            card_type=result["card_type"],
            title=request.title,
            content=request.content,
            image_url=result["image_url"],
            qr_code_url=result.get("qr_code_url"),
            tracking_code=result["tracking_code"],
        )

        share_url = f"{base_url}/api/share/{result['tracking_code']}"

        from datetime import datetime

        return ShareCardResponse(
            id=card_id,
            card_type=result["card_type"],
            image_url=result["image_url"],
            qr_code_url=result.get("qr_code_url"),
            tracking_code=result["tracking_code"],
            share_url=share_url,
            created_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate card", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate card")


@router.get("/{tracking_code}")
async def redirect_to_content(
    tracking_code: str,
    platform: Optional[str] = Query(default=None),
    db_pool=Depends(get_database_pool),
):
    """
    Redirect handler for shared cards.

    Tracks the click and redirects to the main site.
    """
    card = await _get_card_by_tracking_code(db_pool, tracking_code)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    await _increment_clicks(db_pool, tracking_code, platform)

    return RedirectResponse(
        url=f"https://endochat.org?ref={tracking_code}",
        status_code=302,
    )


@router.get("/stats/{card_id}", response_model=ShareStats)
async def get_card_stats(
    card_id: UUID,
    db_pool=Depends(get_database_pool),
):
    """Get statistics for a shared card."""
    query = """
        SELECT id, tracking_code, clicks, platform_shares, created_at
        FROM shared_cards
        WHERE id = $1
    """
    async with db_pool.pool.acquire() as conn:
        row = await conn.fetchrow(query, card_id)

    if not row:
        raise HTTPException(status_code=404, detail="Card not found")

    return ShareStats(
        card_id=row["id"],
        tracking_code=row["tracking_code"],
        clicks=row["clicks"] or 0,
        platform_shares=row["platform_shares"] or {},
        created_at=row["created_at"],
    )


@router.post("/{tracking_code}/track")
async def track_click(
    tracking_code: str,
    request: TrackClickRequest,
    db_pool=Depends(get_database_pool),
):
    """Manually track a card click with additional metadata."""
    card = await _get_card_by_tracking_code(db_pool, tracking_code)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    await _increment_clicks(db_pool, tracking_code, request.platform)

    return {"success": True, "clicks": card["clicks"] + 1}


async def _save_card(
    db_pool,
    conversation_id: Optional[UUID],
    card_type: str,
    title: Optional[str],
    content: str,
    image_url: str,
    qr_code_url: Optional[str],
    tracking_code: str,
) -> UUID:
    """Save a generated card to the database."""
    query = """
        INSERT INTO shared_cards (
            conversation_id, card_type, title, content,
            image_url, qr_code_url, tracking_code
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
    """
    async with db_pool.pool.acquire() as conn:
        row = await conn.fetchrow(
            query,
            conversation_id,
            card_type,
            title,
            content,
            image_url,
            qr_code_url,
            tracking_code,
        )
    return row["id"]


async def _get_card_by_tracking_code(db_pool, tracking_code: str) -> Optional[dict]:
    """Get a card by its tracking code."""
    query = """
        SELECT id, card_type, image_url, tracking_code, clicks, created_at
        FROM shared_cards
        WHERE tracking_code = $1
    """
    async with db_pool.pool.acquire() as conn:
        row = await conn.fetchrow(query, tracking_code)
    return dict(row) if row else None


async def _increment_clicks(db_pool, tracking_code: str, platform: Optional[str]):
    """Increment click count and optionally track platform."""
    if platform:
        query = """
            UPDATE shared_cards
            SET clicks = clicks + 1,
                platform_shares = jsonb_set(
                    COALESCE(platform_shares, '{}'),
                    ARRAY[$2],
                    (COALESCE(platform_shares->$2, '0')::int + 1)::text::jsonb
                )
            WHERE tracking_code = $1
        """
        async with db_pool.pool.acquire() as conn:
            await conn.execute(query, tracking_code, platform)
    else:
        query = """
            UPDATE shared_cards
            SET clicks = clicks + 1
            WHERE tracking_code = $1
        """
        async with db_pool.pool.acquire() as conn:
            await conn.execute(query, tracking_code)


async def _get_candle_count(db_pool) -> int:
    """Get total candle count for candle cards."""
    query = "SELECT COUNT(*) FROM candles"
    try:
        async with db_pool.pool.acquire() as conn:
            result = await conn.fetchval(query)
        return result or 0
    except Exception:
        return 0
