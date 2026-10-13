"""Deterministic state snapshot and interval delta calculations."""

from typing import List

from backend.app.schemas.cricket import (
    CricketDeliveryEvent,
    CricketScoreSnapshot,
    CricketStateDelta,
)

# Dismissal kinds that DO NOT count as a lost wicket under ICC Laws of Cricket
# Sources: ICC Laws of Cricket — Law 30.3/40 and Law 25 (retired):
#   * retired hurt    — batter left the field injured; may resume; not dismissed.
#   * retired not out — batter left the field with permission, not dismissed.
# Every other recorded dismissal kind (including 'retired out', 'timed out',
# 'handled the ball') counts as a lost wicket.
NON_WICKET_DISMISSALS = frozenset({"retired hurt", "retired not out"})


def calculate_state_snapshot(
    deliveries: List[CricketDeliveryEvent],
    after_over: int,
) -> CricketScoreSnapshot:
    """Calculate the authoritative score state at a specified whole-over boundary.
    
    Args:
        deliveries: Chronologically ordered delivery events for an entire innings.
        after_over: -1 denotes innings start (0 runs, 0 wickets).
                    N >= 0 denotes state after all deliveries of 0-based over N.
                    
    Returns:
        CricketScoreSnapshot with runs, wickets, completed overs, and run rate.
    """
    if after_over == -1:
        return CricketScoreSnapshot(
            runs=0,
            wickets=0,
            overs_completed=0,
            legal_balls_in_over=0,
            extras_total=0,
            run_rate=0.0,
        )

    # Filter all deliveries bowled up to and including after_over
    filtered = [d for d in deliveries if d.over <= after_over]

    total_runs = sum(d.runs.total for d in filtered)
    total_extras = sum(d.runs.extras for d in filtered)

    wickets_lost = 0
    for d in filtered:
        if d.wickets:
            for w in d.wickets:
                if w.kind.strip().lower() not in NON_WICKET_DISMISSALS:
                    wickets_lost += 1

    overs_completed = after_over + 1
    run_rate = round(total_runs / overs_completed, 2) if overs_completed > 0 else 0.0

    return CricketScoreSnapshot(
        runs=total_runs,
        wickets=wickets_lost,
        overs_completed=overs_completed,
        legal_balls_in_over=0,
        extras_total=total_extras,
        run_rate=run_rate,
    )


def calculate_state_delta(
    start_snapshot: CricketScoreSnapshot,
    end_snapshot: CricketScoreSnapshot,
    interval_deliveries: List[CricketDeliveryEvent],
) -> CricketStateDelta:
    """Compute the deterministic state difference between start and end boundaries.
    
    Args:
        start_snapshot: State at start boundary (exclusive).
        end_snapshot: State at end boundary (inclusive).
        interval_deliveries: Exact subset of deliveries bowled during the interval.
        
    Returns:
        CricketStateDelta containing runs added, wickets lost, and interval metrics.
    """
    runs_added = end_snapshot.runs - start_snapshot.runs
    wickets_lost = end_snapshot.wickets - start_snapshot.wickets
    completed_overs_delta = end_snapshot.overs_completed - start_snapshot.overs_completed

    # Count legal deliveries in the interval (legal_ball_number > 0)
    legal_balls_added = sum(1 for d in interval_deliveries if d.legal_ball_number > 0)
    extras_added = end_snapshot.extras_total - start_snapshot.extras_total

    interval_run_rate = (
        round(runs_added / completed_overs_delta, 2)
        if completed_overs_delta > 0
        else 0.0
    )

    return CricketStateDelta(
        runs_added=runs_added,
        wickets_lost=wickets_lost,
        completed_overs_delta=completed_overs_delta,
        legal_balls_added=legal_balls_added,
        extras_added=extras_added,
        interval_run_rate=interval_run_rate,
    )


def calculate_final_innings_snapshot(
    deliveries: List[CricketDeliveryEvent],
) -> "CricketScoreSnapshot":
    """Calculate the authoritative state at the true end of an innings.

    Unlike calculate_state_snapshot(deliveries, max_over), this function
    correctly records legal_balls_in_over for innings that ended mid-over
    (e.g., all-out after 2 balls in the final over shows legal_balls_in_over=2,
    overs_completed=<full overs completed>).

    Args:
        deliveries: All chronologically ordered delivery events for the innings.

    Returns:
        CricketScoreSnapshot with overs_completed reflecting ONLY fully completed
        overs, and legal_balls_in_over reflecting balls in the partial final over
        (0 when the innings ended on a whole-over boundary).
    """
    if not deliveries:
        return CricketScoreSnapshot(
            runs=0,
            wickets=0,
            overs_completed=0,
            legal_balls_in_over=0,
            extras_total=0,
            run_rate=0.0,
        )

    total_runs = sum(d.runs.total for d in deliveries)
    total_extras = sum(d.runs.extras for d in deliveries)

    wickets_lost = 0
    for d in deliveries:
        if d.wickets:
            for w in d.wickets:
                if w.kind.strip().lower() not in NON_WICKET_DISMISSALS:
                    wickets_lost += 1

    max_over = max(d.over for d in deliveries)

    # Count legal balls in the final over
    legal_in_last = sum(
        1 for d in deliveries
        if d.over == max_over and d.legal_ball_number > 0
    )

    # Determine whether the final over was completed (6 legal balls)
    if legal_in_last >= 6:
        # Whole-over boundary: the final over is complete
        overs_completed = max_over + 1
        legal_balls_in_over = 0
    else:
        # Partial final over: innings ended before the over was complete
        overs_completed = max_over  # only fully completed overs
        legal_balls_in_over = legal_in_last

    total_overs_for_rr = overs_completed + (legal_balls_in_over / 6.0)
    run_rate = round(total_runs / total_overs_for_rr, 2) if total_overs_for_rr > 0 else 0.0

    return CricketScoreSnapshot(
        runs=total_runs,
        wickets=wickets_lost,
        overs_completed=overs_completed,
        legal_balls_in_over=legal_balls_in_over,
        extras_total=total_extras,
        run_rate=run_rate,
    )

