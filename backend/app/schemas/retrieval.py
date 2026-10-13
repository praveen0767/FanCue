"""Qdrant semantic contextual retrieval contracts."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import LanguageCode, SportType


class RetrievalStatus(str, Enum):
    """Execution status of contextual knowledge retrieval."""
    SUCCESS = "success"
    EMPTY_RESULT = "empty_result"
    FILTER_EMPTY = "filter_empty"
    FAILED = "failed"


class RetrievalQuery(BaseModel):
    """Typed semantic search query sent to the Qdrant retrieval layer."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_text: str = Field(
        ...,
        min_length=3,
        max_length=512,
        description="Natural language semantic search query.",
    )
    sport: SportType = Field(..., description="Mandatory sport filter.")
    language: LanguageCode = Field(..., description="Mandatory language filter.")
    target_topics: Optional[List[str]] = Field(
        default=None,
        description="Optional metadata topic filters (e.g. ['batting_technique', 'rules']).",
    )
    limit: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of context chunks to retrieve.",
    )


class RetrievedPassage(BaseModel):
    """Contextual knowledge chunk retrieved from Qdrant with full provenance metadata."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(
        ...,
        min_length=1,
        description="Deterministic content-addressed identifier of the knowledge document.",
    )
    sport: SportType = Field(...)
    language: LanguageCode = Field(...)
    topic: str = Field(..., min_length=1)
    content: str = Field(..., min_length=10, description="Retrieved markdown passage content.")
    source_name: str = Field(..., min_length=1, description="Originating publication or rulebook.")
    source_url: str = Field(..., description="Canonical source URL.")
    license: str = Field(..., description="SPDX or license name.")
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Vector cosine similarity score. (NOTE: Does NOT represent factual probability).",
    )


class RetrievalResult(BaseModel):
    """Aggregate result from the retrieval layer."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: RetrievalQuery = Field(...)
    passages: List[RetrievedPassage] = Field(default_factory=list)
    status: RetrievalStatus = Field(...)
    error_detail: Optional[str] = Field(
        default=None,
        description="Diagnostic error message if status is FAILED.",
    )
