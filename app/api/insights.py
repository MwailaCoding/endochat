"""API routes for data insights dashboard."""

from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.services.insights_service import InsightsService
from app.core.dependencies import get_database_pool, get_cache_service
from app.services.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


class DashboardResponse(BaseModel):
    """Dashboard metrics response."""

    total_questions: int
    unique_users: int
    total_stories: int
    total_groups: int
    total_candles: int
    questions_today: int
    questions_this_week: int
    avg_confidence_score: float
    top_categories: List[dict]


class TrendingQuestionResponse(BaseModel):
    """Trending question response."""

    question: str
    category: str | None
    count: int
    growth_percent: float


class GeographicPointResponse(BaseModel):
    """Geographic data point response."""

    location: str
    count: int
    latitude: float | None = None
    longitude: float | None = None


class TimelinePointResponse(BaseModel):
    """Timeline data point."""

    period: str
    questions: int
    users: int


class CategoryBreakdownResponse(BaseModel):
    """Category breakdown response."""

    category: str
    count: int
    percentage: float
    avg_confidence: float


class EngagementStatsResponse(BaseModel):
    """Engagement statistics response."""

    story_supports: int
    story_messages: int
    group_joins: int
    group_reviews: int
    card_clicks: int
    total_engagement: int


def get_insights_service(
    db_pool=Depends(get_database_pool),
    cache=Depends(get_cache_service),
) -> InsightsService:
    """Get insights service instance."""
    return InsightsService(db_pool, cache)


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    service: InsightsService = Depends(get_insights_service),
):
    """
    Get the main dashboard metrics.

    Returns aggregated statistics about platform usage.
    """
    if not settings.enable_insights:
        raise HTTPException(status_code=403, detail="Insights feature is disabled")

    metrics = await service.get_dashboard()

    return DashboardResponse(
        total_questions=metrics.total_questions,
        unique_users=metrics.unique_users,
        total_stories=metrics.total_stories,
        total_groups=metrics.total_groups,
        total_candles=metrics.total_candles,
        questions_today=metrics.questions_today,
        questions_this_week=metrics.questions_this_week,
        avg_confidence_score=metrics.avg_confidence_score,
        top_categories=metrics.top_categories,
    )


@router.get("/trending", response_model=List[TrendingQuestionResponse])
async def get_trending_questions(
    days: int = Query(default=7, ge=1, le=90, description="Analysis period in days"),
    limit: int = Query(default=10, ge=1, le=50, description="Max questions to return"),
    service: InsightsService = Depends(get_insights_service),
):
    """
    Get trending questions.

    Returns questions with the highest growth in the specified period.
    """
    if not settings.enable_insights:
        raise HTTPException(status_code=403, detail="Insights feature is disabled")

    trending = await service.get_trending_questions(days=days, limit=limit)

    return [
        TrendingQuestionResponse(
            question=t.question,
            category=t.category,
            count=t.count,
            growth_percent=t.growth_percent,
        )
        for t in trending
    ]


@router.get("/geography", response_model=List[GeographicPointResponse])
async def get_geographic_distribution(
    limit: int = Query(default=20, ge=1, le=100, description="Max locations to return"),
    service: InsightsService = Depends(get_insights_service),
):
    """
    Get geographic distribution of users and content.

    Returns locations with activity counts.
    """
    if not settings.enable_insights:
        raise HTTPException(status_code=403, detail="Insights feature is disabled")

    points = await service.get_geographic_distribution(limit=limit)

    return [
        GeographicPointResponse(
            location=p.location,
            count=p.count,
            latitude=p.latitude,
            longitude=p.longitude,
        )
        for p in points
    ]


@router.get("/timeline", response_model=List[TimelinePointResponse])
async def get_activity_timeline(
    days: int = Query(default=30, ge=1, le=365, description="Number of days"),
    granularity: Literal["hour", "day", "week"] = Query(
        default="day",
        description="Time granularity",
    ),
    service: InsightsService = Depends(get_insights_service),
):
    """
    Get activity timeline data.

    Returns time series data of questions and users.
    """
    if not settings.enable_insights:
        raise HTTPException(status_code=403, detail="Insights feature is disabled")

    timeline = await service.get_activity_timeline(days=days, granularity=granularity)

    return [
        TimelinePointResponse(
            period=point["period"],
            questions=point["questions"],
            users=point["users"],
        )
        for point in timeline
    ]


@router.get("/categories", response_model=List[CategoryBreakdownResponse])
async def get_category_breakdown(
    service: InsightsService = Depends(get_insights_service),
):
    """
    Get breakdown of questions by category.

    Returns categories with counts and percentages.
    """
    if not settings.enable_insights:
        raise HTTPException(status_code=403, detail="Insights feature is disabled")

    categories = await service.get_category_breakdown()

    return [
        CategoryBreakdownResponse(
            category=cat["category"],
            count=cat["count"],
            percentage=cat["percentage"],
            avg_confidence=cat["avg_confidence"],
        )
        for cat in categories
    ]


@router.get("/engagement", response_model=EngagementStatsResponse)
async def get_engagement_stats(
    service: InsightsService = Depends(get_insights_service),
):
    """
    Get engagement statistics across all features.

    Returns counts of supports, messages, joins, etc.
    """
    if not settings.enable_insights:
        raise HTTPException(status_code=403, detail="Insights feature is disabled")

    stats = await service.get_engagement_stats()

    return EngagementStatsResponse(**stats)
