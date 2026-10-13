"""Normalization logic for raw Cricket Data API payloads.

Sanitizes and maps raw API responses into typed, bounded domain models without
inventing missing data.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.app.adapters.cricket_data.models import (
    CricketDataInningsScore,
    CricketDataMatchItem,
    CricketDataTeamInfo,
)

logger = logging.getLogger(__name__)


def parse_innings_score(raw_score: Dict[str, Any]) -> Optional[CricketDataInningsScore]:
    """Parse a single innings score block safely."""
    if not isinstance(raw_score, dict):
        return None

    try:
        raw_r = raw_score.get("r", 0)
        runs = int(raw_r) if raw_r is not None else 0
    except (ValueError, TypeError):
        runs = 0

    try:
        raw_w = raw_score.get("w", 0)
        wickets = int(raw_w) if raw_w is not None else 0
    except (ValueError, TypeError):
        wickets = 0

    try:
        raw_o = raw_score.get("o", 0.0)
        overs = float(raw_o) if raw_o is not None else 0.0
    except (ValueError, TypeError):
        overs = 0.0

    inning_name = str(raw_score.get("inning", "") or "").strip()

    return CricketDataInningsScore(
        r=runs,
        w=wickets,
        o=overs,
        inning=inning_name,
    )


def normalize_match_item(
    raw: Dict[str, Any],
    retrieved_at: str,
) -> Optional[CricketDataMatchItem]:
    """Normalize a raw match entry into a CricketDataMatchItem.

    Returns None if mandatory identifiers (id, name) cannot be resolved.
    """
    if not isinstance(raw, dict):
        return None

    match_id = str(raw.get("id") or "").strip()
    if not match_id:
        return None

    name = str(raw.get("name") or "").strip()
    match_type = str(raw.get("matchType") or "cricket").strip().lower()
    status = str(raw.get("status") or "Scheduled").strip()
    venue = raw.get("venue")
    if venue:
        venue = str(venue).strip()

    date_str = str(raw.get("date") or "").strip()
    if not date_str:
        # Fall back to date part of retrieved_at if missing
        date_str = retrieved_at[:10]

    date_time_gmt = raw.get("dateTimeGMT")
    if date_time_gmt:
        date_time_gmt = str(date_time_gmt).strip()

    # Teams array
    teams_raw = raw.get("teams") or []
    teams: List[str] = []
    if isinstance(teams_raw, list):
        teams = [str(t).strip() for t in teams_raw if t]

    if not name and len(teams) >= 2:
        name = f"{teams[0]} vs {teams[1]}"
    elif not name:
        name = f"Match {match_id}"

    # Team info
    team_info: List[CricketDataTeamInfo] = []
    team_info_raw = raw.get("teamInfo") or []
    if isinstance(team_info_raw, list):
        for ti in team_info_raw:
            if isinstance(ti, dict) and ti.get("name"):
                team_info.append(
                    CricketDataTeamInfo(
                        name=str(ti.get("name")),
                        shortname=str(ti.get("shortname")) if ti.get("shortname") else None,
                        img=str(ti.get("img")) if ti.get("img") else None,
                    )
                )

    # Scores array
    scores: List[CricketDataInningsScore] = []
    scores_raw = raw.get("score") or []
    if isinstance(scores_raw, list):
        for s in scores_raw:
            parsed = parse_innings_score(s)
            if parsed:
                scores.append(parsed)

    series_id = raw.get("series_id")
    if series_id:
        series_id = str(series_id).strip()

    match_started = bool(raw.get("matchStarted", False))
    match_ended = bool(raw.get("matchEnded", False))

    return CricketDataMatchItem(
        id=match_id,
        name=name,
        match_type=match_type,
        status=status,
        venue=venue or None,
        date=date_str,
        date_time_gmt=date_time_gmt or None,
        teams=teams,
        team_info=team_info,
        score=scores,
        series_id=series_id or None,
        match_started=match_started,
        match_ended=match_ended,
        retrieved_at=retrieved_at,
    )
