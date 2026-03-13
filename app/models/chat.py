"""Chat request and response models."""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    """Source citation for an answer."""

    source: Literal["who", "pubmed", "openfda", "drugbank", "medlineplus"]
    title: str
    url: Optional[str] = None
    snippet: Optional[str] = None
    publication_date: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)


class ConfidenceModel(BaseModel):
    """Confidence assessment for an answer."""

    score: int = Field(..., ge=0, le=100)
    level: Literal["high", "medium", "low"]
    badge: str
    reason: str


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The user's question about endometriosis",
    )
    session_id: Optional[str] = Field(
        None, description="Session ID for grouping conversations"
    )
    mode: Literal["simple", "detailed"] = Field(
        "detailed", description="Response mode - simple for plain language, detailed for comprehensive"
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    answer: str = Field(..., description="The generated answer")
    sources: List[SourceCitation] = Field(
        default_factory=list, description="Source citations used"
    )
    confidence: ConfidenceModel = Field(..., description="Confidence assessment")
    response_time_ms: int = Field(..., description="Response time in milliseconds")
    from_cache: bool = Field(False, description="Whether response came from cache")
    conversation_id: str = Field(..., description="Unique conversation identifier")
    suggested_questions: List[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )


class SimpleChatResponse(BaseModel):
    """Simplified response without LLM processing."""

    answer: str
    sources: List[SourceCitation]
    sources_found: int
    response_time_ms: int
    from_cache: bool = False
