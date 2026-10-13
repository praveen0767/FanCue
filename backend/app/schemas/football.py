"""Provisional football domain contracts.

CRITICAL ARCHITECTURAL BOUNDARY:
Football implementation remains deferred until Phase 08 (ADR-006).
This module defines the external contract boundary only to guarantee that
shared orchestration layers never assume cricket-specific concepts (such as overs).
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.common import (
    ExplanationDepth,
    LanguageCode,
    PerspectiveLens,
)


class FootballPeriod(str, Enum):
    """Match period divisions in football."""
    FIRST_HALF = "first_half"
    SECOND_HALF = "second_half"
    EXTRA_TIME_1 = "extra_time_1"
    EXTRA_TIME_2 = "extra_time_2"
    PENALTIES = "penalties"


class FootballInterval(BaseModel):
    """Provisional minute-based interval boundary for football."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    period: FootballPeriod = Field(
        default=FootballPeriod.FIRST_HALF,
        description="Target match period.",
    )
    start_minute: int = Field(
        ...,
        ge=0,
        description="Minute mark when fan left (inclusive of preceding action).",
    )
    end_minute: int = Field(
        ...,
        ge=1,
        description="Minute mark when fan returned.",
    )

    @model_validator(mode="after")
    def validate_minute_sequence(self) -> "FootballInterval":
        if self.end_minute <= self.start_minute:
            raise ValueError(
                f"end_minute ({self.end_minute}) must be strictly greater than "
                f"start_minute ({self.start_minute})."
            )
        return self


class FootballCatchUpRequest(BaseModel):
    """Provisional football catch-up request."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    match_id: str = Field(..., min_length=1, max_length=64)
    interval: FootballInterval = Field(...)
    lens: PerspectiveLens = Field(default=PerspectiveLens.MATCH)
    target_entity: Optional[str] = Field(default=None, max_length=64)
    language: LanguageCode = Field(default=LanguageCode.EN)
    explanation_depth: ExplanationDepth = Field(default=ExplanationDepth.STANDARD)
    correlation_id: Optional[str] = Field(default=None, min_length=8, max_length=64)


class FootballScoreSnapshot(BaseModel):
    """Provisional score state for a football match."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    home_score: int = Field(..., ge=0)
    away_score: int = Field(..., ge=0)
    period: FootballPeriod = Field(...)
    minute: int = Field(..., ge=0)


class FootballStateDelta(BaseModel):
    """Provisional state difference for football."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    home_goals: int = Field(..., ge=0)
    away_goals: int = Field(..., ge=0)
    yellow_cards: int = Field(default=0, ge=0)
    red_cards: int = Field(default=0, ge=0)


class FootballMatchEvent(BaseModel):
    """Provisional event representation for football."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1)
    match_id: str = Field(..., min_length=1)
    period: FootballPeriod = Field(...)
    minute: int = Field(..., ge=0)
    second: Optional[int] = Field(default=None, ge=0, le=59)
    event_type: str = Field(..., min_length=1, description="Goal, foul, card, sub, etc.")
    team: str = Field(..., min_length=1)
    player: Optional[str] = Field(default=None)
