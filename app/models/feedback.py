"""Feedback request and response models."""

from typing import Optional, Literal
from pydantic import BaseModel, Field


FeedbackRating = Literal[1, -1]
FeedbackReason = Literal[
    "wrong_info", "incomplete", "hard_to_understand", "not_relevant", "other"
]


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""

    conversation_id: str = Field(
        ..., description="ID of the conversation being rated"
    )
    message_id: Optional[str] = Field(
        None, description="Optional specific message ID within conversation"
    )
    rating: FeedbackRating = Field(
        ..., description="Rating: 1 for positive, -1 for negative"
    )
    reason: Optional[FeedbackReason] = Field(
        None, description="Reason for negative feedback"
    )
    comment: Optional[str] = Field(
        None, max_length=1000, description="Optional free-text comment"
    )


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    success: bool = Field(..., description="Whether feedback was saved")
    feedback_id: str = Field(..., description="ID of the saved feedback")
    message: str = Field("Thank you for your feedback", description="Confirmation message")


class FeedbackStats(BaseModel):
    """Statistics about feedback."""

    total: int
    positive: int
    negative: int
    satisfaction_rate: float = Field(..., ge=0, le=100)
