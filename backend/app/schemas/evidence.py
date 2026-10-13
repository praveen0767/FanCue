"""Evidence facts, structured fact payloads, and evidence packet assembly contracts."""

from enum import Enum
from typing import Any, Dict, List, Union
from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import SportType
from backend.app.schemas.cricket import (
    CricketScoreSnapshot,
    CricketStateDelta,
)
from backend.app.schemas.football import (
    FootballScoreSnapshot,
    FootballStateDelta,
)
from backend.app.schemas.provenance import SourceProvenance
from backend.app.schemas.retrieval import RetrievedPassage


class FactType(str, Enum):
    """Categorization of verified match evidence facts."""
    WICKET = "wicket"
    BOUNDARY = "boundary"
    PARTNERSHIP = "partnership"
    OVER_SUMMARY = "over_summary"
    STATE_MILESTONE = "state_milestone"
    MATCH_RESULT = "match_result"


class EvidenceFact(BaseModel):
    """A deterministic, verifiable atomic match fact linked directly to source events."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Reproducible identifier for the fact (e.g. 'fact_1529229_ov2_w1').",
    )
    fact_type: FactType = Field(..., description="Category of fact.")
    match_id: str = Field(..., min_length=1)
    source_revision: str = Field(..., min_length=1)
    referenced_event_ids: List[str] = Field(
        ...,
        min_length=1,
        description="List of source event IDs that substantiate this fact.",
    )
    description: str = Field(
        ...,
        min_length=5,
        max_length=256,
        description="Canonical human-readable fact statement.",
    )
    structured_payload: Dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict,
        description="Typed scalar attributes supporting programmatic verification.",
    )


class MatchEvidencePacket(BaseModel):
    """Complete bundle of deterministic facts and provenance assembled for AI explanation."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    packet_id: str = Field(..., min_length=1, description="Deterministic packet identifier.")
    match_id: str = Field(..., min_length=1)
    sport: SportType = Field(...)
    interval_summary: str = Field(..., min_length=1, description="E.g. 'Innings 0, Overs 13-18'.")
    state_before: Union[CricketScoreSnapshot, FootballScoreSnapshot] = Field(...)
    state_after: Union[CricketScoreSnapshot, FootballScoreSnapshot] = Field(...)
    state_delta: Union[CricketStateDelta, FootballStateDelta] = Field(...)
    key_facts: List[EvidenceFact] = Field(
        default_factory=list,
        description="Chronologically ordered consequential facts selected for interval.",
    )
    retrieved_knowledge_ids: List[str] = Field(
        default_factory=list,
        description="IDs of semantic knowledge documents retrieved from Qdrant.",
    )
    retrieved_passages: List[RetrievedPassage] = Field(
        default_factory=list,
        description="Full retrieved context passages with source URLs and locators.",
    )
    provenance: SourceProvenance = Field(..., description="Authoritative dataset provenance record.")
