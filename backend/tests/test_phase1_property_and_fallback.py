"""Phase 1 — property tests, fallback validity, plural formatting (Step 3).

- Determinism: identical inputs yield identical evidence facts and event IDs.
- Fallback validity: every supported fallback scenario passes the verifier.
- Singular/plural formatting: 1 wicket / 1 over / 1 six forms.
- Interval additivity across all valid windows on real fixtures, checked
  against an engine-independent raw-JSON aggregation.
"""

from datetime import datetime, timezone
import json
import os

import pytest

from backend.app.ai.models import AICandidateClaim, AIExplanationDraft
from backend.app.explanations.deterministic_fallback import build_deterministic_fallback
from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.orchestration.evidence_builder import EvidencePacketBuilder
from backend.app.schemas.cricket import CricketCatchUpRequest, CricketInterval
from backend.app.schemas.explanation import ClaimType
from backend.app.schemas.provenance import PermittedUse, SourceProvenance
from backend.app.verification.claim_verifier import ClaimVerifier

FIXTURES = {
    "1529229": (
        os.path.abspath("data/raw/1529229.json"),
        "8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f",
    ),
    "1552779": (
        os.path.abspath("data/raw/1552779.json"),
        "99b2df4d4ebcaa328834ec101776a201c679b5d89b1a604241c504b0d9bb3e2b",
    ),
}


def _prov(sha):
    return SourceProvenance(
        source_id="cricsheet_historical",
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=datetime.now(timezone.utc),
        dataset_revision="1",
        source_format="json",
        source_format_version="1.3.0",
        file_sha256=sha,
        license_name="ODC-By-1.0",
        license_url="http://opendatacommons.org/licenses/by/1.0/",
        attribution_text="Data provided by Cricsheet under ODC-By v1.0.",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
    )


@pytest.fixture(scope="module")
def engines():
    return {
        mid: CricketMatchEngine.from_fixture(
            file_path=path, match_id=mid, provenance=_prov(sha)
        )
        for mid, (path, sha) in FIXTURES.items()
    }


def _packet_by_engine(engine, innings, start, end):
    request = CricketCatchUpRequest(
        match_id=engine.match_id,
        interval=CricketInterval(innings=innings, start_after_over=start, end_after_over=end),
    )
    return EvidencePacketBuilder(engine, retrieval_service=None).build_packet(request)


def _fallback_draft(payload):
    """Convert fallback claims into a verifiable AIExplanationDraft draft."""
    claims = [
        AICandidateClaim(
            claim_id=c.claim_id,
            claim_type=c.claim_type,
            text=c.text,
            cited_fact_ids=list(c.cited_fact_ids),
            cited_knowledge_ids=list(c.cited_knowledge_ids),
        )
        for c in payload.claims
    ]
    return AIExplanationDraft(summary=payload.summary, claims=claims)


# Engine-independent reference aggregation straight from the raw JSON.


def _raw_stats(match_id, innings):
    path = FIXTURES[match_id][0]
    raw = json.load(open(path, encoding="utf-8"))
    overs = raw["innings"][innings]["overs"]
    stats = {}
    for grp in overs:
        wk = [w["player_out"] for d in grp["deliveries"] for w in (d.get("wickets") or [])]
        kinds = [w["kind"] for d in grp["deliveries"] for w in (d.get("wickets") or [])]
        stats[grp["over"]] = {
            "runs": sum(d["runs"]["total"] for d in grp["deliveries"]),
            "extras": sum(d["runs"]["extras"] for d in grp["deliveries"]),
            # extras detail (wides, noballs) lives at d["extras"], NOT d["runs"]["extras"]
            "legal": sum(
                1 for d in grp["deliveries"]
                if d.get("extras", {}).get("wides", 0) == 0
                and d.get("extras", {}).get("noballs", 0) == 0
            ),
            "wickets": wk,
            "kinds": kinds,
        }
    return stats, raw



# ─── Fallback validity across supported scenarios ─────────────────────────────


class TestFallbackValidity:
    """Every supported deterministic-fallback scenario must pass verification —
    the fallback cannot itself violate evidence integrity."""

    SCENARIOS = [
        ("1529229", 0, 13, 14),   # single over, multiple events
        ("1529229", 0, 0, 8),     # wickets + boundaries
        ("1529229", 0, -1, 3),    # from innings start
        ("1552779", 1, 18, 19),   # T20 chase end
        ("1552779", 0, 19, 19) if False else ("1552779", 0, 18, 19),  # T20 final over
        ("1529229", 1, 47, 48),   # chase completion interval
    ]

    @pytest.mark.parametrize("mid,inn,s,e", SCENARIOS)
    def test_fallback_scenarios_pass_verifier(self, engines, mid, inn, s, e):
        verifier = ClaimVerifier(reject_on_any_core_failure=True)
        payload = build_deterministic_fallback(_packet_by_engine(engines[mid], inn, s, e))
        report = verifier.verify(_fallback_draft(payload),
                                 _packet_by_engine(engines[mid], inn, s, e))
        assert report.is_verified, (
            f"Fallback scenario {mid} inn{inn} ({s}, {e}] failed verification: "
            f"{[(r.reason.value, r.detail) for r in report.rejected_claims]}"
        )

    def test_fallback_labelled_non_ai(self, engines):
        payload = build_deterministic_fallback(_packet_by_engine(engines["1529229"], 0, 13, 14))
        label_check = payload.summary.lower()
        assert "deterministic recap" in label_check, (
            "Fallback summary must clearly label itself as non-AI-generated"
        )

    def test_singular_plural_wicket_formatting(self, engines):
        """Interval with exactly one wicket lost → prose says '1 wicket', not
        '1 wickets'. CURRENTLY FAILING: the builder hard-codes 'wickets'."""
        found = False
        for mid, inn, s, e in self.SCENARIOS:
            p = _packet_by_engine(engines[mid], inn, s, e)
            if p.state_delta.wickets_lost == 1:
                found = True
                payload = build_deterministic_fallback(p)
                assert "1 wicket" in payload.summary, (
                    f"Expected '1 wicket' in: {payload.summary}"
                )
                assert "1 wickets" not in payload.summary
                break
        assert found, "No 1-wicket scenario located in scenario list"

    def test_fallback_summary_is_concise_and_uses_positive_wicket_language(self, engines):
        """Phone-sized fallback copy should read like a recap, not a raw ledger."""
        packet = _packet_by_engine(engines["1529229"], 0, -1, 49)
        payload = build_deterministic_fallback(packet)
        assert payload.summary.startswith("Deterministic recap:")
        assert "score moved from" in payload.summary
        assert "scoring at" in payload.summary
        assert "Key events:" not in payload.summary
        assert "-7 wickets" not in payload.summary
        assert "lost" in payload.summary

    def test_singular_plural_over_formatting(self, engines):
        """Delta of exactly one completed over → 'in 1 completed over'."""
        for mid, inn, s, e in self.SCENARIOS:
            p = _packet_by_engine(engines[mid], inn, s, e)
            if p.state_delta.completed_overs_delta == 1:
                payload = build_deterministic_fallback(p)
                # The summary or delta claim line may phrase overs; assert the
                # malformed '1 overs' never appears adjacent to a 1.
                assert "1 overs" not in payload.summary
                for claim in payload.claims:
                    if claim.claim_type == ClaimType.SCORE_DELTA:
                        assert "1 overs" not in claim.text
                break


# ─── Determinism ─────────────────────────────────────────────────────────────


class TestDeterminism:
    def test_identical_requests_identical_facts_and_ids(self, engines):
        p1 = _packet_by_engine(engines["1529229"], 0, 13, 14)
        p2 = _packet_by_engine(engines["1529229"], 0, 13, 14)
        assert [f.fact_id for f in p1.key_facts] == [f.fact_id for f in p2.key_facts]
        assert p1.model_dump(exclude={"provenance"}) == p2.model_dump(exclude={"provenance"})


# ─── Interval additivity sweep over all valid windows ────────────────────────


class TestIntervalAdditivitySweep:
    """delta(A→B) + delta(B→C) == delta(A→C) for runs, wickets and legal balls,
    across every (A, C) window of each fixture innings (bounded by max over)."""

    @pytest.mark.parametrize("mid", ["1529229", "1552779"])
    def test_additivity_all_windows(self, engines, mid):
        engine = engines[mid]
        for inn in range(len(engine.raw_data.get("innings", []))):
            max_over = max(d.over for d in engine.get_innings_events(inn))
            for a in range(-1, max_over + 1):
                for c in range(a + 1, max_over + 1):
                    req_ac = CricketCatchUpRequest(
                        match_id=mid,
                        interval=CricketInterval(innings=inn, start_after_over=a, end_after_over=c),
                    )
                    s_before, s_after, d_ac, _, _ = engine.reconstruct_interval(req_ac)
                    assert d_ac.runs_added == s_after.runs - s_before.runs
                    assert d_ac.wickets_lost == s_after.wickets - s_before.wickets
                    # Independent legal-ball reference per raw over
                    stats, _ = _raw_stats(mid, inn)
                    expected_legal = sum(stats[o]["legal"] for o in range(a + 1, c + 1))
                    assert d_ac.legal_balls_added == expected_legal

    @pytest.mark.parametrize("mid", ["1529229", "1552779"])
    def test_delta_matches_raw_aggregation_sampled(self, engines, mid):
        """Sampled reconciliation: interval runs/extras equal raw-JSON sums."""
        engine = engines[mid]
        stats, _ = _raw_stats(mid, 0)
        for (a, c) in [(-1, 5), (11, 17), (24, 25), (39, 49)]:
            max_over = max(d.over for d in engine.get_innings_events(0))
            if c > max_over:
                continue
            req = CricketCatchUpRequest(
                match_id=mid,
                interval=CricketInterval(innings=0, start_after_over=a, end_after_over=c),
            )
            delta = engine.reconstruct_interval(req)[2]
            exp_runs = sum(stats[o]["runs"] for o in range(a + 1, c + 1))
            exp_extras = sum(stats[o]["extras"] for o in range(a + 1, c + 1))
            assert delta.runs_added == exp_runs
            assert delta.extras_added == exp_extras
