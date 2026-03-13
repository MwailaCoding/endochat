"""API routes for anonymous story sharing."""

from typing import Optional, List, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Header

from app.config import settings
from app.models.stories import (
    StoryCreate,
    StoryResponse,
    StoryList,
    SupportResponse,
    EncouragementCreate,
    EncouragementResponse,
    EncouragementList,
)
from app.services.story_service import StoryService, Story, StoryServiceError
from app.core.dependencies import get_database_pool
from app.services.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/stories", tags=["stories"])


def get_story_service(db_pool=Depends(get_database_pool)) -> StoryService:
    """Get story service instance."""
    return StoryService(db_pool)


def _story_to_response(story: Story) -> StoryResponse:
    """Convert internal story model to response."""
    return StoryResponse(
        id=story.id,
        content=story.content,
        title=story.title,
        author_name=story.author_name,
        location=story.location,
        tags=story.tags,
        supports=story.supports,
        views=story.views,
        featured=story.featured,
        has_supported=story.has_supported,
        created_at=story.created_at,
    )


@router.get("", response_model=StoryList)
async def get_stories(
    filter: Literal["recent", "popular", "featured"] = Query(
        default="recent",
        description="Filter type",
    ),
    tags: Optional[str] = Query(
        default=None,
        description="Comma-separated tags to filter by",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
    service: StoryService = Depends(get_story_service),
):
    """
    Get stories with filtering.

    Filter types:
    - recent: Most recently posted
    - popular: Most supported
    - featured: Curated featured stories
    """
    if not settings.enable_stories:
        raise HTTPException(status_code=403, detail="Stories feature is disabled")

    tags_list = None
    if tags:
        tags_list = [t.strip().lower() for t in tags.split(",")]

    stories, total = await service.get_stories(
        filter_type=filter,
        tags=tags_list,
        limit=limit,
        offset=offset,
        viewer_session_id=x_session_id,
    )

    return StoryList(
        stories=[_story_to_response(s) for s in stories],
        total=total,
        limit=limit,
        offset=offset,
        filter_type=filter,
    )


@router.get("/mine", response_model=StoryList)
async def get_my_stories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    x_session_id: str = Header(..., alias="X-Session-ID"),
    service: StoryService = Depends(get_story_service),
):
    """Get stories created by the current session."""
    if not settings.enable_stories:
        raise HTTPException(status_code=403, detail="Stories feature is disabled")

    stories, total = await service.get_my_stories(
        session_id=x_session_id,
        limit=limit,
        offset=offset,
    )

    return StoryList(
        stories=[_story_to_response(s) for s in stories],
        total=total,
        limit=limit,
        offset=offset,
        filter_type="mine",
    )


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: UUID,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
    service: StoryService = Depends(get_story_service),
):
    """Get a single story by ID."""
    if not settings.enable_stories:
        raise HTTPException(status_code=403, detail="Stories feature is disabled")

    story = await service.get_story(
        story_id=story_id,
        viewer_session_id=x_session_id,
        track_view=True,
    )

    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    return _story_to_response(story)


@router.post("", response_model=StoryResponse, status_code=201)
async def create_story(
    request: StoryCreate,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    service: StoryService = Depends(get_story_service),
):
    """
    Create a new story.

    Stories are automatically moderated for basic content safety.
    """
    if not settings.enable_stories:
        raise HTTPException(status_code=403, detail="Stories feature is disabled")

    try:
        story_id = await service.create_story(
            content=request.content,
            session_id=x_session_id,
            title=request.title,
            author_name=request.author_name,
            location=request.location,
            tags=request.tags,
        )
    except StoryServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)

    story = await service.get_story(story_id, x_session_id, track_view=False)
    if not story:
        raise HTTPException(status_code=500, detail="Failed to create story")

    logger.info("Story created", story_id=str(story_id))
    return _story_to_response(story)


@router.post("/{story_id}/support", response_model=SupportResponse)
async def support_story(
    story_id: UUID,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    service: StoryService = Depends(get_story_service),
):
    """Add a support reaction to a story."""
    if not settings.enable_stories:
        raise HTTPException(status_code=403, detail="Stories feature is disabled")

    story = await service.get_story(story_id, x_session_id, track_view=False)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    is_new = await service.add_support(story_id, x_session_id)

    return SupportResponse(
        success=True,
        is_new_support=is_new,
        total_supports=story.supports + (1 if is_new else 0),
    )


@router.delete("/{story_id}/support", response_model=SupportResponse)
async def remove_support(
    story_id: UUID,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    service: StoryService = Depends(get_story_service),
):
    """Remove a support reaction from a story."""
    if not settings.enable_stories:
        raise HTTPException(status_code=403, detail="Stories feature is disabled")

    story = await service.get_story(story_id, x_session_id, track_view=False)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    was_supported = await service.remove_support(story_id, x_session_id)

    return SupportResponse(
        success=True,
        is_new_support=False,
        total_supports=story.supports - (1 if was_supported else 0),
    )


@router.post("/{story_id}/message", response_model=EncouragementResponse, status_code=201)
async def send_encouragement(
    story_id: UUID,
    request: EncouragementCreate,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
    service: StoryService = Depends(get_story_service),
):
    """Send an anonymous encouragement message to a story author."""
    if not settings.enable_stories:
        raise HTTPException(status_code=403, detail="Stories feature is disabled")

    story = await service.get_story(story_id, x_session_id, track_view=False)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    try:
        message_id = await service.send_encouragement(
            story_id=story_id,
            message=request.message,
            from_session=x_session_id,
        )
    except StoryServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)

    from datetime import datetime

    return EncouragementResponse(
        id=message_id,
        message=request.message,
        created_at=datetime.utcnow(),
    )


@router.get("/{story_id}/messages", response_model=EncouragementList)
async def get_story_messages(
    story_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: StoryService = Depends(get_story_service),
):
    """Get encouragement messages for a story."""
    if not settings.enable_stories:
        raise HTTPException(status_code=403, detail="Stories feature is disabled")

    messages = await service.get_messages_for_story(story_id, limit, offset)

    return EncouragementList(
        messages=[
            EncouragementResponse(
                id=m.id,
                message=m.message,
                created_at=m.created_at,
            )
            for m in messages
        ],
        total=len(messages),
    )


@router.delete("/{story_id}")
async def hide_story(
    story_id: UUID,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    service: StoryService = Depends(get_story_service),
):
    """
    Hide a story (soft delete).

    Only the story owner can hide their own stories.
    """
    if not settings.enable_stories:
        raise HTTPException(status_code=403, detail="Stories feature is disabled")

    success = await service.hide_story(story_id, x_session_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Story not found or you don't have permission to delete it",
        )

    return {"success": True, "message": "Story hidden successfully"}
