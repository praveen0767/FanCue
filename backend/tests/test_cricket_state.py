"""Tests for deterministic state snapshot and delta calculation logic."""

import pytest

from backend.app.match_engine.state import (
    calculate_state_delta,
    calculate_state_snapshot,
)
from backend.app.schemas.cricket import (
    CricketDeliveryEvent,
    CricketDeliveryRuns,
    CricketWicket,
)


def make_delivery(
    over: int,
    ball: int,
    batter_runs: int = 1,
    extras_runs: int = 0,
    is_legal: bool = True,
    wicket_kind: str = None,
    legal_ball: int = None,
) -> CricketDeliveryEvent:
    wickets = None
    if wicket_kind:
        wickets = [CricketWicket(player_out="Batter", kind=wicket_kind)]
    if legal_ball is not None:
        lb_num = legal_ball
    else:
        lb_num = min(ball, 6) if is_legal else 0

    return CricketDeliveryEvent(
        event_id=f"test_ov{over}_b{ball}",
        match_id="test_match",
        innings=0,
        over=over,
        delivery_in_over=ball,
        legal_ball_number=lb_num,
        batter="Striker",
        bowler="Bowler",
        non_striker="NonStriker",
        runs=CricketDeliveryRuns(
            batter=batter_runs,
            extras=extras_runs,
            total=batter_runs + extras_runs,
        ),
        wickets=wickets,
    )


def test_calculate_state_snapshot_innings_start():
    """Sentinel -1 boundary must return clean 0-state snapshot."""
    deliveries = [make_delivery(over=0, ball=1, batter_runs=4)]
    snap = calculate_state_snapshot(deliveries, after_over=-1)
    assert snap.runs == 0
    assert snap.wickets == 0
    assert snap.overs_completed == 0
    assert snap.legal_balls_in_over == 0
    assert snap.run_rate == 0.0


def test_calculate_state_snapshot_completed_overs():
    """State snapshot after over 0 (human over 1)."""
    deliveries = [
        make_delivery(over=0, ball=1, batter_runs=1),
        make_delivery(over=0, ball=2, batter_runs=4),
        make_delivery(over=0, ball=3, batter_runs=0, wicket_kind="bowled"),
        make_delivery(over=0, ball=4, batter_runs=2),
        make_delivery(over=0, ball=5, batter_runs=1),
        make_delivery(over=0, ball=6, batter_runs=0),
    ]
    snap = calculate_state_snapshot(deliveries, after_over=0)
    assert snap.runs == 8
    assert snap.wickets == 1
    assert snap.overs_completed == 1
    assert snap.run_rate == 8.0


def test_calculate_state_snapshot_non_wicket_dismissal():
    """Dismissals such as 'retired hurt' must NOT increment wickets lost."""
    deliveries = [
        make_delivery(over=0, ball=1, batter_runs=2),
        make_delivery(over=0, ball=2, batter_runs=0, wicket_kind="retired hurt"),
    ]
    snap = calculate_state_snapshot(deliveries, after_over=0)
    assert snap.runs == 2
    assert snap.wickets == 0  # Retired hurt is not out


def test_calculate_state_delta():
    """State delta between two snapshot points."""
    delivs = [
        make_delivery(over=1, ball=1, batter_runs=4),
        make_delivery(over=1, ball=2, batter_runs=6),
        make_delivery(over=1, ball=3, batter_runs=0, wicket_kind="caught"),
        make_delivery(over=1, ball=4, batter_runs=1),
        make_delivery(over=1, ball=5, batter_runs=0, extras_runs=1, is_legal=False),
        make_delivery(over=1, ball=6, batter_runs=2),
        make_delivery(over=1, ball=7, batter_runs=1),
    ]
    start_snap = calculate_state_snapshot([], after_over=0)  # runs=0, overs=1
    end_snap = calculate_state_snapshot(delivs, after_over=1)  # over 1 complete (overs=2)

    delta = calculate_state_delta(start_snap, end_snap, delivs)
    assert delta.runs_added == 15  # 14 off bat + 1 extra
    assert delta.wickets_lost == 1
    assert delta.completed_overs_delta == 1
    assert delta.legal_balls_added == 6  # 6 legal balls + 1 wide
    assert delta.extras_added == 1
    assert delta.interval_run_rate == 15.0
