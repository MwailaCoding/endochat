"""Chat API endpoints."""

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from app.models.chat import ChatRequest, ChatResponse
from app.core.dependencies import get_orchestrator
from app.services.orchestrator import ChatOrchestrator
from app.services.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
    orchestrator: ChatOrchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    """
    Process a chat question about endometriosis.

    Returns an answer with cited sources and confidence score.
    """
    try:
        # Get session ID from request or header
        session_id = request.session_id or req.headers.get("X-Session-Id")

        logger.info(
            "chat_request",
            question_length=len(request.question),
            mode=request.mode,
            has_session=bool(session_id),
        )

        # Process the question
        response = await orchestrator.process_question(
            question=request.question,
            session_id=session_id,
            mode=request.mode,
            use_llm=True,
        )

        return response

    except Exception as e:
        logger.error("chat_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your question. Please try again.",
        )


@router.post("/chat/simple", response_model=ChatResponse)
async def chat_simple(
    request: ChatRequest,
    req: Request,
    orchestrator: ChatOrchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    """
    Process a chat question without LLM (faster, cheaper).

    Returns sources and a template-based answer.
    """
    try:
        session_id = request.session_id or req.headers.get("X-Session-Id")

        response = await orchestrator.process_simple(
            question=request.question,
            session_id=session_id,
        )

        return response

    except Exception as e:
        logger.error("chat_simple_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your question.",
        )


@router.get("/chat/suggestions")
async def get_suggestions(
    question: str,
    category: str = None,
    orchestrator: ChatOrchestrator = Depends(get_orchestrator),
) -> dict:
    """Get follow-up question suggestions."""
    suggestions = await orchestrator.get_suggestions(question, category)
    return {"suggestions": suggestions}


@router.get("/chat/starters")
async def get_starter_questions(
    orchestrator: ChatOrchestrator = Depends(get_orchestrator),
) -> dict:
    """Get starter questions for new users."""
    starters = orchestrator.suggestion_generator.get_starter_questions()
    return {"questions": starters}
