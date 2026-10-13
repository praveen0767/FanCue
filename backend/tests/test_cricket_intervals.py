"""Tests for interval delivery filtering and deterministic fact extraction."""

import pytest

from backend.app.match_engine.errors import InvalidIntervalError
from backend.app.match_engine.intervals import (
    extract_key_facts,
    filter_interval_deliveries,
)
from backend.app.schemas.cricket import (
    CricketDeliveryEvent,
    CricketDeliveryRuns,
    CricketWicket,
)
from backend.app.schemas.evidence import FactType


def make_delivery(
    over: int,
    ball: int,
    batter_runs: int = 1,
    wicket_kind: str = None,
) -> CricketDeliveryEvent:
    wickets = None
    if wicket_kind:
        wickets = [CricketWicket(player_out=f"Player_{over}_{ball}", kind=wicket_kind)]
    return CricketDeliveryEvent(
        event_id=f"ev_ov{over}_b{ball}",
        match_id="test_match",
        innings=0,
        over=over,
        delivery_in_over=ball,
        legal_ball_number=ball,
        batter="Batter",
        bowler="Bowler",
        non_striker="NonStriker",
        runs=CricketDeliveryRuns(batter=batter_runs, extras=0, total=batter_runs),
        wickets=wickets,
    )


def test_filter_interval_deliveries_inclusive_exclusive():
    """Verify exclusive start, inclusive end."""
    deliveries = [
        make_delivery(over=12, ball=1),
        make_delivery(over=13, ball=1),
        make_delivery(over=14, ball=1),
        make_delivery(over=18, ball=6),
        make_delivery(over=19, ball=1),
    ]
    # Interval (12, 18] -> includes overs 13, 14, 18
    filtered = filter_interval_deliveries(deliveries, start_after_over=12, end_after_over=18)
    overs = [d.over for d in filtered]
    assert 12 not in overs
    assert 13 in overs
    assert 14 in overs
    assert 18 in overs
    assert 19 not in overs


def test_filter_interval_from_innings_start():
    """Interval starting at -1 includes over 0."""
    deliveries = [
        make_delivery(over=0, ball=1),
        make_delivery(over=1, ball=1),
    ]
    filtered = filter_interval_deliveries(deliveries, start_after_over=-1, end_after_over=0)
    assert len(filtered) == 1
    assert filtered[0].over == 0


def test_filter_interval_invalid_progression():
    """end_after_over <= start_after_over raises InvalidIntervalError."""
    with pytest.raises(InvalidIntervalError):
        filter_interval_deliveries([], start_after_over=15, end_after_over=10)

    with pytest.raises(InvalidIntervalError):
        filter_interval_deliveries([], start_after_over=10, end_after_over=10)


def test_filter_interval_start_less_than_sentinel():
    """start_after_over < -1 raises InvalidIntervalError."""
    with pytest.raises(InvalidIntervalError):
        filter_interval_deliveries([], start_after_over=-2, end_after_over=5)


def test_extract_key_facts_wickets_and_sixes():
    """Verify deterministic fact extraction for wickets and sixes."""
    deliveries = [
        make_delivery(over=2, ball=3, batter_runs=0, wicket_kind="caught"),
        make_delivery(over=2, ball=4, batter_runs=6),
    ]
    facts = extract_key_facts("match_1", 0, "rev1", deliveries)
    assert len(facts) >= 2

    wicket_facts = [f for f in facts if f.fact_type == FactType.WICKET]
    boundary_facts = [f for f in facts if f.fact_type == FactType.BOUNDARY]

    assert len(wicket_facts) == 1
    assert "caught" in wicket_facts[0].description
    assert wicket_facts[0].referenced_event_ids == ["ev_ov2_b3"]

    assert len(boundary_facts) == 1
    assert "6" in boundary_facts[0].description


def test_extract_key_facts_over_summaries():
    """Verify maiden and high-scoring over fact generation."""
    # Maiden over (6 balls, 0 runs)
    maiden_delivs = [make_delivery(over=3, ball=b, batter_runs=0) for b in range(1, 7)]
    # Big over (yielding >= 15 runs)
    big_delivs = [make_delivery(over=4, ball=b, batter_runs=3) for b in range(1, 7)]  # 18 runs

    facts = extract_key_facts("match_1", 0, "rev1", maiden_delivs + big_delivs)
    summaries = [f for f in facts if f.fact_type == FactType.OVER_SUMMARY]
    assert len(summaries) == 2

    descriptions = [s.description for s in summaries]
    assert any("MAIDEN" in d for d in descriptions)
    assert any("HIGH-SCORING" in d for d in descriptions)
