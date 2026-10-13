"""FastAPI routers — match listing and interval discovery.

GET /matches
    Return all available fixture-backed matches (no invented data).

GET /matches/{match_id}/intervals
    Return valid innings/interval options from the actual cricket engine.
"""

from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.app.adapters.cricket_data.client import get_cricket_data_client
from backend.app.adapters.cricket_data.models import (
    CricketDataMatchesResponse,
    CricketDataScorecardResponse,
)
from backend.app.core.fixtures import get_engine, get_match_descriptor, list_available_match_ids
from backend.app.match_engine.errors import InningsIndexOutOfBoundsError
from backend.app.schemas.common import MatchDescriptor
from backend.app.schemas.errors import ErrorCode, ErrorDetail, ErrorResponse

router = APIRouter(tags=["matches"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MatchListResponse(BaseModel):
    """List of available historical match fixtures."""

    model_config = ConfigDict(frozen=True)

    matches: List[MatchDescriptor] = Field(..., description="Fixture-backed match descriptors.")
    total: int = Field(..., ge=0, description="Total number of available matches.")


class InningsIntervalOption(BaseModel):
    """One discrete interval option within a specific innings."""

    model_config = ConfigDict(frozen=True)

    innings: int = Field(..., ge=0, description="0-based innings index.")
    start_after_over: int = Field(..., ge=-1, description="Interval start (exclusive).")
    end_after_over: int = Field(..., ge=0, description="Interval end (inclusive).")
    label: str = Field(..., description="Human-readable description of the interval.")


class IntervalsResponse(BaseModel):
    """Valid interval options for a given match, derived from actual engine data."""

    model_config = ConfigDict(frozen=True)

    match_id: str = Field(...)
    intervals: List[InningsIntervalOption] = Field(
        ..., description="Enumerated valid intervals."
    )
    total_innings: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/matches", response_model=MatchListResponse, summary="List available matches")
def list_matches() -> MatchListResponse:
    """Return all matches backed by fixture files in data/raw/.

    Only verified Cricsheet JSON files are included. No data is invented.
    """
    ids = list_available_match_ids()
    descriptors: List[MatchDescriptor] = []
    for mid in ids:
        desc = get_match_descriptor(mid)
        if desc is not None:
            descriptors.append(desc)

    return MatchListResponse(matches=descriptors, total=len(descriptors))


@router.get(
    "/matches/near-live",
    response_model=CricketDataMatchesResponse,
    summary="List near-live matches from CricketData.org",
)
def list_near_live_matches(
    offset: int = Query(0, ge=0, description="Pagination offset"),
    refresh: bool = Query(False, description="Bypass cache and force fresh request"),
) -> CricketDataMatchesResponse:
    """Return near-live match discovery results from CricketData.org.

    Separated strictly from Cricsheet historical fixtures.
    Responses are cached in-memory and rate-limited to stay within quotas.
    """
    client = get_cricket_data_client()
    return client.get_current_matches(offset=offset, force_refresh=refresh)


@router.get(
    "/matches/near-live/{match_id}/scorecard",
    response_model=CricketDataScorecardResponse,
    summary="Get near-live match scorecard",
)
def get_near_live_scorecard(
    match_id: str,
    refresh: bool = Query(False, description="Bypass cache and force fresh request"),
) -> CricketDataScorecardResponse:
    """Return scorecard for a near-live match from CricketData.org."""
    client = get_cricket_data_client()
    return client.get_match_scorecard(match_id=match_id, force_refresh=refresh)



@router.get(
    "/matches/{match_id}/intervals",
    response_model=IntervalsResponse,
    summary="List valid intervals for a match",
    responses={
        404: {"model": ErrorResponse, "description": "Match not found."},
    },
)
def list_intervals(match_id: str) -> IntervalsResponse:
    """Return valid innings and interval options derived from the actual cricket engine.

    Interval boundaries are whole-over integer values consistent with the
    CricketInterval contract: start_after_over is exclusive, end_after_over is inclusive,
    and -1 denotes innings start.

    Only intervals within the recorded match progression are returned.
    """
    engine = get_engine(match_id)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.MATCH_NOT_FOUND,
                    message=f"Match '{match_id}' is not available in the fixture registry.",
                    field="match_id",
                ),
                correlation_id="api-intervals-" + match_id,
            ).model_dump(mode="json"),
        )

    total_innings = len(engine.raw_data.get("innings", []))
    options: List[InningsIntervalOption] = []

    for inns_idx in range(total_innings):
        try:
            deliveries = engine.get_innings_events(inns_idx)
        except InningsIndexOutOfBoundsError:
            continue
        if not deliveries:
            continue

        max_over = max(d.over for d in deliveries)

        # Build options: from innings start to each over in steps
        # Offer: start→5, start→10, start→15, ... up to max_over
        # Plus any middle sub-interval (e.g. over 5→10) for longer matches
        step = 5
        boundaries = list(range(0, max_over + 1, step))
        if max_over not in boundaries:
            boundaries.append(max_over)

        # Innings-start intervals: -1 → each boundary
        for end in boundaries:
            if end == 0:
                continue
            label = f"Innings {inns_idx + 1}: start → after over {end}"
            options.append(
                InningsIntervalOption(
                    innings=inns_idx,
                    start_after_over=-1,
                    end_after_over=end,
                    label=label,
                )
            )

        # Mid-innings intervals: boundary pairs
        for i in range(len(boundaries) - 1):
            s, e = boundaries[i], boundaries[i + 1]
            if e <= s:
                continue
            label = f"Innings {inns_idx + 1}: overs {s + 1}–{e}"
            options.append(
                InningsIntervalOption(
                    innings=inns_idx,
                    start_after_over=s,
                    end_after_over=e,
                    label=label,
                )
            )

    return IntervalsResponse(
        match_id=match_id,
        intervals=options,
        total_innings=total_innings,
    )
