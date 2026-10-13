"""AI explanation generation, claim structuring, verification outcomes, and catch-up response contracts."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.common import (
    LanguageCode,
    MatchDescriptor,
    MatchMode,
)
from backend.app.schemas.cricket import (
    CricketInterval,
    CricketScoreSnapshot,
    CricketStateDelta,
)
from backend.app.schemas.evidence import MatchEvidencePacket


class ClaimType(str, Enum):
    """Semantic category of an individual explanatory statement."""
    SCORE_DELTA = "score_delta"
    EVENT_CHRONOLOGY = "event_chronology"
    TACTICAL_CONTEXT = "tactical_context"
    HISTORICAL_RULE = "historical_rule"
    META = "meta"


class StructuredClaim(BaseModel):
    """An individual assertion in an explanation with explicit citation linkage."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(..., min_length=1, description="Unique claim identifier.")
    claim_type: ClaimType = Field(..., description="Classification of assertion.")
    text: str = Field(..., min_length=3, description="Natural language assertion.")
    cited_fact_ids: List[str] = Field(
        default_factory=list,
        description="IDs of atomic EvidenceFacts cited to substantiate this claim.",
    )
    cited_knowledge_ids: List[str] = Field(
        default_factory=list,
        description="IDs of Qdrant RetrievedPassages cited for background context.",
    )


class GenerationMode(str, Enum):
    """Origin of generated response."""
    LLM_VERIFIED = "llm_verified"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


class VerificationStatus(str, Enum):
    """Fact verification outcome."""
    VERIFIED = "verified"
    FAILED_VERIFICATION = "failed_verification"
    UNVERIFIED_FALLBACK = "unverified_fallback"


class FallbackReason(str, Enum):
    """Diagnostic justification for invoking the deterministic fallback."""
    NONE = "none"
    TIMEOUT = "timeout"
    LLM_ERROR = "llm_error"
    FACT_MISMATCH = "fact_mismatch"
    UNSUPPORTED_CLAIMS = "unsupported_claims"
    DISABLED = "disabled"


class ExplanationPayload(BaseModel):
    """Structured explanation and verification envelope."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(..., min_length=10, description="Synthesized narrative explanation.")
    claims: List[StructuredClaim] = Field(
        default_factory=list,
        description="Granular assertions with evidence citations.",
    )
    generation_mode: GenerationMode = Field(..., description="LLM generated or deterministic fallback.")
    verification_status: VerificationStatus = Field(..., description="Fact verification outcome.")
    fallback_reason: FallbackReason = Field(
        default=FallbackReason.NONE,
        description="Reason fallback was engaged, or NONE if LLM output verified.",
    )


class CricketCatchUpResponse(BaseModel):
    """Complete fan-facing API response for cricket catch-up."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    match: MatchDescriptor = Field(..., description="Authoritative match metadata.")
    interval: CricketInterval = Field(..., description="Requested interval.")
    state_before: CricketScoreSnapshot = Field(..., description="State at start boundary.")
    state_after: CricketScoreSnapshot = Field(..., description="State at end boundary.")
    state_delta: CricketStateDelta = Field(..., description="Calculated state difference.")
    evidence_packet: MatchEvidencePacket = Field(..., description="Inspectable evidence packet.")
    explanation: ExplanationPayload = Field(..., description="Structured verified explanation.")
    language: LanguageCode = Field(..., description="Output language.")
    mode: MatchMode = Field(default=MatchMode.REPLAY, description="Always REPLAY in V1.")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Response generation UTC timestamp.",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal notices or disclosures.",
    )

    @field_validator("generated_at")
    @classmethod
    def validate_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware UTC datetime.")
        return v
