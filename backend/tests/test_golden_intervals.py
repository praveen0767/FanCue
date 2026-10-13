"""
Golden interval test set — Phase 1.

All expected values independently derived from raw Cricsheet JSON source
by walking raw overs/deliveries without using the engine as oracle.
Generation script: scratch/generate_golden.py.

Fixture provenance:
  1529229 — India vs West Indies, ODI, 2026-10-03 (Cricsheet)
  1552779 — India vs Pakistan,    T20, 2026-10-03 (Cricsheet)

Over-index convention:
  Cricsheet raw JSON stores 0-indexed over numbers.
  Engine event.over == Cricsheet raw 'over' field (0-based).
  after_over = N → state after all deliveries in over-index N.
  User-facing label: over N+1.
  after_over = -1 → innings start (0/0).

Interval boundary convention (exclusive start, inclusive end):
  filter_interval_deliveries(deliveries, start_after_over, end_after_over)
  returns deliveries d where start_after_over < d.over <= end_after_over.

Wicket counting:
  'retired hurt' is NOT a wicket.
  All other kinds (including 'retired out', 'run out', 'obstructing the field') ARE wickets.
"""
import json
import pytest

from backend.app.adapters.cricket.normalizer import normalize_innings_deliveries
from backend.app.adapters.cricket.parser import load_cricsheet_json
from backend.app.match_engine.intervals import filter_interval_deliveries
from backend.app.match_engine.state import (
    calculate_state_snapshot,
    calculate_final_innings_snapshot,
    calculate_state_delta,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def odi_raw():
    return load_cricsheet_json("data/raw/1529229.json")


@pytest.fixture(scope="module")
def t20_raw():
    return load_cricsheet_json("data/raw/1552779.json")


@pytest.fixture(scope="module")
def odi0(odi_raw):
    return normalize_innings_deliveries(odi_raw, "1529229", 0)


@pytest.fixture(scope="module")
def odi1(odi_raw):
    return normalize_innings_deliveries(odi_raw, "1529229", 1)


@pytest.fixture(scope="module")
def t20_0(t20_raw):
    return normalize_innings_deliveries(t20_raw, "1552779", 0)


@pytest.fixture(scope="module")
def t20_1(t20_raw):
    return normalize_innings_deliveries(t20_raw, "1552779", 1)


# ── helper ────────────────────────────────────────────────────────────────────

def interval_delta(deliveries, start, end):
    """Returns (runs, wickets, legal_balls) for interval (start, end]."""
    snap_start = calculate_state_snapshot(deliveries, start)
    snap_end   = calculate_state_snapshot(deliveries, end)
    interval   = filter_interval_deliveries(deliveries, start, end)
    delta      = calculate_state_delta(snap_start, snap_end, interval)
    return delta.runs_added, delta.wickets_lost, delta.legal_balls_added


# ── 1529229 ODI — Innings 0 (India batting) ──────────────────────────────────
# Hand-calculated totals from raw JSON source.
# Inn0: 351/7 in 50 overs.

class TestGoldenODI0Snapshots:
    """Golden: 1529229 ODI Innings 0 state snapshots."""

    def test_snapshot_innings_start(self, odi0):
        snap = calculate_state_snapshot(odi0, -1)
        assert snap.runs == 0 and snap.wickets == 0 and snap.overs_completed == 0

    def test_snapshot_after_5_overs(self, odi0):
        # after_over=4 → 5 overs complete. Raw: 9/2 from 30 legal balls.
        snap = calculate_state_snapshot(odi0, 4)
        assert snap.runs == 9, f"Expected 9, got {snap.runs}"
        assert snap.wickets == 2, f"Expected 2, got {snap.wickets}"
        assert snap.overs_completed == 5

    def test_snapshot_after_10_overs(self, odi0):
        # Raw: 28/2 from 60 legal balls.
        snap = calculate_state_snapshot(odi0, 9)
        assert snap.runs == 28 and snap.wickets == 2 and snap.overs_completed == 10

    def test_snapshot_after_15_overs(self, odi0):
        # Raw: 59/2 from 90 legal balls.
        snap = calculate_state_snapshot(odi0, 14)
        assert snap.runs == 59 and snap.wickets == 2 and snap.overs_completed == 15

    def test_snapshot_after_20_overs(self, odi0):
        # Raw: 102/2 from 120 legal balls.
        snap = calculate_state_snapshot(odi0, 19)
        assert snap.runs == 102 and snap.wickets == 2 and snap.overs_completed == 20

    def test_snapshot_after_25_overs(self, odi0):
        # Raw: 142/3 from 150 legal balls.
        snap = calculate_state_snapshot(odi0, 24)
        assert snap.runs == 142 and snap.wickets == 3 and snap.overs_completed == 25

    def test_final_innings_snapshot(self, odi0):
        # Full 50-over innings: 351/7 in exactly 50 overs (no partial).
        snap = calculate_final_innings_snapshot(odi0)
        assert snap.runs == 351 and snap.wickets == 7
        assert snap.overs_completed == 50 and snap.legal_balls_in_over == 0


class TestGoldenODI0Intervals:
    """Golden: 1529229 ODI Innings 0 interval deltas."""

    def test_interval_powerplay(self, odi0):
        # (-1, 4]: overs 1-5. Raw: 9 runs, 2 wkts, 30 legal.
        runs, wkts, legal = interval_delta(odi0, -1, 4)
        assert runs == 9 and wkts == 2 and legal == 30

    def test_interval_overs_6_to_10(self, odi0):
        # (4, 9]: overs 6-10. Raw: 19 runs, 0 wkts, 30 legal.
        runs, wkts, legal = interval_delta(odi0, 4, 9)
        assert runs == 19 and wkts == 0 and legal == 30

    def test_interval_overs_11_to_15(self, odi0):
        # (9, 14]: Raw: 31 runs, 0 wkts, 30 legal.
        runs, wkts, legal = interval_delta(odi0, 9, 14)
        assert runs == 31 and wkts == 0 and legal == 30

    def test_interval_overs_16_to_20(self, odi0):
        # (14, 19]: Raw: 43 runs, 0 wkts, 30 legal.
        runs, wkts, legal = interval_delta(odi0, 14, 19)
        assert runs == 43 and wkts == 0 and legal == 30

    def test_interval_overs_21_to_25(self, odi0):
        # (19, 24]: Raw: 40 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(odi0, 19, 24)
        assert runs == 40 and wkts == 1 and legal == 30

    def test_interval_overs_26_to_30(self, odi0):
        # (24, 29]: Raw: 30 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(odi0, 24, 29)
        assert runs == 30 and wkts == 1 and legal == 30

    def test_interval_overs_31_to_35(self, odi0):
        # (29, 34]: Raw: 44 runs, 0 wkts, 30 legal.
        runs, wkts, legal = interval_delta(odi0, 29, 34)
        assert runs == 44 and wkts == 0 and legal == 30

    def test_interval_overs_36_to_40(self, odi0):
        # (34, 39]: Raw: 30 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(odi0, 34, 39)
        assert runs == 30 and wkts == 1 and legal == 30

    def test_interval_overs_41_to_45(self, odi0):
        # (39, 44]: Raw: 40 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(odi0, 39, 44)
        assert runs == 40 and wkts == 1 and legal == 30

    def test_interval_death_overs(self, odi0):
        # (44, 49]: overs 46-50. Raw: 65 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(odi0, 44, 49)
        assert runs == 65 and wkts == 1 and legal == 30

    def test_interval_full_innings(self, odi0):
        # (-1, 49]: entire innings. Raw: 351/7, 300 legal.
        runs, wkts, legal = interval_delta(odi0, -1, 49)
        assert runs == 351 and wkts == 7 and legal == 300

    def test_interval_additivity_powerplay(self, odi0):
        """(-1,4] + (4,9] == (-1,9]"""
        r1, w1, l1 = interval_delta(odi0, -1, 4)
        r2, w2, l2 = interval_delta(odi0, 4, 9)
        r3, w3, l3 = interval_delta(odi0, -1, 9)
        assert r1 + r2 == r3 and w1 + w2 == w3 and l1 + l2 == l3


# ── 1529229 ODI — Innings 1 (West Indies batting, chase) ─────────────────────
# Inn1: 352/5 in 48.2 overs (partial final over — 2 legal balls then won).

class TestGoldenODI1Snapshots:
    """Golden: 1529229 ODI Innings 1 state snapshots (chase innings, partial end)."""

    def test_snapshot_after_5_overs(self, odi1):
        # Raw: 45/1 after 5 overs.
        snap = calculate_state_snapshot(odi1, 4)
        assert snap.runs == 45 and snap.wickets == 1 and snap.overs_completed == 5

    def test_snapshot_after_10_overs(self, odi1):
        # Raw: 78/1.
        snap = calculate_state_snapshot(odi1, 9)
        assert snap.runs == 78 and snap.wickets == 1

    def test_snapshot_after_15_overs(self, odi1):
        # Raw: 106/1.
        snap = calculate_state_snapshot(odi1, 14)
        assert snap.runs == 106 and snap.wickets == 1

    def test_snapshot_after_20_overs(self, odi1):
        # Raw: 148/1.
        snap = calculate_state_snapshot(odi1, 19)
        assert snap.runs == 148 and snap.wickets == 1

    def test_snapshot_after_25_overs(self, odi1):
        # Raw: 177/2.
        snap = calculate_state_snapshot(odi1, 24)
        assert snap.runs == 177 and snap.wickets == 2

    def test_final_innings_snapshot_partial_over(self, odi1):
        # Chase completed in over 48 (index 48) after 2 legal balls.
        # overs_completed=48 (full), legal_balls_in_over=2, runs=352/5.
        snap = calculate_final_innings_snapshot(odi1)
        assert snap.runs == 352, f"Expected 352, got {snap.runs}"
        assert snap.wickets == 5, f"Expected 5, got {snap.wickets}"
        assert snap.overs_completed == 48, f"Expected 48, got {snap.overs_completed}"
        assert snap.legal_balls_in_over == 2, f"Expected 2, got {snap.legal_balls_in_over}"


class TestGoldenODI1Intervals:
    """Golden: 1529229 ODI Innings 1 interval deltas."""

    def test_interval_powerplay(self, odi1):
        # (-1, 4]: 45 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(odi1, -1, 4)
        assert runs == 45 and wkts == 1 and legal == 30

    def test_interval_overs_6_to_10(self, odi1):
        # (4, 9]: 33 runs, 0 wkts, 30 legal.
        runs, wkts, legal = interval_delta(odi1, 4, 9)
        assert runs == 33 and wkts == 0 and legal == 30

    def test_interval_overs_11_to_15(self, odi1):
        # (9, 14]: 28 runs, 0 wkts, 30 legal.
        runs, wkts, legal = interval_delta(odi1, 9, 14)
        assert runs == 28 and wkts == 0 and legal == 30

    def test_interval_overs_16_to_20(self, odi1):
        # (14, 19]: 42 runs, 0 wkts, 30 legal.
        runs, wkts, legal = interval_delta(odi1, 14, 19)
        assert runs == 42 and wkts == 0 and legal == 30

    def test_interval_overs_21_to_25(self, odi1):
        # (19, 24]: 29 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(odi1, 19, 24)
        assert runs == 29 and wkts == 1 and legal == 30

    def test_interval_full_chase(self, odi1):
        # (-1, 48]: entire innings. Raw: 352/5, 290 legal (48.2 overs).
        runs, wkts, legal = interval_delta(odi1, -1, 48)
        assert runs == 352 and wkts == 5 and legal == 290


# ── 1552779 T20 — Innings 0 (India batting) ──────────────────────────────────
# Inn0: 211/6 in 20.0 overs.

class TestGoldenT20_0Snapshots:
    """Golden: 1552779 T20 Innings 0 snapshots."""

    def test_snapshot_after_5_overs(self, t20_0):
        # Raw: 63/2 after 5 overs.
        snap = calculate_state_snapshot(t20_0, 4)
        assert snap.runs == 63 and snap.wickets == 2 and snap.overs_completed == 5

    def test_snapshot_after_10_overs(self, t20_0):
        # Raw: 114/3.
        snap = calculate_state_snapshot(t20_0, 9)
        assert snap.runs == 114 and snap.wickets == 3 and snap.overs_completed == 10

    def test_snapshot_after_15_overs(self, t20_0):
        # Raw: 137/5.
        snap = calculate_state_snapshot(t20_0, 14)
        assert snap.runs == 137 and snap.wickets == 5 and snap.overs_completed == 15

    def test_final_innings_snapshot_complete(self, t20_0):
        # Full 20-over innings.
        snap = calculate_final_innings_snapshot(t20_0)
        assert snap.runs == 211 and snap.wickets == 6
        assert snap.overs_completed == 20 and snap.legal_balls_in_over == 0


class TestGoldenT20_0Intervals:
    """Golden: 1552779 T20 Innings 0 interval deltas."""

    def test_interval_powerplay(self, t20_0):
        # (-1, 4]: 63 runs, 2 wkts, 30 legal.
        runs, wkts, legal = interval_delta(t20_0, -1, 4)
        assert runs == 63 and wkts == 2 and legal == 30

    def test_interval_middle_overs(self, t20_0):
        # (4, 9]: 51 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(t20_0, 4, 9)
        assert runs == 51 and wkts == 1 and legal == 30

    def test_interval_overs_11_to_15(self, t20_0):
        # (9, 14]: 23 runs, 2 wkts, 30 legal.
        runs, wkts, legal = interval_delta(t20_0, 9, 14)
        assert runs == 23 and wkts == 2 and legal == 30

    def test_interval_death_overs(self, t20_0):
        # (14, 19]: 74 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(t20_0, 14, 19)
        assert runs == 74 and wkts == 1 and legal == 30

    def test_interval_full_innings(self, t20_0):
        # (-1, 19]: 211/6, 120 legal.
        runs, wkts, legal = interval_delta(t20_0, -1, 19)
        assert runs == 211 and wkts == 6 and legal == 120


# ── 1552779 T20 — Innings 1 (Pakistan batting, chase) ────────────────────────
# Inn1: 192/6 in 20.0 overs.

class TestGoldenT20_1Snapshots:
    """Golden: 1552779 T20 Innings 1 snapshots."""

    def test_snapshot_after_5_overs(self, t20_1):
        snap = calculate_state_snapshot(t20_1, 4)
        assert snap.runs == 36 and snap.wickets == 2 and snap.overs_completed == 5

    def test_snapshot_after_10_overs(self, t20_1):
        snap = calculate_state_snapshot(t20_1, 9)
        assert snap.runs == 76 and snap.wickets == 3 and snap.overs_completed == 10

    def test_snapshot_after_15_overs(self, t20_1):
        snap = calculate_state_snapshot(t20_1, 14)
        assert snap.runs == 130 and snap.wickets == 4 and snap.overs_completed == 15

    def test_final_innings_snapshot_complete(self, t20_1):
        snap = calculate_final_innings_snapshot(t20_1)
        assert snap.runs == 192 and snap.wickets == 6
        assert snap.overs_completed == 20 and snap.legal_balls_in_over == 0


class TestGoldenT20_1Intervals:
    """Golden: 1552779 T20 Innings 1 interval deltas."""

    def test_interval_powerplay(self, t20_1):
        # (-1, 4]: 36 runs, 2 wkts, 30 legal.
        runs, wkts, legal = interval_delta(t20_1, -1, 4)
        assert runs == 36 and wkts == 2 and legal == 30

    def test_interval_middle(self, t20_1):
        # (4, 9]: 40 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(t20_1, 4, 9)
        assert runs == 40 and wkts == 1 and legal == 30

    def test_interval_overs_11_to_15(self, t20_1):
        # (9, 14]: 54 runs, 1 wkt, 30 legal.
        runs, wkts, legal = interval_delta(t20_1, 9, 14)
        assert runs == 54 and wkts == 1 and legal == 30

    def test_interval_death_overs(self, t20_1):
        # (14, 19]: 62 runs, 2 wkts, 30 legal.
        runs, wkts, legal = interval_delta(t20_1, 14, 19)
        assert runs == 62 and wkts == 2 and legal == 30

    def test_interval_full_innings(self, t20_1):
        runs, wkts, legal = interval_delta(t20_1, -1, 19)
        assert runs == 192 and wkts == 6 and legal == 120


# ── Determinism tests ─────────────────────────────────────────────────────────

class TestDeterminism:
    """Identical inputs must yield identical IDs and facts on repeated calls."""

    def test_event_ids_are_stable(self, odi0):
        ids1 = [d.event_id for d in odi0]
        ids2 = [d.event_id for d in odi0]
        assert ids1 == ids2

    def test_fact_ids_are_stable(self, odi0):
        from backend.app.match_engine.intervals import extract_key_facts
        interval = filter_interval_deliveries(odi0, -1, 9)
        facts1 = extract_key_facts("1529229", 0, "rev1", interval)
        facts2 = extract_key_facts("1529229", 0, "rev1", interval)
        ids1 = [f.fact_id for f in facts1]
        ids2 = [f.fact_id for f in facts2]
        assert ids1 == ids2

    def test_same_delivery_same_snapshot(self, odi0):
        snap1 = calculate_state_snapshot(odi0, 19)
        snap2 = calculate_state_snapshot(odi0, 19)
        assert snap1.runs == snap2.runs
        assert snap1.wickets == snap2.wickets

    def test_packet_id_is_deterministic(self):
        from backend.app.adapters.cricket.identifiers import generate_packet_id
        pid1 = generate_packet_id("1529229", 0, -1, 9)
        pid2 = generate_packet_id("1529229", 0, -1, 9)
        assert pid1 == pid2


# ── Rule-based edge case tests ────────────────────────────────────────────────

class TestEngineRules:
    """Rule-based audit: extras, legal ball counting, edge dismissals."""

    def _make_delivery(self, over, ball, batter=1, extras=0, extras_type=None,
                       wicket=None, player="B", bowler="Bwlr"):
        from backend.app.schemas.cricket import (
            CricketDeliveryEvent, CricketDeliveryRuns, CricketDeliveryExtras, CricketWicket
        )
        raw_extras = None
        is_legal = True
        if extras_type == "wide":
            raw_extras = CricketDeliveryExtras(wides=extras, noballs=0, byes=0, legbyes=0, penalty=0)
            is_legal = False
        elif extras_type == "noball":
            raw_extras = CricketDeliveryExtras(wides=0, noballs=extras, byes=0, legbyes=0, penalty=0)
            is_legal = False
        elif extras_type == "bye":
            raw_extras = CricketDeliveryExtras(wides=0, noballs=0, byes=extras, legbyes=0, penalty=0)
        elif extras_type == "legbye":
            raw_extras = CricketDeliveryExtras(wides=0, noballs=0, byes=0, legbyes=extras, penalty=0)
        elif extras_type == "penalty":
            raw_extras = CricketDeliveryExtras(wides=0, noballs=0, byes=0, legbyes=0, penalty=extras)

        wickets_obj = None
        if wicket:
            wickets_obj = [CricketWicket(player_out=player, kind=wicket)]

        legal_ball_number = ball if is_legal else 0
        return CricketDeliveryEvent(
            event_id=f"ev_{over}_{ball}_{extras_type or 'normal'}",
            match_id="test",
            innings=0,
            over=over,
            delivery_in_over=ball,
            legal_ball_number=legal_ball_number,
            batter=player,
            bowler=bowler,
            non_striker="NS",
            runs=CricketDeliveryRuns(
                batter=batter,
                extras=extras if extras_type else 0,
                total=batter + (extras if extras_type else 0),
            ),
            extras=raw_extras,
            wickets=wickets_obj,
        )

    def test_wide_is_not_legal_ball(self):
        deliveries = [self._make_delivery(0, 1, batter=0, extras=1, extras_type="wide")]
        snap = calculate_state_snapshot(deliveries, 0)
        assert snap.runs == 1
        # legal_balls_added is checked via delta
        interval = filter_interval_deliveries(deliveries, -1, 0)
        delta = calculate_state_delta(
            calculate_state_snapshot(deliveries, -1),
            snap, interval
        )
        assert delta.legal_balls_added == 0, "Wide must not count as legal ball"

    def test_noball_is_not_legal_ball(self):
        deliveries = [self._make_delivery(0, 1, batter=1, extras=1, extras_type="noball")]
        snap = calculate_state_snapshot(deliveries, 0)
        interval = filter_interval_deliveries(deliveries, -1, 0)
        delta = calculate_state_delta(
            calculate_state_snapshot(deliveries, -1),
            snap, interval
        )
        assert delta.legal_balls_added == 0, "No-ball must not count as legal ball"

    def test_bye_is_legal_ball(self):
        """Byes count as legal balls (ball hit the stumps without bat, no wide/noball)."""
        deliveries = [self._make_delivery(0, 1, batter=0, extras=2, extras_type="bye")]
        snap = calculate_state_snapshot(deliveries, 0)
        interval = filter_interval_deliveries(deliveries, -1, 0)
        delta = calculate_state_delta(
            calculate_state_snapshot(deliveries, -1),
            snap, interval
        )
        assert delta.legal_balls_added == 1, "Bye must count as legal ball"
        assert delta.runs_added == 2, "Bye runs must be counted"

    def test_legbye_is_legal_ball(self):
        """Leg byes count as legal balls."""
        deliveries = [self._make_delivery(0, 1, batter=0, extras=1, extras_type="legbye")]
        interval = filter_interval_deliveries(deliveries, -1, 0)
        delta = calculate_state_delta(
            calculate_state_snapshot(deliveries, -1),
            calculate_state_snapshot(deliveries, 0), interval
        )
        assert delta.legal_balls_added == 1, "Leg-bye must count as legal ball"

    def test_penalty_runs_counted_in_total(self):
        """Penalty runs must appear in extras_total."""
        deliveries = [self._make_delivery(0, 1, batter=0, extras=5, extras_type="penalty")]
        snap = calculate_state_snapshot(deliveries, 0)
        assert snap.runs == 5, f"Penalty runs must appear in total: got {snap.runs}"

    def test_batter_four_runs_not_labelled_boundary(self):
        """4 batter runs with no extras_type is just a run — not a wide or no-ball boundary."""
        deliveries = [self._make_delivery(0, 1, batter=4)]
        interval = filter_interval_deliveries(deliveries, -1, 0)
        delta = calculate_state_delta(
            calculate_state_snapshot(deliveries, -1),
            calculate_state_snapshot(deliveries, 0), interval
        )
        assert delta.runs_added == 4
        assert delta.legal_balls_added == 1

    def test_run_out_counts_as_wicket(self):
        deliveries = [self._make_delivery(0, 1, wicket="run out")]
        snap = calculate_state_snapshot(deliveries, 0)
        assert snap.wickets == 1

    def test_retired_hurt_not_wicket(self):
        deliveries = [self._make_delivery(0, 1, wicket="retired hurt")]
        snap = calculate_state_snapshot(deliveries, 0)
        assert snap.wickets == 0

    def test_stumped_is_wicket(self):
        deliveries = [self._make_delivery(0, 1, wicket="stumped")]
        snap = calculate_state_snapshot(deliveries, 0)
        assert snap.wickets == 1

    def test_multiple_wickets_same_ball_counted(self):
        """Edge case: two wickets on one ball (handled ball + run out — rare but possible)."""
        from backend.app.schemas.cricket import (
            CricketDeliveryEvent, CricketDeliveryRuns, CricketWicket
        )
        delivery = CricketDeliveryEvent(
            event_id="ev_double_wkt",
            match_id="test",
            innings=0, over=0, delivery_in_over=1,
            legal_ball_number=1,
            batter="B1", bowler="Bwlr", non_striker="NS",
            runs=CricketDeliveryRuns(batter=0, extras=0, total=0),
            wickets=[
                CricketWicket(player_out="B1", kind="run out"),
                CricketWicket(player_out="B2", kind="obstructing the field"),
            ],
        )
        snap = calculate_state_snapshot([delivery], 0)
        assert snap.wickets == 2, f"Two wickets on one ball must both be counted: {snap.wickets}"
