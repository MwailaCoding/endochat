"""API routes module."""

from fastapi import APIRouter

from app.api import (
    chat,
    feedback,
    health,
    popular,
    share,
    groups,
    stories,
    insights,
    candles,
)

api_router = APIRouter()

# Core routes
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(feedback.router, tags=["feedback"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(popular.router, tags=["popular"])

# Enhanced features
api_router.include_router(share.router, tags=["share"])
api_router.include_router(groups.router, tags=["groups"])
api_router.include_router(stories.router, tags=["stories"])
api_router.include_router(insights.router, tags=["insights"])
api_router.include_router(candles.router, tags=["candles"])

__all__ = ["api_router"]
