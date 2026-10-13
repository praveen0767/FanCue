"""Phase 1 — rule-based engine audit (backend/tests/test_phase1_engine_audit.py).

Every expected value is derived from ICC Laws of Cricket and the Cricsheet JSON
v1.3.0 spec, NOT from current engine output. Where a real fixture is used, the
expected numbers were independently computed from the raw JSON (derivation
transcript recorded in docs/plan/phase-10-phase-1-correctness-report.md).

Audit coverage:
- Wides / no-balls do not count as legal balls; byes / leg-byes do.
- A non-boundary four is not a boundary/six fact.
- Retired hurt / retired not out are NOT wickets; retired out IS a wicket and
  is not credited to the bowler.
- Penalty runs count towards extras and team total.
- Reduced-over targets: surfaced only when the source provides them; never invented.
- Boundary convention pinning on real fixture data (Cricsheet 'over' is 0-indexed).
"""

from datetime import datetime, timezone
import json
import os

import pytest

from backend.app.adapters.cricket.normalizer import normalize_innings_deliveries
from backend.app.match_engine.intervals import extract_key_facts, filter_interval_deliveries
from backend.app.match_engine.state import (
    NON_WICKET_DISMISSALS,
    calculate_state_snapshot,
    calculate_final_innings_snapshot,
)
from backend.app.schemas.cricket import (
    CricketCatchUpRequest,
    CricketDeliveryEvent,
    CricketDeliveryRuns,
    CricketInterval,
    CricketWicket,
)
from backend.app.schemas.evidence import FactType
from backend.app.schemas.provenance import PermittedUse, SourceProvenance

FIXTURE_1529229 = os.path.abspath("data/raw/1529229.json")
SHA256_1529229 = "8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f"


def _provenance():
    return SourceProvenance(
        source_id="cricsheet_historical_odi",
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=datetime.now(timezone.utc),
        dataset_revision="1",
        source_format="json",
        source_format_version="1.3.0",
        file_sha256=SHA256_1529229,
        license_name="ODC-By-1.0",
        license_url="http://opendatacommons.org/licenses/by/1.0/",
        attribution_text="Data provided by Cricsheet under ODC-By v1.0.",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
    )


def _norm(raw_innings, match_id="audit_match", index=0):
    root = {"innings": [raw_innings]}
    return normalize_innings_deliveries(root, match_id, index)


def _inn(overs):
    """Build a raw Cricsheet-style innings dict from compact over specs."""
    return {
        "team": "Team A",
        "overs": [{"over": i, "deliveries": d} for i, d in enumerate(overs)],
    }


def _d(batter="Striker A", bowler="Bowler B", batter_runs=1, extras=None, total=None):
    if total is None:
        total = batter_runs + (sum(extras.values()) if extras else 0)
    body = {
        "batter": batter,
        "bowler": bowler,
        "non_striker": "NonStriker",
        "runs": {"batter": batter_runs, "extras": sum(extras.values()) if extras else 0, "total": total},
    }
    if extras:
        body["extras"] = extras
    return body


# ─── Wides and no-balls do not consume a legal ball ───────────────────────────


class TestIllegalBallAccounting:
    """Laws 22 & 21: wides and no-balls are re-bowled; they are not one of the 6."""

    def test_wide_does_not_advance_legal_ball_count(self):
        """A wide followed by 2 legal balls → legal_ball_number of the third
        delivery must be 2, NOT 3."""
        raw = _inn([[
            _d(extras={"wides": 1}, total=2),
            _d(batter_runs=0),
            _d(batter_runs=1),
        ]])
        events = _norm(raw)
        legal_numbers = [e.legal_ball_number for e in events]
        assert legal_numbers == [0, 1, 2], f"Expected [0, 1, 2]; got {legal_numbers}"

    def test_noball_does_not_advance_legal_ball_count(self):
        """A no-ball followed by 2 legal balls → legal numbers [0, 1, 2]."""
        raw = _inn([[
            _d(extras={"noballs": 1}, total=2),
            _d(batter_runs=0),
            _d(batter_runs=1),
        ]])
        events = _norm(raw)
        assert [e.legal_ball_number for e in events] == [0, 1, 2]

    def test_over_with_one_wide_has_seven_deliveries_six_legal(self):
        raw = _inn([[_d(batter_runs=0, extras={"wides": 1}, total=1)] + [_d(batter_runs=0) for _ in range(6)]])
        events = _norm(raw)
        assert len(events) == 7
        assert sum(1 for e in events if e.legal_ball_number > 0) == 6


class TestByesAndLegByesAreLegal:
    """Byes/leg-byes (Law 23) are scored on legal deliveries."""

    def test_bye_and_legbye_count_as_legal_balls(self):
        raw = _inn([[
            _d(batter_runs=0, extras={"byes": 2}, total=2),
            _d(batter_runs=0, extras={"legbyes": 1}, total=1),
            _d(batter_runs=0),
            _d(batter_runs=0),
            _d(batter_runs=0),
            _d(batter_runs=0),
        ]])
        events = _norm(raw)
        assert all(e.legal_ball_number > 0 for e in events), "Byes must be legal balls"
        assert events[-1].legal_ball_number == 6

    def test_snapshot_counts_bye_runs_and_extras(self):
        deliveries = _norm(
            _inn([[
                _d(batter_runs=0, extras={"byes": 2}, total=2),
                _d(batter_runs=0, extras={"legbyes": 1}, total=1),
                _d(batter_runs=4),
            ]])
        )
        snap = calculate_state_snapshot(deliveries, after_over=0)
        assert snap.runs == 7          # hand: 0+2+1+4 = 7
        assert snap.extras_total == 3  # hand: 2 byes + 1 leg-bye
        assert snap.overs_completed == 1


class TestNonBoundaryFour:
    """The fact extractor must only treat batter_runs ≥ 6 as a six fact."""

    def test_six_fact_created_for_six_runs(self):
        deliveries = _norm(_inn([[_d(batter_runs=6)]]))
        facts = extract_key_facts("m", 0, "rev1", deliveries)
        assert any(f.fact_type == FactType.BOUNDARY for f in facts)

    def test_four_does_not_create_six_fact(self):
        deliveries = _norm(_inn([[_d(batter_runs=4)]]))
        facts = extract_key_facts("m", 0, "rev1", deliveries)
        assert [f for f in facts if f.fact_type == FactType.BOUNDARY] == [], (
            "Fours must not be extracted as six/boundary facts"
        )


# ─── Retired dismissals ───────────────────────────────────────────────────────


def _dismissal_delivery(kind: str, over: int = 2, ball: int = 3) -> CricketDeliveryEvent:
    return CricketDeliveryEvent(
        event_id=f"ev_{kind.replace(' ', '_')}_{over}_{ball}",
        match_id="m", innings=0, over=over, delivery_in_over=ball,
        legal_ball_number=ball, batter="Batter X", bowler="Bowler Y", non_striker="NS",
        runs=CricketDeliveryRuns(batter=1, extras=0, total=1),
        wickets=[CricketWicket(player_out="Batter X", kind=kind)],
    )


class TestRetiredDismissalSemantics:
    """ICC Law 25 + Cricsheet kinds: 'retired hurt', 'retired out', 'retired not out'."""

    def test_retired_hurt_is_not_a_wicket(self):
        assert "retired hurt" in NON_WICKET_DISMISSALS

    def test_retired_not_out_is_not_a_wicket(self):
        """A batter who retires NOT OUT has not been dismissed (Law 25.5)."""
        assert "retired not out" in NON_WICKET_DISMISSALS, (
            "'retired not out' must not count as a lost wicket"
        )

    def test_retired_out_is_a_wicket(self):
        assert "retired out" not in NON_WICKET_DISMISSALS

    def test_retired_hurt_produces_no_wicket_fact(self):
        """A 'retired hurt' record must not generate a WICKET evidence fact.

        CURRENTLY FAILING: extract_key_facts emits a WICKET fact for every
        d.wickets entry, including non-dismissal retired-hurt records.
        """
        facts = extract_key_facts("m", 0, "rev1", [_dismissal_delivery("retired hurt")])
        wicket_facts = [f for f in facts if f.fact_type == FactType.WICKET]
        assert wicket_facts == [], (
            "retired hurt must not generate a WICKET fact; got "
            f"{[f.description for f in wicket_facts]}"
        )

    def test_retired_out_wicket_fact_not_credited_to_bowler(self):
        facts = extract_key_facts("m", 0, "rev1", [_dismissal_delivery("retired out")])
        wicket_facts = [f for f in facts if f.fact_type == FactType.WICKET]
        assert len(wicket_facts) == 1
        assert "off bowling of" not in wicket_facts[0].description


# ─── Penalty runs (Law 41) ────────────────────────────────────────────────────


class TestPenaltyRuns:
    def test_penalty_runs_count_in_runs_and_extras(self):
        raw = _inn([[_d(batter_runs=0, extras={"penalty": 5}, total=5)]])
        events = _norm(raw)
        snap = calculate_state_snapshot(events, after_over=0)
        assert snap.runs == 5
        assert snap.extras_total == 5


# ─── Boundary convention & over indexing on real fixture data ────────────────


class TestBoundaryConventionOnRealFixture:
    """Cricsheet 'over' is 0-indexed ('over': 0 is the 1st over).

    FanCue request contract (docs/product/interval-model.md, ADR-008 and the
    CricketInterval docstring): start/end_after_over use the SAME 0-based source
    index. after_over = N ⇒ the state after all deliveries of 0-based over N ⇒
    N+1 user-facing completed overs.

    Suspected defect 1 claimed an interval ending 'after over 25' must not
    include the state after 26 completed overs. Under the documented 0-based
    contract, after_over=25 IS the state after 26 completed overs — the
    suspicion is a convention mis-reading, not a defect. These tests pin the
    convention so drift in either direction fails loudly.
    """

    @pytest.fixture(scope="class")
    def engine(self):
        from backend.app.match_engine.cricket import CricketMatchEngine
        return CricketMatchEngine.from_fixture(
            file_path=FIXTURE_1529229, match_id="1529229", provenance=_provenance(),
        )

    @staticmethod
    def _request(start, end, innings=0):
        return CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=innings, start_after_over=start, end_after_over=end),
        )

    def test_request_states_are_zero_based_inclusive(self, engine):
        request = self._request(14, 25)
        state_before, state_after, delta, _, _ = engine.reconstruct_interval(request)
        assert state_after.overs_completed == 26
        assert state_before.overs_completed == 15
        assert delta.completed_overs_delta == 11

    def test_state_at_25_excludes_over_index_26(self, engine):
        deliveries = engine.get_innings_events(0)
        within = filter_interval_deliveries(deliveries, 24, 25)
        assert {d.over for d in within} == {25}

        # Independent check against the raw JSON: a single-over request spanning
        # only over index 25 must equal the sum of that over's deliveries only.
        raw = json.load(open(FIXTURE_1529229, encoding="utf-8"))
        raw_runs_25 = sum(
            dd["runs"]["total"]
            for grp in raw["innings"][0]["overs"]
            if grp["over"] == 25
            for dd in grp["deliveries"]
        )
        req = self._request(24, 25)  # single-over interval: only over index 25
        assert engine.reconstruct_interval(req)[2].runs_added == raw_runs_25

    def test_fact_payloads_use_one_based_user_facing_overs(self, engine):
        """Facts describing source over index 14 call it 'over 15' (user-facing)."""
        _, _, _, facts, _ = engine.reconstruct_interval(self._request(13, 14))
        for f in facts:
            if "over" in f.structured_payload:
                assert f.structured_payload["over"] == 15, (
                    f"Payload over must be user-facing 1-based (source index 14 → 15); got "
                    f"{f.structured_payload['over']}"
                )


# ─── Innings limit and target authority (never invent a DLS target) ──────────


class TestInningsLimitAuthority:
    def test_engine_surfaces_source_target_for_chasing_innings(self):
        """Cricsheet innings 1 of 1529229 records target = {overs: 50, runs: 352}."""
        from backend.app.match_engine.cricket import CricketMatchEngine
        engine = CricketMatchEngine.from_fixture(
            file_path=FIXTURE_1529229, match_id="1529229", provenance=_provenance(),
        )
        target = engine.get_innings_target(1)
        assert target == {"overs": 50, "runs": 352}, (
            f"Authoritative target expected straight from source; got {target}"
        )

    def test_engine_returns_none_when_source_has_no_target(self):
        """Innings 0 has no target in the source; the engine must NOT invent one."""
        from backend.app.match_engine.cricket import CricketMatchEngine
        engine = CricketMatchEngine.from_fixture(
            file_path=FIXTURE_1529229, match_id="1529229", provenance=_provenance(),
        )
        assert engine.get_innings_target(0) is None


# ─── All-out / partial final over display (synthetic, hand-reasoned) ─────────


class TestInningsCompletionShapes:
    def test_display_notation_for_partial_final_over(self):
        """Innings ended mid-over displays as <full overs>.<balls>, e.g. 19.3 —
        NOT the nominal limit 20.0. (Suspected defect 3.)"""
        deliveries = _norm(
            _inn([[ _d(batter_runs=1) for _ in range(6)] for _ in range(19)]
                 + [[_d(batter_runs=1) for _ in range(3)]]),          # 3 balls of over 20
        )
        final = calculate_final_innings_snapshot(deliveries)
        assert final.overs_completed == 19
        assert final.legal_balls_in_over == 3
        assert f"{final.overs_completed}.{final.legal_balls_in_over}" == "19.3"

    def test_full_50_over_innings_display(self):
        deliveries = _norm(_inn([[_d(batter_runs=1) for _ in range(6)] for _ in range(50)]))
        final = calculate_final_innings_snapshot(deliveries)
        assert final.overs_completed == 50
        assert final.legal_balls_in_over == 0


# ─── Unknown / unsafe source data ────────────────────────────────────────────


class TestUnknownDataSafety:
    """Missing optional fields must surface an explicit safe limitation, not a
    fabricated value."""

    def test_missing_bowler_defaults_to_unknown(self):
        raw_over = [{"batter": "X", "runs": {"batter": 1, "extras": 0, "total": 1}}]
        events = _norm(_inn([raw_over]))
        assert events[0].bowler == "Unknown"
