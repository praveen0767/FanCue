"""
Phase 1 regression tests — Cricket correctness, evidence integrity.

Each test was written BEFORE the corresponding fix was applied.
Tests marked BUG_REPRO reproduce confirmed defects from probe_defects.py.

Defects confirmed:
- BUG-01: Run-out wicket descriptions incorrectly say "off bowling of <bowler>".
- BUG-02: Obstructing-the-field and hit-wicket not credited to bowler but were
          included in "off bowling of" prose.
- BUG-03: retired_out should count as a wicket (ICC Laws). It was missing from
          NON_WICKET_DISMISSALS which only excluded 'retired hurt'. The set name
          is inverted — it lists dismissals that are NOT wickets.
- BUG-04: overs_completed is always after_over+1 even for partial final overs,
          hiding actual balls bowled when an innings ends mid-over.

Dismissal kinds NOT credited to the bowler (ICC Law 24.4):
  run out, obstructing the field (fielding side), retired out, retired hurt,
  timed out, hit the ball twice (the striker did it, not the bowler).
Dismissal kinds credited to the bowler:
  bowled, caught, lbw, stumped, handled the ball, hit wicket.
"""

import pytest

from backend.app.match_engine.intervals import extract_key_facts
from backend.app.match_engine.state import (
    NON_WICKET_DISMISSALS,
    calculate_state_snapshot,
)
from backend.app.schemas.cricket import (
    CricketDeliveryEvent,
    CricketDeliveryRuns,
    CricketWicket,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def make_delivery(
    over: int,
    ball: int,
    batter_runs: int = 1,
    extras_runs: int = 0,
    is_legal: bool = True,
    wicket_kind: str = None,
    player_out: str = "Batter",
    bowler: str = "Bowler",
) -> CricketDeliveryEvent:
    wickets = None
    if wicket_kind:
        wickets = [CricketWicket(player_out=player_out, kind=wicket_kind)]
    legal_ball_number = ball if is_legal else 0
    return CricketDeliveryEvent(
        event_id=f"ev_{over}_{ball}",
        match_id="test_match",
        innings=0,
        over=over,
        delivery_in_over=ball,
        legal_ball_number=legal_ball_number,
        batter=player_out if wicket_kind else "Striker",
        bowler=bowler,
        non_striker="NonStriker",
        runs=CricketDeliveryRuns(
            batter=batter_runs,
            extras=extras_runs,
            total=batter_runs + extras_runs,
        ),
        wickets=wickets,
    )


# ─── BUG-01: Run-out description must NOT mention "off bowling of" ─────────────

class TestRunOutBowlerCredit:
    """BUG-01: run out should not attribute the dismissal to the bowler."""

    def test_run_out_description_omits_bowling_credit(self):
        """FAILING before fix: description must not say 'off bowling of'."""
        d = make_delivery(over=5, ball=3, wicket_kind="run out",
                          player_out="A Kamboj", bowler="AS Joseph")
        facts = extract_key_facts("m1", 0, "rev1", [d])
        wicket_facts = [f for f in facts if "WICKET" in f.description]
        assert len(wicket_facts) == 1, "Expected exactly one wicket fact"
        desc = wicket_facts[0].description
        assert "off bowling of" not in desc, (
            f"Run-out description incorrectly attributes bowler: {desc!r}"
        )

    def test_run_out_structured_payload_has_no_bowler(self):
        """FAILING before fix: run-out payload must not contain a 'bowler' key."""
        d = make_delivery(over=5, ball=3, wicket_kind="run out",
                          player_out="A Kamboj", bowler="AS Joseph")
        facts = extract_key_facts("m1", 0, "rev1", [d])
        wicket_facts = [f for f in facts if "WICKET" in f.description]
        payload = wicket_facts[0].structured_payload
        assert "bowler" not in payload, (
            f"Run-out payload should not include bowler key: {payload}"
        )

    def test_obstructing_field_description_omits_bowling_credit(self):
        """Obstructing-the-field: fielding-side, not bowler's dismissal."""
        d = make_delivery(over=10, ball=2, wicket_kind="obstructing the field",
                          player_out="Player X", bowler="Bowler Y")
        facts = extract_key_facts("m1", 0, "rev1", [d])
        wicket_facts = [f for f in facts if "WICKET" in f.description]
        assert len(wicket_facts) == 1
        desc = wicket_facts[0].description
        assert "off bowling of" not in desc, (
            f"Obstructing-the-field description incorrectly attributes bowler: {desc!r}"
        )

    def test_bowler_credited_dismissals_keep_bowling_credit(self):
        """Caught, bowled, lbw, stumped, hit wicket MUST retain 'off bowling of'."""
        for kind in ("caught", "bowled", "lbw", "stumped", "hit wicket"):
            d = make_delivery(over=3, ball=4, wicket_kind=kind,
                              player_out="Batter", bowler="Bowler")
            facts = extract_key_facts("m1", 0, "rev1", [d])
            wicket_facts = [f for f in facts if "WICKET" in f.description]
            assert len(wicket_facts) == 1, f"Expected wicket fact for kind={kind}"
            desc = wicket_facts[0].description
            assert "off bowling of" in desc, (
                f"Bowler-credited kind '{kind}' must include 'off bowling of' in: {desc!r}"
            )

    def test_run_out_fact_description_includes_kind(self):
        """Run-out description must still include the dismissal kind."""
        d = make_delivery(over=5, ball=3, wicket_kind="run out",
                          player_out="A Kamboj", bowler="AS Joseph")
        facts = extract_key_facts("m1", 0, "rev1", [d])
        wicket_facts = [f for f in facts if "WICKET" in f.description]
        desc = wicket_facts[0].description
        assert "run out" in desc.lower(), (
            f"Description must mention the dismissal kind: {desc!r}"
        )
        assert "A Kamboj" in desc, f"Description must name the dismissed player: {desc!r}"


# ─── BUG-02: retired out IS a wicket ─────────────────────────────────────────

class TestRetiredOutIsWicket:
    """BUG-02: 'retired out' is a wicket under ICC laws and must decrement."""

    def test_retired_out_counts_as_wicket(self):
        """FAILING before fix: retired_out must increment wickets_lost."""
        deliveries = [
            make_delivery(over=0, ball=1, batter_runs=2),
            make_delivery(over=0, ball=2, batter_runs=0, wicket_kind="retired out"),
        ]
        snap = calculate_state_snapshot(deliveries, after_over=0)
        assert snap.wickets == 1, (
            f"'retired out' must count as a wicket, got {snap.wickets}"
        )

    def test_retired_hurt_does_not_count_as_wicket(self):
        """Regression: 'retired hurt' must still NOT count as a wicket."""
        deliveries = [
            make_delivery(over=0, ball=1, batter_runs=2),
            make_delivery(over=0, ball=2, batter_runs=0, wicket_kind="retired hurt"),
        ]
        snap = calculate_state_snapshot(deliveries, after_over=0)
        assert snap.wickets == 0, (
            f"'retired hurt' must NOT count as a wicket, got {snap.wickets}"
        )

    def test_non_wicket_dismissals_set_contents(self):
        """NON_WICKET_DISMISSALS must contain 'retired hurt' but NOT 'retired out'."""
        assert "retired hurt" in NON_WICKET_DISMISSALS
        assert "retired out" not in NON_WICKET_DISMISSALS, (
            "'retired out' is a wicket and must not be in NON_WICKET_DISMISSALS"
        )

    def test_timed_out_counts_as_wicket(self):
        """Timed out is a wicket (Law 40). Must increment wickets_lost."""
        deliveries = [make_delivery(over=0, ball=1, wicket_kind="timed out")]
        snap = calculate_state_snapshot(deliveries, after_over=0)
        assert snap.wickets == 1, (
            f"'timed out' must count as a wicket, got {snap.wickets}"
        )

    def test_handled_ball_counts_as_wicket(self):
        """Handled the ball (now part of obstructing the field) counts as wicket."""
        deliveries = [make_delivery(over=0, ball=1, wicket_kind="handled the ball")]
        snap = calculate_state_snapshot(deliveries, after_over=0)
        assert snap.wickets == 1, (
            f"'handled the ball' must count as a wicket, got {snap.wickets}"
        )


# ─── BUG-03: Partial final over representation ───────────────────────────────

class TestPartialOverRepresentation:
    """BUG-03: when an innings ends mid-over, the snapshot must record
       legal_balls_in_over correctly, not just max_over+1.
    """

    def _make_partial_over(self, over_idx: int, num_legal: int):
        """Generate num_legal balls in over_idx (simulating innings end mid-over)."""
        return [
            make_delivery(over=over_idx, ball=b, is_legal=True)
            for b in range(1, num_legal + 1)
        ]

    def test_completed_over_has_zero_partial_balls(self):
        """A complete 6-ball over: legal_balls_in_over must be 0 (whole-over boundary)."""
        deliveries = [make_delivery(over=0, ball=b) for b in range(1, 7)]
        snap = calculate_state_snapshot(deliveries, after_over=0)
        assert snap.legal_balls_in_over == 0, (
            f"Whole-over boundary should have legal_balls_in_over=0, got {snap.legal_balls_in_over}"
        )

    def test_partial_final_over_records_balls_bowled(self):
        """If innings ends after 2 legal balls in the final over,
           legal_balls_in_over must reflect 2, not 0."""
        # 5 complete overs + partial 6th (2 balls)
        deliveries = []
        for ov in range(5):
            deliveries.extend(make_delivery(over=ov, ball=b) for b in range(1, 7))
        # Partial over 5 — 2 legal balls then innings ends
        deliveries.extend(self._make_partial_over(5, 2))

        # Snapshot at the whole-over boundary (over 4 = 5 complete overs)
        snap_at_5 = calculate_state_snapshot(deliveries, after_over=4)
        assert snap_at_5.legal_balls_in_over == 0, (
            "Whole-over boundary snap must have legal_balls_in_over=0"
        )

        # Snapshot that includes partial over 5 — engine should record partial balls
        # This uses the max-delivery snapshot helper (reconstruct_completed_innings)
        # We test state.py directly:
        from backend.app.match_engine.state import calculate_final_innings_snapshot
        final_snap = calculate_final_innings_snapshot(deliveries)
        assert final_snap.legal_balls_in_over == 2, (
            f"Partial final over must record 2 legal balls, got {final_snap.legal_balls_in_over}"
        )
        assert final_snap.overs_completed == 5, (
            f"overs_completed must be 5 (full overs), got {final_snap.overs_completed}"
        )

    def test_full_50_over_innings_has_zero_partial(self):
        """Full 50-over innings: legal_balls_in_over must be 0."""
        deliveries = []
        for ov in range(50):
            deliveries.extend(make_delivery(over=ov, ball=b) for b in range(1, 7))
        from backend.app.match_engine.state import calculate_final_innings_snapshot
        final_snap = calculate_final_innings_snapshot(deliveries)
        assert final_snap.legal_balls_in_over == 0
        assert final_snap.overs_completed == 50


# ─── Boundary convention explicit tests ──────────────────────────────────────

class TestBoundaryConvention:
    """Explicit tests for the after_over boundary definition."""

    def test_after_over_n_includes_exactly_over_n(self):
        """filter(24, 25] must yield only deliveries with over==25."""
        deliveries = [
            make_delivery(over=23, ball=1),
            make_delivery(over=24, ball=1),
            make_delivery(over=25, ball=1),
            make_delivery(over=26, ball=1),
        ]
        from backend.app.match_engine.intervals import filter_interval_deliveries
        filtered = filter_interval_deliveries(deliveries, 24, 25)
        overs = {d.over for d in filtered}
        assert overs == {25}, f"Expected only over=25, got {overs}"

    def test_snapshot_after_over_n_equals_n_plus_one_completed(self):
        """State snapshot after_over=N always reports overs_completed=N+1."""
        deliveries = [make_delivery(over=ov, ball=b) for ov in range(10) for b in range(1, 7)]
        for n in range(10):
            snap = calculate_state_snapshot(deliveries, after_over=n)
            assert snap.overs_completed == n + 1, (
                f"after_over={n} should give overs_completed={n + 1}, got {snap.overs_completed}"
            )

    def test_filter_from_minus_one_includes_over_zero(self):
        """Interval (-1, 0] must include over 0 only."""
        from backend.app.match_engine.intervals import filter_interval_deliveries
        deliveries = [
            make_delivery(over=0, ball=1),
            make_delivery(over=1, ball=1),
        ]
        filtered = filter_interval_deliveries(deliveries, -1, 0)
        assert len(filtered) == 1
        assert filtered[0].over == 0


# ─── Interval additivity property tests ──────────────────────────────────────

class TestIntervalAdditivity:
    """Property: delta(A→B) + delta(B→C) == delta(A→C) for runs, wickets, legal balls."""

    def _make_deliveries(self):
        deliveries = []
        run_pattern = [1, 4, 0, 6, 2, 1, 0, 1, 3, 2, 0, 4, 1, 0, 6, 2, 1, 1]
        for ov in range(3):
            for b in range(1, 7):
                deliveries.append(make_delivery(over=ov, ball=b, batter_runs=run_pattern[(ov * 6 + b - 1) % len(run_pattern)]))
        return deliveries

    def test_additivity_runs(self):
        from backend.app.match_engine.intervals import filter_interval_deliveries
        from backend.app.match_engine.state import calculate_state_delta
        deliveries = self._make_deliveries()
        snap_m1 = calculate_state_snapshot(deliveries, -1)
        snap_1  = calculate_state_snapshot(deliveries, 1)
        snap_2  = calculate_state_snapshot(deliveries, 2)

        ivA = filter_interval_deliveries(deliveries, -1, 1)
        ivB = filter_interval_deliveries(deliveries, 1, 2)
        ivC = filter_interval_deliveries(deliveries, -1, 2)

        dA = calculate_state_delta(snap_m1, snap_1, ivA)
        dB = calculate_state_delta(snap_1, snap_2, ivB)
        dC = calculate_state_delta(snap_m1, snap_2, ivC)

        assert dA.runs_added + dB.runs_added == dC.runs_added, (
            f"Additivity failed: {dA.runs_added} + {dB.runs_added} != {dC.runs_added}"
        )
        assert dA.legal_balls_added + dB.legal_balls_added == dC.legal_balls_added

    def test_additivity_wickets(self):
        from backend.app.match_engine.intervals import filter_interval_deliveries
        from backend.app.match_engine.state import calculate_state_delta
        deliveries = [
            make_delivery(over=0, ball=1, wicket_kind="bowled"),
            make_delivery(over=0, ball=2),
            make_delivery(over=1, ball=1, wicket_kind="caught"),
            make_delivery(over=1, ball=2),
            make_delivery(over=2, ball=1),
        ]
        s_m1 = calculate_state_snapshot(deliveries, -1)
        s_0  = calculate_state_snapshot(deliveries, 0)
        s_1  = calculate_state_snapshot(deliveries, 1)
        s_2  = calculate_state_snapshot(deliveries, 2)

        d01 = calculate_state_delta(s_m1, s_1, filter_interval_deliveries(deliveries, -1, 1))
        d12 = calculate_state_delta(s_1, s_2, filter_interval_deliveries(deliveries, 1, 2))
        d02 = calculate_state_delta(s_m1, s_2, filter_interval_deliveries(deliveries, -1, 2))

        assert d01.wickets_lost + d12.wickets_lost == d02.wickets_lost
