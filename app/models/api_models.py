"""Models for external API responses."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class WHOResponse(BaseModel):
    """Response from WHO Global Health Observatory API."""

    title: str
    content: str
    publication_date: Optional[str] = None
    url: str
    indicator_code: Optional[str] = None
    sections: Dict[str, str] = Field(default_factory=dict)


class PubMedArticle(BaseModel):
    """Article from PubMed E-utilities API."""

    pmid: str
    title: str
    abstract: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    journal: Optional[str] = None
    publication_date: Optional[str] = None
    url: str
    mesh_terms: List[str] = Field(default_factory=list)


class OpenFDADrug(BaseModel):
    """Drug information from OpenFDA API."""

    drug_name: str
    generic_name: Optional[str] = None
    brand_names: List[str] = Field(default_factory=list)
    indications: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    adverse_reactions: List[str] = Field(default_factory=list)
    dosage_forms: List[str] = Field(default_factory=list)
    source_url: str


class DrugBankDrug(BaseModel):
    """Drug information from DrugBank API."""

    drugbank_id: str
    name: str
    description: Optional[str] = None
    indication: Optional[str] = None
    pharmacodynamics: Optional[str] = None
    mechanism_of_action: Optional[str] = None
    toxicity: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    url: str


class MedlinePlusArticle(BaseModel):
    """Health topic from MedlinePlus API."""

    title: str
    url: str
    snippet: Optional[str] = None
    full_summary: Optional[str] = None
    organization: str = "MedlinePlus"


class UnifiedAPIResult(BaseModel):
    """Unified result from any health API."""

    source: str
    title: str
    content: str
    url: Optional[str] = None
    publication_date: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class HealthCheckResponse(BaseModel):
    """Health check endpoint response."""

    healthy: bool
    status: str
    database: str = "unknown"
    cache: str = "unknown"
    latency_ms: int
    version: str


class PopularQuestionResponse(BaseModel):
    """Popular question with metadata."""

    id: str
    question: str
    category: Optional[str] = None
    ask_count: int
    last_asked: str


class PopularQuestionsResponse(BaseModel):
    """Response for popular questions endpoint."""

    questions: List[PopularQuestionResponse]
    total: int
