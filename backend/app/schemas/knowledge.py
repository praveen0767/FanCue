"""Knowledge document and chunk metadata contracts for Qdrant ingestion and retrieval."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.common import LanguageCode, SportType
from backend.app.schemas.provenance import PermittedUse


class ReviewStatus(str, Enum):
    """Editorial and legal review status of knowledge documents."""
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class SourceCheckStatus(str, Enum):
    """Verification status of upstream references and citations."""
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    PENDING = "pending"


class KnowledgeType(str, Enum):
    """Semantic category of knowledge note."""
    TERMINOLOGY = "terminology"
    INTERVAL_INTERPRETATION = "interval_interpretation"
    FORMAT_CONTEXT = "format_context"
    RULES = "rules"


class KnowledgeSourceType(str, Enum):
    """Origin classification of the content."""
    FANCUE_AUTHORED = "fancue_authored"
    OFFICIAL_REFERENCE = "official_reference"
    DATA_SPECIFICATION = "data_specification"


class KnowledgeDocumentFrontmatter(BaseModel):
    """Schema for Markdown YAML frontmatter in ingestion/knowledge/."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
        description="Logical document identifier stable across revisions.",
    )
    title: str = Field(
        ...,
        min_length=3,
        max_length=128,
        description="Concise human-readable title.",
    )
    sport: SportType = Field(..., description="Sport category.")
    language: LanguageCode = Field(default=LanguageCode.EN, description="Language code.")
    topic: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
        description="Domain topic grouping.",
    )
    knowledge_type: KnowledgeType = Field(..., description="Knowledge classification.")
    review_status: ReviewStatus = Field(
        default=ReviewStatus.DRAFT,
        description="Review gate status: only 'approved' may enter production collections.",
    )
    source_type: KnowledgeSourceType = Field(
        default=KnowledgeSourceType.FANCUE_AUTHORED,
        description="Source material origin.",
    )
    source_name: str = Field(..., min_length=2, max_length=128)
    source_url: str = Field(..., min_length=8)
    source_revision: str = Field(..., min_length=1, max_length=64)
    citation_locator: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Exact Law, Clause, or Section locator.",
    )
    license: str = Field(
        default="CC-BY-4.0",
        min_length=2,
        max_length=128,
        description="License of the authored text passage.",
    )
    permitted_use: PermittedUse = Field(
        default=PermittedUse.OPEN_ATTRIBUTION,
        description="Permitted usage tier.",
    )
    source_check_status: SourceCheckStatus = Field(
        default=SourceCheckStatus.VERIFIED,
        description="Verification state of source claims.",
    )
    document_revision: str = Field(
        default="1.0.0",
        min_length=1,
        max_length=32,
        description="Revision number of this specific note.",
    )
    effective_from: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Effective start date in ISO YYYY-MM-DD format.",
    )
    effective_to: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Effective expiry date in ISO YYYY-MM-DD format.",
    )


class KnowledgeChunkPayload(BaseModel):
    """Complete typed Qdrant payload schema stored with each vector point."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Required by FanCue Constitution (AGENTS.md Section 6)
    doc_id: str = Field(
        ...,
        min_length=8,
        description="Deterministic content-addressed document identity.",
    )
    source_name: str = Field(..., min_length=2, max_length=128)
    source_url: str = Field(..., min_length=8)
    license: str = Field(..., min_length=2, max_length=128)
    language: LanguageCode = Field(...)
    sport: SportType = Field(...)
    topic: str = Field(..., min_length=3, max_length=64)
    chunk_index: int = Field(..., ge=0, description="0-based index of chunk within document.")
    ingestion_date: str = Field(..., description="ISO 8601 UTC ingestion timestamp.")
    permitted_use: PermittedUse = Field(...)

    # Extended Reliability and Provenance Fields (Phase 04 Section 6)
    logical_doc_id: str = Field(..., min_length=3, max_length=64)
    document_revision: str = Field(..., min_length=1, max_length=32)
    source_revision: str = Field(..., min_length=1, max_length=64)
    content_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    chunk_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    chunker_version: str = Field(..., min_length=1, max_length=32)
    embedding_model: str = Field(..., min_length=3, max_length=128)
    embedding_model_revision: str = Field(..., min_length=8, max_length=64)
    embedding_dimensions: int = Field(default=384, ge=1)
    source_type: KnowledgeSourceType = Field(...)
    knowledge_type: KnowledgeType = Field(...)
    section_title: str = Field(..., min_length=1, max_length=128)
    citation_locator: Optional[str] = Field(default=None, max_length=128)
    effective_from: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    effective_to: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    review_status: ReviewStatus = Field(...)
    source_check_status: SourceCheckStatus = Field(...)
    active: bool = Field(default=True)
    text: str = Field(..., min_length=10, description="Exact normalized text passage.")


class KnowledgeChunk(BaseModel):
    """In-memory representation of an individual knowledge chunk with point ID."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str = Field(
        ...,
        min_length=8,
        description="Deterministic chunk identifier: {doc_id}_c{chunk_index}_{chunk_sha256[:8]}.",
    )
    point_id: str = Field(
        ...,
        pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
        description="Deterministic UUIDv5 suitable for Qdrant point identifier.",
    )
    payload: KnowledgeChunkPayload = Field(...)
    token_count: int = Field(..., ge=1, description="Token count under the target embedding tokenizer.")
