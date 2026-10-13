"""Common domain types, enums, identifiers, and match descriptor contracts."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SportType(str, Enum):
    """Supported sport domain identifiers."""
    CRICKET = "cricket"
    FOOTBALL = "football"


class LanguageCode(str, Enum):
    """Supported output languages.
    
    English ('en') is the normative baseline.
    Tamil ('ta') is evaluated under AC-10 quality gates.
    """
    EN = "en"
    TA = "ta"


class PerspectiveLens(str, Enum):
    """Viewing perspective lens."""
    MATCH = "match"
    TEAM = "team"
    PLAYER = "player"


class ExplanationDepth(str, Enum):
    """Detail level for narrative catch-up."""
    BRIEF = "brief"
    STANDARD = "standard"
    DEEP = "deep"


class MatchMode(str, Enum):
    """Data freshness and presentation mode."""
    REPLAY = "replay"
    LIVE = "live"


class MatchDescriptor(BaseModel):
    """Metadata describing a supported match fixture."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    match_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Stable internal match identifier (e.g. '1529229').",
    )
    sport: SportType = Field(
        ...,
        description="Sport category.",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Human-readable match title (e.g. 'India vs West Indies').",
    )
    format: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Match format (e.g. 'ODI', 'T20', 'Test', 'EPL').",
    )
    teams: List[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Participating teams in order [team1, team2].",
    )
    date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Match start date in ISO YYYY-MM-DD format.",
    )
    venue: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Venue or stadium name.",
    )
    mode: MatchMode = Field(
        default=MatchMode.REPLAY,
        description="Classification: V1 strictly operates in replay mode.",
    )
    source_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Identifier of originating dataset source (e.g. 'cricsheet_historical_odi').",
    )
    source_revision: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Source format revision or snapshot hash.",
    )
    supported_innings: List[int] = Field(
        default_factory=lambda: [0, 1],
        description="Available innings or period indexes (0-based).",
    )


class RequestCorrelation(BaseModel):
    """Correlation and tracing metadata for request envelopes."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="Unique request correlation ID for tracing and audit.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timezone-aware UTC timestamp when request was initiated.",
    )
