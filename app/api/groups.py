"""API routes for support group finder."""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Header

from app.config import settings
from app.models.groups import (
    SupportGroupCreate,
    SupportGroupResponse,
    SupportGroupList,
    ReviewCreate,
    ReviewResponse,
    JoinGroupResponse,
)
from app.services.support_groups import SupportGroupFinder, SupportGroup
from app.core.dependencies import get_database_pool
from app.services.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/groups", tags=["groups"])


def get_group_finder(db_pool=Depends(get_database_pool)) -> SupportGroupFinder:
    """Get support group finder instance."""
    return SupportGroupFinder(db_pool)


def _group_to_response(group: SupportGroup) -> SupportGroupResponse:
    """Convert internal group model to response."""
    return SupportGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        group_types=group.group_types,
        country=group.country,
        city=group.city,
        address=group.address,
        latitude=group.latitude,
        longitude=group.longitude,
        contact_info=group.contact_info,
        website=group.website,
        meeting_schedule=group.meeting_schedule,
        member_count=group.member_count,
        verified=group.verified,
        distance_km=group.distance_km,
        created_at=group.created_at,
    )


@router.get("/search", response_model=SupportGroupList)
async def search_groups(
    lat: Optional[float] = Query(default=None, ge=-90, le=90, alias="lat"),
    lng: Optional[float] = Query(default=None, ge=-180, le=180, alias="lng"),
    location: Optional[str] = Query(default=None, max_length=200),
    radius: float = Query(default=50.0, ge=1, le=500, alias="radius"),
    group_types: Optional[str] = Query(default=None, description="Comma-separated types"),
    verified_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    finder: SupportGroupFinder = Depends(get_group_finder),
):
    """
    Search for support groups by location.

    Provide either lat/lng coordinates or a location string.
    The location string will be geocoded automatically.
    """
    if not settings.enable_groups:
        raise HTTPException(status_code=403, detail="Groups feature is disabled")

    types_list = None
    if group_types:
        types_list = [t.strip() for t in group_types.split(",")]

    groups, total = await finder.search_groups(
        latitude=lat,
        longitude=lng,
        location=location,
        radius_km=radius,
        group_types=types_list,
        verified_only=verified_only,
        limit=limit,
        offset=offset,
    )

    return SupportGroupList(
        groups=[_group_to_response(g) for g in groups],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{group_id}", response_model=SupportGroupResponse)
async def get_group(
    group_id: UUID,
    finder: SupportGroupFinder = Depends(get_group_finder),
):
    """Get a specific support group by ID."""
    if not settings.enable_groups:
        raise HTTPException(status_code=403, detail="Groups feature is disabled")

    group = await finder.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return _group_to_response(group)


@router.post("", response_model=SupportGroupResponse, status_code=201)
async def create_group(
    request: SupportGroupCreate,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    finder: SupportGroupFinder = Depends(get_group_finder),
):
    """
    Submit a new support group.

    New groups are unverified by default and require admin approval.
    """
    if not settings.enable_groups:
        raise HTTPException(status_code=403, detail="Groups feature is disabled")

    group_id = await finder.add_group(
        name=request.name,
        description=request.description,
        group_types=request.group_types,
        country=request.country,
        city=request.city,
        address=request.address,
        latitude=request.latitude,
        longitude=request.longitude,
        contact_info=request.contact_info.model_dump(),
        website=request.website,
        meeting_schedule=request.meeting_schedule,
        submitted_by_session=x_session_id,
    )

    group = await finder.get_group(group_id)
    if not group:
        raise HTTPException(status_code=500, detail="Failed to create group")

    logger.info("Support group created", group_id=str(group_id), name=request.name)

    return _group_to_response(group)


@router.post("/{group_id}/join", response_model=JoinGroupResponse)
async def join_group(
    group_id: UUID,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    finder: SupportGroupFinder = Depends(get_group_finder),
):
    """
    Track a user joining a group.

    This tracks interest/engagement but doesn't actually join
    an external group - just records the intent.
    """
    if not settings.enable_groups:
        raise HTTPException(status_code=403, detail="Groups feature is disabled")

    group = await finder.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    is_new = await finder.join_group(group_id, x_session_id)

    if is_new:
        return JoinGroupResponse(
            success=True,
            is_new_join=True,
            message="Successfully tracked your interest in this group",
        )
    else:
        return JoinGroupResponse(
            success=True,
            is_new_join=False,
            message="You have already shown interest in this group",
        )


@router.post("/{group_id}/review", response_model=ReviewResponse, status_code=201)
async def add_review(
    group_id: UUID,
    request: ReviewCreate,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    finder: SupportGroupFinder = Depends(get_group_finder),
):
    """Add or update a review for a support group."""
    if not settings.enable_groups:
        raise HTTPException(status_code=403, detail="Groups feature is disabled")

    group = await finder.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await finder.add_review(
        group_id=group_id,
        session_id=x_session_id,
        rating=request.rating,
        review_text=request.review_text,
    )

    from datetime import datetime

    return ReviewResponse(
        rating=request.rating,
        review_text=request.review_text,
        created_at=datetime.utcnow(),
    )


@router.get("/{group_id}/reviews", response_model=List[ReviewResponse])
async def get_reviews(
    group_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    finder: SupportGroupFinder = Depends(get_group_finder),
):
    """Get reviews for a support group."""
    if not settings.enable_groups:
        raise HTTPException(status_code=403, detail="Groups feature is disabled")

    group = await finder.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    reviews = await finder.get_group_reviews(group_id, limit, offset)

    return [
        ReviewResponse(
            rating=r["rating"],
            review_text=r["review_text"],
            created_at=r["created_at"],
        )
        for r in reviews
    ]
