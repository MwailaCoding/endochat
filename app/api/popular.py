"""Popular questions API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.models.api_models import PopularQuestionsResponse, PopularQuestionResponse
from app.core.dependencies import get_popular_repo
from app.services.database.repositories.popular import PopularRepository
from app.services.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/popular", response_model=PopularQuestionsResponse)
async def get_popular_questions(
    limit: int = Query(10, ge=1, le=50, description="Maximum questions to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    repo: PopularRepository = Depends(get_popular_repo),
) -> PopularQuestionsResponse:
    """
    Get most popular questions asked by users.

    Optionally filter by category (symptoms, treatment, diagnosis, etc.).
    """
    try:
        questions = await repo.get_top(limit=limit, category=category)

        response_questions = [
            PopularQuestionResponse(
                id=str(q.id),
                question=q.question,
                category=q.category,
                ask_count=q.ask_count,
                last_asked=str(q.last_asked),
            )
            for q in questions
        ]

        return PopularQuestionsResponse(
            questions=response_questions,
            total=len(response_questions),
        )

    except Exception as e:
        logger.error("popular_questions_error", error=str(e))
        return PopularQuestionsResponse(questions=[], total=0)


@router.get("/popular/trending")
async def get_trending_questions(
    limit: int = Query(5, ge=1, le=20),
    hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    repo: PopularRepository = Depends(get_popular_repo),
) -> dict:
    """
    Get trending questions from recent time period.

    Shows questions gaining popularity in the specified time window.
    """
    try:
        questions = await repo.get_trending(limit=limit, within_hours=hours)

        return {
            "questions": [
                {
                    "id": str(q.id),
                    "question": q.question,
                    "category": q.category,
                    "ask_count": q.ask_count,
                }
                for q in questions
            ],
            "time_window_hours": hours,
        }

    except Exception as e:
        logger.error("trending_questions_error", error=str(e))
        return {"questions": [], "time_window_hours": hours}


@router.get("/popular/categories")
async def get_question_categories(
    repo: PopularRepository = Depends(get_popular_repo),
) -> dict:
    """
    Get all question categories with counts.

    Useful for building category navigation.
    """
    try:
        categories = await repo.get_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error("categories_error", error=str(e))
        return {"categories": []}


@router.get("/popular/search")
async def search_popular_questions(
    q: str = Query(..., min_length=2, description="Search term"),
    limit: int = Query(10, ge=1, le=50),
    repo: PopularRepository = Depends(get_popular_repo),
) -> dict:
    """Search popular questions by text."""
    try:
        questions = await repo.search(search_term=q, limit=limit)

        return {
            "query": q,
            "questions": [
                {
                    "id": str(q.id),
                    "question": q.question,
                    "category": q.category,
                    "ask_count": q.ask_count,
                }
                for q in questions
            ],
        }

    except Exception as e:
        logger.error("search_questions_error", error=str(e))
        return {"query": q, "questions": []}
