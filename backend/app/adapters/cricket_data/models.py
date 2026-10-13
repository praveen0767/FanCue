"""Pydantic models for Cricket Data API normalization and near-live match discovery."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CricketDataInningsScore(BaseModel):
    """Normalized score for one innings in a match."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    r: int = Field(default=0, ge=0, description="Runs scored.")
    w: int = Field(default=0, ge=0, description="Wickets lost.")
    o: float = Field(default=0.0, ge=0.0, description="Overs bowled (e.g. 18.2).")
    inning: str = Field(default="", description="Innings title, e.g. 'India Inning 1'.")


class CricketDataTeamInfo(BaseModel):
    """Team details reported by the provider."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str = Field(..., description="Full team name.")
    shortname: Optional[str] = Field(default=None, description="Short code, e.g. 'IND'.")
    img: Optional[str] = Field(default=None, description="Team emblem URL if available.")


class CricketDataMatchItem(BaseModel):
    """Normalized near-live match descriptor from CricketData.org."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str = Field(..., description="Provider match UUID.")
    name: str = Field(..., description="Match headline, e.g. 'India vs Australia, 1st ODI'.")
    match_type: str = Field(..., description="Match format code: 't20', 'odi', 'test'.")
    status: str = Field(..., description="Match state message, e.g. 'Innings break'.")
    venue: Optional[str] = Field(default=None, description="Stadium and city.")
    date: str = Field(..., description="Start date (YYYY-MM-DD).")
    date_time_gmt: Optional[str] = Field(default=None, description="GMT start time string.")
    teams: List[str] = Field(default_factory=list, description="List of 2 competing teams.")
    team_info: List[CricketDataTeamInfo] = Field(
        default_factory=list, description="Optional team metadata."
    )
    score: List[CricketDataInningsScore] = Field(
        default_factory=list, description="Innings score summaries."
    )
    series_id: Optional[str] = Field(default=None, description="Tournament / series UUID.")
    match_started: bool = Field(default=False, description="Whether play has begun.")
    match_ended: bool = Field(default=False, description="Whether match has completed.")
    source: str = Field(default="CricketData.org", description="Authoritative external source.")
    source_url: str = Field(default="https://cricketdata.org/", description="Provider URL.")
    freshness: str = Field(
        default="Near-live · ~30s-5m delay",
        description="Freshness statement to ensure honest expectations.",
    )
    license: str = Field(
        default="Personal/Non-commercial free tier (100 hits/day)",
        description="Dataset licensing designation.",
    )
    retrieved_at: str = Field(..., description="ISO UTC timestamp of retrieval.")


class CricketDataMatchesResponse(BaseModel):
    """API envelope for near-live match discovery."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(default="success", description="'success', 'unconfigured', 'rate_limited', 'error'.")
    configured: bool = Field(default=True, description="Whether a valid API key is present.")
    matches: List[CricketDataMatchItem] = Field(default_factory=list, description="Discovered matches.")
    total: int = Field(default=0, ge=0, description="Total count of matches.")
    cached: bool = Field(default=False, description="True if served from internal TTL cache.")
    cached_at: Optional[str] = Field(default=None, description="Cache generation timestamp.")
    hits_today: Optional[int] = Field(default=None, description="Provider quota hits today.")
    hits_left: Optional[int] = Field(default=None, description="Provider quota hits remaining.")
    message: Optional[str] = Field(default=None, description="Informational or error notice.")


class CricketDataScorecardResponse(BaseModel):
    """API envelope for near-live match scorecard."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(default="success", description="'success', 'unconfigured', 'rate_limited', 'error', 'not_found'.")
    configured: bool = Field(default=True, description="Whether a valid API key is present.")
    match: Optional[CricketDataMatchItem] = Field(default=None, description="Match metadata summary.")
    scorecard: Optional[Dict[str, Any]] = Field(default=None, description="Raw normalized scorecard entries.")
    can_reconstruct_interval: bool = Field(
        default=False,
        description="Always False on free tier scorecards — ball-by-ball delivery log required.",
    )
    limitation_reason: str = Field(
        default=(
            "Granular ball-by-ball delivery ledger required for deterministic interval "
            "reconstruction is not available in free tier scorecards. Scorecards provide "
            "aggregate figures only."
        ),
        description="Honest explanation of capability boundary.",
    )
    cached: bool = Field(default=False, description="True if served from internal TTL cache.")
    cached_at: Optional[str] = Field(default=None, description="Cache generation timestamp.")
    message: Optional[str] = Field(default=None, description="Status or error message.")
