"""Contract tests for CricketCatchUpRequest, CricketInterval, snapshots, and events."""

import pytest
from pydantic import ValidationError

from backend.app.schemas.common import (
    ExplanationDepth,
    LanguageCode,
    PerspectiveLens,
)
from backend.app.schemas.cricket import (
    CricketCatchUpRequest,
    CricketDeliveryEvent,
    CricketDeliveryRuns,
    CricketInterval,
    CricketScoreSnapshot,
    CricketStateDelta,
    CricketWicket,
)


def test_valid_whole_over_interval():
    """Valid interval between two whole overs."""
    interval = CricketInterval(innings=0, start_after_over=12, end_after_over=18)
    assert interval.innings == 0
    assert interval.start_after_over == 12
    assert interval.end_after_over == 18


def test_valid_interval_innings_start():
    """Boundary start at -1 represents the innings start."""
    interval = CricketInterval(innings=0, start_after_over=-1, end_after_over=5)
    assert interval.start_after_over == -1
    assert interval.end_after_over == 5


def test_invalid_interval_negative_boundary_other_than_sentinel():
    """Boundary < -1 is strictly invalid."""
    with pytest.raises(ValidationError) as exc:
        CricketInterval(innings=0, start_after_over=-2, end_after_over=10)
    assert "greater than or equal to -1" in str(exc.value)


def test_invalid_reversed_interval():
    """Start boundary after end boundary must be rejected."""
    with pytest.raises(ValidationError) as exc:
        CricketInterval(innings=0, start_after_over=18, end_after_over=12)
    assert "must be strictly greater than start_after_over" in str(exc.value)


def test_invalid_identical_interval_boundaries():
    """Identical start and end boundaries (zero length) must be rejected."""
    with pytest.raises(ValidationError) as exc:
        CricketInterval(innings=0, start_after_over=10, end_after_over=10)
    assert "must be strictly greater than start_after_over" in str(exc.value)


def test_decimal_float_over_prohibited():
    """Float over values (e.g. 12.4) must fail validation when passed as float or float string."""
    with pytest.raises(ValidationError):
        CricketInterval.model_validate({"innings": 0, "start_after_over": 12.4, "end_after_over": 18})


def test_valid_cricket_catchup_request():
    """Valid request with default lens and language."""
    req = CricketCatchUpRequest(
        match_id="1529229",
        interval=CricketInterval(innings=0, start_after_over=14, end_after_over=22),
    )
    assert req.match_id == "1529229"
    assert req.lens == PerspectiveLens.MATCH
    assert req.language == LanguageCode.EN
    assert req.explanation_depth == ExplanationDepth.STANDARD


def test_request_missing_match_id():
    """Missing match_id must fail validation."""
    with pytest.raises(ValidationError):
        CricketCatchUpRequest(
            interval=CricketInterval(innings=0, start_after_over=0, end_after_over=5),
        )


def test_request_negative_innings():
    """Negative innings number must be rejected."""
    with pytest.raises(ValidationError):
        CricketInterval(innings=-1, start_after_over=0, end_after_over=5)


def test_request_perspective_lens_requires_target_entity():
    """Team or player lens requires target_entity."""
    with pytest.raises(ValidationError) as exc:
        CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=0, end_after_over=5),
            lens=PerspectiveLens.TEAM,
            target_entity=None,
        )
    assert "target_entity is required when lens is 'team'" in str(exc.value)


def test_request_unsupported_language():
    """Unsupported language codes must be rejected."""
    with pytest.raises(ValidationError) as exc:
        CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=0, end_after_over=5),
            language="fr",  # Not supported
        )
    assert "Input should be 'en' or 'ta'" in str(exc.value)


def test_request_forbids_unexpected_fields():
    """Unknown fields must be rejected."""
    with pytest.raises(ValidationError):
        CricketCatchUpRequest.model_validate({
            "match_id": "1529229",
            "interval": {"innings": 0, "start_after_over": 0, "end_after_over": 5},
            "unsupported_extra": "hack",
        })


def test_cricket_score_snapshot():
    """Verify score snapshot constraints."""
    snap = CricketScoreSnapshot(
        runs=142,
        wickets=3,
        overs_completed=22,
        legal_balls_in_over=0,
        extras_total=6,
        run_rate=6.45,
    )
    assert snap.runs == 142
    assert snap.wickets == 3

    # Wickets exceeding 10 must fail
    with pytest.raises(ValidationError):
        CricketScoreSnapshot(runs=100, wickets=11, overs_completed=20)


def test_cricket_state_delta():
    """Verify state delta calculation container."""
    delta = CricketStateDelta(
        runs_added=53,
        wickets_lost=1,
        completed_overs_delta=8,
        legal_balls_added=48,
        extras_added=2,
        interval_run_rate=6.62,
    )
    assert delta.runs_added == 53
    assert delta.completed_overs_delta == 8


def test_cricket_delivery_event_normalized():
    """Verify delivery event schema with runs and wickets."""
    event = CricketDeliveryEvent(
        event_id="1529229_inn0_ov2_b3",
        match_id="1529229",
        innings=0,
        over=2,
        delivery_in_over=3,
        legal_ball_number=3,
        batter="Shubman Gill",
        bowler="JNT Seales",
        non_striker="RG Sharma",
        runs=CricketDeliveryRuns(batter=0, extras=0, total=0),
        wickets=[CricketWicket(player_out="Shubman Gill", kind="caught", fielders=["SD Hope"])],
    )
    assert event.legal_ball_number == 3
    assert event.wickets[0].kind == "caught"
