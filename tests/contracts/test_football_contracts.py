"""Contract tests for provisional football schemas."""

import pytest
from pydantic import ValidationError

from backend.app.schemas.common import LanguageCode, PerspectiveLens
from backend.app.schemas.football import (
    FootballCatchUpRequest,
    FootballInterval,
    FootballMatchEvent,
    FootballPeriod,
    FootballScoreSnapshot,
    FootballStateDelta,
)


def test_valid_football_interval():
    """Verify provisional football minute-based interval."""
    interval = FootballInterval(
        period=FootballPeriod.FIRST_HALF,
        start_minute=15,
        end_minute=35,
    )
    assert interval.period == FootballPeriod.FIRST_HALF
    assert interval.start_minute == 15
    assert interval.end_minute == 35


def test_invalid_football_interval_reversed():
    """Football interval with end_minute <= start_minute must fail validation."""
    with pytest.raises(ValidationError) as exc:
        FootballInterval(
            period=FootballPeriod.SECOND_HALF,
            start_minute=60,
            end_minute=45,
        )
    assert "must be strictly greater than start_minute" in str(exc.value)


def test_invalid_football_interval_identical():
    """Identical minute boundaries must fail validation."""
    with pytest.raises(ValidationError):
        FootballInterval(
            period=FootballPeriod.FIRST_HALF,
            start_minute=30,
            end_minute=30,
        )


def test_valid_football_catchup_request():
    """Verify provisional football catch-up request."""
    req = FootballCatchUpRequest(
        match_id="fb_match_1001",
        interval=FootballInterval(
            period=FootballPeriod.SECOND_HALF,
            start_minute=55,
            end_minute=72,
        ),
        lens=PerspectiveLens.MATCH,
        language=LanguageCode.EN,
    )
    assert req.match_id == "fb_match_1001"
    assert req.interval.start_minute == 55


def test_football_match_event():
    """Verify provisional football match event representation."""
    ev = FootballMatchEvent(
        event_id="fb_ev_goal_1",
        match_id="fb_match_1001",
        period=FootballPeriod.FIRST_HALF,
        minute=23,
        second=45,
        event_type="goal",
        team="Arsenal",
        player="Bukayo Saka",
    )
    assert ev.event_type == "goal"
    assert ev.minute == 23


def test_football_schemas_do_not_accept_cricket_fields():
    """Enforce architectural isolation: cricket over fields must be rejected by football schemas."""
    with pytest.raises(ValidationError):
        FootballCatchUpRequest.model_validate({
            "match_id": "fb_1001",
            "interval": {
                "period": "first_half",
                "start_minute": 0,
                "end_minute": 45,
                "after_over": 10,  # Cricket concept
            },
        })
