"""Cricket-specific domain contracts: intervals, requests, state snapshots, and delivery events."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.common import (
    ExplanationDepth,
    LanguageCode,
    PerspectiveLens,
)


class CricketInterval(BaseModel):
    """Formal whole-over interval boundary specification for a single cricket innings.
    
    Adheres strictly to docs/product/interval-model.md and ADR-008:
    - after_over = -1 represents the innings start (before any ball bowled).
    - after_over = N represents the state after all deliveries of the Nth over (0-indexed).
    - start_after_over is exclusive; end_after_over is inclusive.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    innings: int = Field(
        default=0,
        ge=0,
        description="0-based innings index (0 = 1st innings, 1 = 2nd innings).",
    )
    start_after_over: int = Field(
        ...,
        ge=-1,
        description="Start boundary (exclusive). -1 denotes innings start; 12 denotes after over 13 completed.",
    )
    end_after_over: int = Field(
        ...,
        ge=0,
        description="End boundary (inclusive). 18 denotes end of over 19 (0-indexed).",
    )

    @model_validator(mode="after")
    def validate_interval_bounds(self) -> "CricketInterval":
        """Enforce strict interval progression rules."""
        if self.end_after_over <= self.start_after_over:
            raise ValueError(
                f"end_after_over ({self.end_after_over}) must be strictly greater than "
                f"start_after_over ({self.start_after_over})."
            )
        return self


class CricketCatchUpRequest(BaseModel):
    """Fan catch-up request for a specified cricket match interval."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    match_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Target match identifier.",
    )
    interval: CricketInterval = Field(
        ...,
        description="Requested innings and whole-over boundary interval.",
    )
    lens: PerspectiveLens = Field(
        default=PerspectiveLens.MATCH,
        description="Presentation perspective lens.",
    )
    target_entity: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Target team name or player name when lens is 'team' or 'player'.",
    )
    language: LanguageCode = Field(
        default=LanguageCode.EN,
        description="Requested explanation language ('en' baseline or 'ta' evaluated).",
    )
    explanation_depth: ExplanationDepth = Field(
        default=ExplanationDepth.STANDARD,
        description="Detail level of generated explanation.",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=64,
        description="Optional client-provided correlation tracking ID.",
    )

    @model_validator(mode="after")
    def validate_target_entity(self) -> "CricketCatchUpRequest":
        """Verify target_entity is specified when lens is team or player."""
        if self.lens in (PerspectiveLens.TEAM, PerspectiveLens.PLAYER) and not self.target_entity:
            raise ValueError(f"target_entity is required when lens is '{self.lens.value}'.")
        return self


class CricketScoreSnapshot(BaseModel):
    """Deterministic score state at an exact boundary point."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    runs: int = Field(..., ge=0, description="Total team runs scored at boundary.")
    wickets: int = Field(..., ge=0, le=10, description="Total wickets lost (0 to 10).")
    overs_completed: int = Field(..., ge=0, description="Number of fully completed overs.")
    legal_balls_in_over: int = Field(
        default=0,
        ge=0,
        le=6,
        description="Legal balls bowled in current over (0 for whole-over boundaries).",
    )
    extras_total: int = Field(default=0, ge=0, description="Cumulative extras conceded.")
    run_rate: float = Field(default=0.0, ge=0.0, description="Current runs per over.")


class CricketStateDelta(BaseModel):
    """Deterministic difference calculated between start and end boundaries."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    runs_added: int = Field(..., ge=0, description="Runs scored during interval.")
    wickets_lost: int = Field(..., ge=0, le=10, description="Wickets fell during interval.")
    completed_overs_delta: int = Field(..., ge=0, description="Full overs completed during interval.")
    legal_balls_added: int = Field(..., ge=0, description="Total legal deliveries in interval.")
    extras_added: int = Field(default=0, ge=0, description="Total extras conceded in interval.")
    interval_run_rate: float = Field(default=0.0, ge=0.0, description="Run rate across interval.")


class CricketDeliveryRuns(BaseModel):
    """Run attribution on a single delivery."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    batter: int = Field(..., ge=0, description="Runs off the bat.")
    extras: int = Field(..., ge=0, description="Extras runs awarded.")
    total: int = Field(..., ge=0, description="Total runs resulting from delivery.")


class CricketDeliveryExtras(BaseModel):
    """Detailed extras breakdown on a delivery."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    wides: int = Field(default=0, ge=0)
    noballs: int = Field(default=0, ge=0)
    byes: int = Field(default=0, ge=0)
    legbyes: int = Field(default=0, ge=0)
    penalty: int = Field(default=0, ge=0)


class CricketWicket(BaseModel):
    """Dismissal record on a delivery."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    player_out: str = Field(..., min_length=1, description="Dismissed batter name.")
    kind: str = Field(..., min_length=1, description="Dismissal method (bowled, caught, lbw, etc.).")
    fielders: Optional[List[str]] = Field(default=None, description="Names of assisting fielders.")


class CricketDeliveryEvent(BaseModel):
    """Normalized delivery event emitted by the cricket engine."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1, description="Deterministic unique ball ID.")
    match_id: str = Field(..., min_length=1)
    innings: int = Field(..., ge=0)
    over: int = Field(..., ge=0, description="0-indexed completed over.")
    delivery_in_over: int = Field(..., ge=1, description="Delivery sequence within over.")
    legal_ball_number: int = Field(
        ...,
        ge=0,
        le=6,
        description="Legal ball index (1 to 6), or 0 if illegal (wide/no-ball).",
    )
    batter: str = Field(..., min_length=1)
    bowler: str = Field(..., min_length=1)
    non_striker: str = Field(..., min_length=1)
    runs: CricketDeliveryRuns = Field(...)
    extras: Optional[CricketDeliveryExtras] = Field(default=None)
    wickets: Optional[List[CricketWicket]] = Field(default=None)
