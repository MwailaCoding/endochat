"""Feedback API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.models.feedback import FeedbackRequest, FeedbackResponse, FeedbackStats
from app.core.dependencies import get_feedback_repo
from app.services.database.repositories.feedback import FeedbackRepository
from app.services.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    repo: FeedbackRepository = Depends(get_feedback_repo),
) -> FeedbackResponse:
    """
    Submit feedback on a chat answer.

    Rating: 1 for positive (helpful), -1 for negative (not helpful).
    """
    try:
        # Validate conversation_id is a valid UUID
        try:
            conversation_uuid = UUID(request.conversation_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid conversation_id format",
            )

        feedback = await repo.create(
            conversation_id=conversation_uuid,
            rating=request.rating,
            message_id=request.message_id,
            reason=request.reason,
            comment=request.comment,
        )

        logger.info(
            "feedback_submitted",
            feedback_id=str(feedback.id),
            rating=request.rating,
            reason=request.reason,
        )

        return FeedbackResponse(
            success=True,
            feedback_id=str(feedback.id),
            message="Thank you for your feedback!",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("feedback_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to save feedback. Please try again.",
        )


@router.get("/feedback/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    repo: FeedbackRepository = Depends(get_feedback_repo),
) -> FeedbackStats:
    """Get feedback statistics."""
    try:
        stats = await repo.get_stats()
        return FeedbackStats(**stats)
    except Exception as e:
        logger.error("feedback_stats_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve feedback statistics.",
        )


@router.get("/feedback/reasons")
async def get_feedback_reasons(
    repo: FeedbackRepository = Depends(get_feedback_repo),
) -> dict:
    """Get breakdown of negative feedback by reason."""
    try:
        breakdown = await repo.get_reason_breakdown()
        return {"reasons": breakdown}
    except Exception as e:
        logger.error("feedback_reasons_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve feedback reasons.",
        )
