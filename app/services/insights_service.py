"""Insights service for data visualization and dashboard."""

from typing import Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.services.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TrendingQuestion:
    """Trending question with growth metrics."""

    question: str
    category: Optional[str]
    count: int
    growth_percent: float


@dataclass
class GeographicPoint:
    """Geographic data point."""

    location: str
    count: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class DashboardMetrics:
    """Aggregated dashboard metrics."""

    total_questions: int
    unique_users: int
    total_stories: int
    total_groups: int
    total_candles: int
    questions_today: int
    questions_this_week: int
    avg_confidence_score: float
    top_categories: List[dict]


class InsightsService:
    """Service for generating insights and dashboard data."""

    def __init__(self, db_pool, cache_service=None):
        """Initialize with database pool and optional cache."""
        self.db_pool = db_pool
        self.cache = cache_service

    async def get_dashboard(self) -> DashboardMetrics:
        """
        Get aggregated dashboard metrics.

        Returns comprehensive metrics about platform usage.
        """
        cache_key = "insights:dashboard"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return DashboardMetrics(**cached)

        async with self.db_pool.pool.acquire() as conn:
            total_questions = await conn.fetchval(
                "SELECT COUNT(*) FROM conversations"
            ) or 0

            unique_users = await conn.fetchval(
                "SELECT COUNT(DISTINCT session_id) FROM conversations"
            ) or 0

            total_stories = await conn.fetchval(
                "SELECT COUNT(*) FROM stories WHERE moderated = TRUE AND hidden = FALSE"
            ) or 0

            total_groups = await conn.fetchval(
                "SELECT COUNT(*) FROM support_groups WHERE active = TRUE"
            ) or 0

            total_candles = await conn.fetchval(
                "SELECT COUNT(*) FROM candles"
            ) or 0

            today = datetime.utcnow().date()
            questions_today = await conn.fetchval(
                "SELECT COUNT(*) FROM conversations WHERE DATE(created_at) = $1",
                today,
            ) or 0

            week_ago = today - timedelta(days=7)
            questions_this_week = await conn.fetchval(
                "SELECT COUNT(*) FROM conversations WHERE DATE(created_at) >= $1",
                week_ago,
            ) or 0

            avg_confidence = await conn.fetchval(
                "SELECT AVG(confidence_score) FROM conversations WHERE confidence_score IS NOT NULL"
            ) or 0.0

            top_categories_rows = await conn.fetch("""
                SELECT category, COUNT(*) as count
                FROM popular_questions
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
                LIMIT 5
            """)

        top_categories = [
            {"category": row["category"], "count": row["count"]}
            for row in top_categories_rows
        ]

        metrics = DashboardMetrics(
            total_questions=total_questions,
            unique_users=unique_users,
            total_stories=total_stories,
            total_groups=total_groups,
            total_candles=total_candles,
            questions_today=questions_today,
            questions_this_week=questions_this_week,
            avg_confidence_score=round(avg_confidence, 2),
            top_categories=top_categories,
        )

        if self.cache:
            await self.cache.set(cache_key, metrics.__dict__, ttl=300)

        return metrics

    async def get_trending_questions(
        self,
        days: int = 7,
        limit: int = 10,
    ) -> List[TrendingQuestion]:
        """
        Get trending questions with growth calculation.

        Args:
            days: Period to analyze
            limit: Maximum questions to return

        Returns:
            List of trending questions with growth metrics
        """
        cache_key = f"insights:trending:{days}:{limit}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return [TrendingQuestion(**q) for q in cached]

        now = datetime.utcnow()
        current_start = now - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)

        query = """
            WITH current_period AS (
                SELECT 
                    question,
                    category,
                    COUNT(*) as current_count
                FROM popular_questions
                WHERE created_at >= $1
                GROUP BY question, category
            ),
            previous_period AS (
                SELECT 
                    question,
                    COUNT(*) as previous_count
                FROM popular_questions
                WHERE created_at >= $2 AND created_at < $1
                GROUP BY question
            )
            SELECT 
                c.question,
                c.category,
                c.current_count as count,
                COALESCE(p.previous_count, 0) as previous_count,
                CASE 
                    WHEN COALESCE(p.previous_count, 0) = 0 THEN 100.0
                    ELSE ((c.current_count - p.previous_count)::float / p.previous_count * 100)
                END as growth_percent
            FROM current_period c
            LEFT JOIN previous_period p ON c.question = p.question
            ORDER BY c.current_count DESC, growth_percent DESC
            LIMIT $3
        """

        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, current_start, previous_start, limit)

        trending = [
            TrendingQuestion(
                question=row["question"],
                category=row["category"],
                count=row["count"],
                growth_percent=round(row["growth_percent"], 1),
            )
            for row in rows
        ]

        if self.cache:
            await self.cache.set(
                cache_key,
                [t.__dict__ for t in trending],
                ttl=600,
            )

        return trending

    async def get_geographic_distribution(
        self,
        limit: int = 20,
    ) -> List[GeographicPoint]:
        """
        Get geographic distribution of users/content.

        Based on stories and group locations.
        """
        cache_key = f"insights:geography:{limit}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return [GeographicPoint(**p) for p in cached]

        query = """
            WITH combined_locations AS (
                SELECT location, NULL as latitude, NULL as longitude
                FROM stories
                WHERE location IS NOT NULL AND hidden = FALSE
                UNION ALL
                SELECT 
                    COALESCE(city || ', ' || country, city, country) as location,
                    latitude,
                    longitude
                FROM support_groups
                WHERE active = TRUE AND (city IS NOT NULL OR country IS NOT NULL)
            )
            SELECT 
                location,
                COUNT(*) as count,
                MAX(latitude) as latitude,
                MAX(longitude) as longitude
            FROM combined_locations
            WHERE location IS NOT NULL AND location != ''
            GROUP BY location
            ORDER BY count DESC
            LIMIT $1
        """

        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, limit)

        points = [
            GeographicPoint(
                location=row["location"],
                count=row["count"],
                latitude=row["latitude"],
                longitude=row["longitude"],
            )
            for row in rows
        ]

        if self.cache:
            await self.cache.set(
                cache_key,
                [p.__dict__ for p in points],
                ttl=3600,
            )

        return points

    async def get_activity_timeline(
        self,
        days: int = 30,
        granularity: str = "day",
    ) -> List[dict]:
        """
        Get activity timeline data.

        Args:
            days: Number of days to analyze
            granularity: 'day', 'week', or 'hour'

        Returns:
            List of data points with timestamp and counts
        """
        cache_key = f"insights:timeline:{days}:{granularity}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

        start_date = datetime.utcnow() - timedelta(days=days)

        if granularity == "hour":
            date_trunc = "hour"
        elif granularity == "week":
            date_trunc = "week"
        else:
            date_trunc = "day"

        query = f"""
            SELECT 
                DATE_TRUNC('{date_trunc}', created_at) as period,
                COUNT(*) as questions,
                COUNT(DISTINCT session_id) as users
            FROM conversations
            WHERE created_at >= $1
            GROUP BY DATE_TRUNC('{date_trunc}', created_at)
            ORDER BY period ASC
        """

        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, start_date)

        timeline = [
            {
                "period": row["period"].isoformat(),
                "questions": row["questions"],
                "users": row["users"],
            }
            for row in rows
        ]

        if self.cache:
            await self.cache.set(cache_key, timeline, ttl=1800)

        return timeline

    async def get_category_breakdown(self) -> List[dict]:
        """Get breakdown of questions by category."""
        cache_key = "insights:categories"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

        query = """
            SELECT 
                COALESCE(category, 'uncategorized') as category,
                COUNT(*) as count,
                AVG(confidence_score) as avg_confidence
            FROM popular_questions
            GROUP BY category
            ORDER BY count DESC
        """

        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query)

        total = sum(row["count"] for row in rows)
        categories = [
            {
                "category": row["category"],
                "count": row["count"],
                "percentage": round(row["count"] / total * 100, 1) if total > 0 else 0,
                "avg_confidence": round(row["avg_confidence"] or 0, 2),
            }
            for row in rows
        ]

        if self.cache:
            await self.cache.set(cache_key, categories, ttl=1800)

        return categories

    async def get_engagement_stats(self) -> dict:
        """Get engagement statistics across features."""
        cache_key = "insights:engagement"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

        async with self.db_pool.pool.acquire() as conn:
            story_supports = await conn.fetchval(
                "SELECT COALESCE(SUM(supports), 0) FROM stories"
            ) or 0

            story_messages = await conn.fetchval(
                "SELECT COUNT(*) FROM story_messages"
            ) or 0

            group_joins = await conn.fetchval(
                "SELECT COUNT(*) FROM group_joins"
            ) or 0

            group_reviews = await conn.fetchval(
                "SELECT COUNT(*) FROM group_reviews"
            ) or 0

            card_shares = await conn.fetchval(
                "SELECT COALESCE(SUM(clicks), 0) FROM shared_cards"
            ) or 0

        stats = {
            "story_supports": story_supports,
            "story_messages": story_messages,
            "group_joins": group_joins,
            "group_reviews": group_reviews,
            "card_clicks": card_shares,
            "total_engagement": (
                story_supports + story_messages + group_joins + group_reviews + card_shares
            ),
        }

        if self.cache:
            await self.cache.set(cache_key, stats, ttl=600)

        return stats
