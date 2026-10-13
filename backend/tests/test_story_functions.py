"""
Tests for deterministic story functions (Phase 1, Step 5).

All assertions use authoritative evidence packet inputs.
No invented narrative, player psychology, or speculative claims.
"""
import pytest

from backend.app.domain.story import (
    chapters,
    story_beats,
    headline,
    required_rate_arc,
    StoryBeat,
    RequiredRateArc,
    MAX_STORY_BEATS,
    MAX_WINDOW_OVERS,
)
from backend.app.schemas.cricket import CricketScoreSnapshot, CricketStateDelta
from backend.app.schemas.evidence import (
    EvidenceFact,
    FactType,
    MatchEvidencePacket,
)
from backend.app.schemas.common import SportType
from backend.app.schemas.provenance import PermittedUse, SourceProvenance
from datetime import datetime, timezone



# ── Helpers ────────────────────────────────────────────────────────────────────

def make_provenance() -> SourceProvenance:
    return SourceProvenance(
        source_id="cricsheet_test",
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        dataset_revision="rev1",
        source_format="json",
        source_format_version="1.3.0",
        file_sha256="a" * 64,
        license_name="ODC-By-1.0",
        license_url="http://opendatacommons.org/licenses/by/1.0/",
        attribution_text="Data provided by Cricsheet under ODC-By v1.0.",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
    )


def make_delta(runs=20, wickets=1, overs=5, legal=30, extras=2, rpo=4.0) -> CricketStateDelta:
    return CricketStateDelta(
        runs_added=runs,
        wickets_lost=wickets,
        completed_overs_delta=overs,
        legal_balls_added=legal,
        extras_added=extras,
        interval_run_rate=rpo,
    )


def make_snapshot(runs=0, wickets=0, overs=0) -> CricketScoreSnapshot:
    return CricketScoreSnapshot(
        runs=runs,
        wickets=wickets,
        overs_completed=overs,
        legal_balls_in_over=0,
        extras_total=0,
        run_rate=0.0,
    )


def make_wicket_fact(over=5, player="Batter A", kind="caught") -> EvidenceFact:
    return EvidenceFact(
        fact_id=f"fact_wkt_{over}_{player.replace(' ', '_')}",
        fact_type=FactType.WICKET,
        match_id="m1",
        source_revision="rev1",
        referenced_event_ids=[f"ev_{over}_1"],
        description=f"WICKET: {player} was dismissed ({kind}) in over {over}.",
        structured_payload={
            "player_out": player,
            "kind": kind,
            "over": over,
            "delivery": 1,
        },
    )


def make_six_fact(over=10, batter="Batter B") -> EvidenceFact:
    return EvidenceFact(
        fact_id=f"fact_six_{over}_{batter.replace(' ', '_')}",
        fact_type=FactType.BOUNDARY,
        match_id="m1",
        source_revision="rev1",
        referenced_event_ids=[f"ev_{over}_2"],
        description=f"SIX: {batter} hit a 6 in over {over}.",
        structured_payload={"batter": batter, "bowler": "Bowler", "runs": 6, "over": over},
    )


def make_over_summary_fact(over=8, runs=18) -> EvidenceFact:
    return EvidenceFact(
        fact_id=f"fact_oversummary_{over}",
        fact_type=FactType.OVER_SUMMARY,
        match_id="m1",
        source_revision="rev1",
        referenced_event_ids=[f"ev_{over}_1", f"ev_{over}_6"],
        description=f"HIGH-SCORING OVER: Over {over} yielded {runs} runs.",
        structured_payload={"over": over, "runs": runs},
    )


def make_packet(facts=None, delta_kwargs=None) -> MatchEvidencePacket:
    delta = make_delta(**(delta_kwargs or {}))
    return MatchEvidencePacket(
        packet_id="pkt_test",
        match_id="m1",
        sport=SportType.CRICKET,
        interval_summary="Test interval",
        state_before=make_snapshot(),
        state_after=make_snapshot(runs=delta.runs_added, wickets=delta.wickets_lost, overs=delta.completed_overs_delta),
        state_delta=delta,
        key_facts=facts or [],
        retrieved_knowledge_ids=[],
        retrieved_passages=[],
        provenance=make_provenance(),
    )


# ── chapters() tests ──────────────────────────────────────────────────────────

class TestChapters:

    def test_t20_full_innings_has_three_phases(self):
        windows = chapters("T20", 0, 19)
        labels = [w["label"] for w in windows]
        assert "Powerplay" in labels
        assert "Middle" in labels
        assert "Death" in labels

    def test_odi_phases_present(self):
        windows = chapters("ODI", 0, 49)
        labels = [w["label"] for w in windows]
        assert "Powerplay" in labels

    def test_windows_do_not_exceed_max_width(self):
        windows = chapters("ODI", 0, 49)
        for w in windows:
            span = w["end_after_over"] - w["start_after_over"]
            assert span <= MAX_WINDOW_OVERS, (
                f"Window {w['label']} exceeds {MAX_WINDOW_OVERS} overs: span={span}"
            )

    def test_windows_clamped_to_available_overs(self):
        windows = chapters("T20", 0, 6)
        for w in windows:
            assert w["end_after_over"] <= 6

    def test_no_empty_windows(self):
        windows = chapters("T20", 0, 19)
        for w in windows:
            assert w["end_after_over"] > w["start_after_over"]

    def test_last_n_windows_present(self):
        windows = chapters("T20", 0, 19)
        labels = [w["label"] for w in windows]
        assert any("Last" in l for l in labels)

    def test_innings_index_returned_in_window(self):
        windows = chapters("T20", 1, 19)
        assert all(w["innings"] == 1 for w in windows)

    def test_no_duplicates(self):
        windows = chapters("ODI", 0, 49)
        keys = [(w["start_after_over"], w["end_after_over"]) for w in windows]
        assert len(keys) == len(set(keys))

    def test_unknown_format_returns_empty(self):
        assert chapters("SuperOver", 0, 0) == []

    def test_last_n_clamped_when_too_few_overs(self):
        windows = chapters("T20", 0, 1, last_n_options=[6])
        for w in windows:
            assert w["end_after_over"] <= 1


# ── story_beats() tests ───────────────────────────────────────────────────────

class TestStoryBeats:

    def test_empty_packet_returns_empty(self):
        beats = story_beats(make_packet(facts=[]))
        assert beats == []

    def test_max_four_beats_returned(self):
        facts = [make_wicket_fact(over=i + 1, player=f"Batter {i}") for i in range(6)]
        beats = story_beats(make_packet(facts=facts))
        assert len(beats) <= MAX_STORY_BEATS

    def test_wickets_outrank_sixes(self):
        wkt = make_wicket_fact(over=8)
        six = make_six_fact(over=2)
        beats = story_beats(make_packet(facts=[six, wkt]))
        assert beats[0].beat_type == FactType.WICKET.value

    def test_beat_has_fact_id(self):
        beats = story_beats(make_packet(facts=[make_wicket_fact()]))
        assert beats[0].fact_id != ""

    def test_beat_description_matches_fact(self):
        wkt = make_wicket_fact(over=5, player="Rahul")
        beats = story_beats(make_packet(facts=[wkt]))
        assert "Rahul" in beats[0].description

    def test_no_invented_beats_when_no_facts(self):
        beats = story_beats(make_packet(facts=[]))
        assert len(beats) == 0

    def test_over_summary_beat(self):
        beats = story_beats(make_packet(facts=[make_over_summary_fact(over=12, runs=20)]))
        assert beats[0].beat_type == FactType.OVER_SUMMARY.value

    def test_beats_return_dataclass(self):
        beats = story_beats(make_packet(facts=[make_wicket_fact()]))
        assert isinstance(beats[0], StoryBeat)

    def test_wicket_label_includes_player_and_kind(self):
        wkt = make_wicket_fact(over=7, player="Kohli", kind="bowled")
        beats = story_beats(make_packet(facts=[wkt]))
        label = beats[0].label
        assert "Kohli" in label
        assert "bowled" in label


# ── headline() tests ──────────────────────────────────────────────────────────

class TestHeadline:

    def test_neutral_headline_has_run_count(self):
        packet = make_packet(delta_kwargs={"runs": 12, "wickets": 0, "overs": 3, "rpo": 4.0})
        h = headline(packet)
        assert "12" in h

    def test_wicket_cluster_headline(self):
        packet = make_packet(delta_kwargs={"runs": 22, "wickets": 3, "overs": 5, "rpo": 4.4})
        h = headline(packet)
        assert "3" in h and "wicket" in h.lower()

    def test_four_wicket_cluster_headline(self):
        packet = make_packet(delta_kwargs={"runs": 15, "wickets": 4, "overs": 3, "rpo": 5.0})
        h = headline(packet)
        assert "4" in h and "wicket" in h.lower()

    def test_high_tempo_headline(self):
        packet = make_packet(delta_kwargs={"runs": 50, "wickets": 0, "overs": 5, "rpo": 10.0})
        h = headline(packet)
        assert "50" in h

    def test_singular_wicket_in_neutral(self):
        packet = make_packet(delta_kwargs={"runs": 10, "wickets": 1, "overs": 2, "rpo": 5.0})
        h = headline(packet)
        assert "1 wicket" in h

    def test_plural_wickets_in_cluster(self):
        packet = make_packet(delta_kwargs={"runs": 10, "wickets": 3, "overs": 2, "rpo": 5.0})
        h = headline(packet)
        assert "wickets" in h

    def test_no_speculative_language(self):
        prohibited = ["searching", "dominance", "firmly in control", "miscommunication",
                      "panicked", "choked", "momentum guarantees"]
        packet = make_packet(delta_kwargs={"runs": 8, "wickets": 0, "overs": 3, "rpo": 2.7})
        h = headline(packet)
        for term in prohibited:
            assert term.lower() not in h.lower()

    def test_singular_over_in_neutral(self):
        packet = make_packet(delta_kwargs={"runs": 8, "wickets": 0, "overs": 1, "rpo": 8.0})
        h = headline(packet)
        assert "1 over" in h

    def test_headline_length_within_limit(self):
        for wkts in [0, 1, 3, 5]:
            packet = make_packet(delta_kwargs={"runs": 30, "wickets": wkts, "overs": 5, "rpo": 6.0})
            assert len(headline(packet)) <= 120


# ── required_rate_arc() tests ─────────────────────────────────────────────────

class TestRequiredRateArc:

    def test_returns_none_when_target_missing(self):
        assert required_rate_arc(None, 50, 60) is None

    def test_returns_none_when_runs_scored_missing(self):
        assert required_rate_arc(200, None, 60) is None

    def test_returns_none_when_balls_missing(self):
        assert required_rate_arc(200, 100, None) is None

    def test_simple_chase_arc(self):
        arc = required_rate_arc(200, 100, 60)
        assert arc.runs_required == 100
        assert arc.required_rate == 10.0
        assert not arc.is_chase_complete
        assert not arc.is_impossible

    def test_chase_complete(self):
        arc = required_rate_arc(200, 205, 12)
        assert arc.is_chase_complete
        assert arc.runs_required == 0
        assert arc.required_rate == 0.0

    def test_chase_impossible(self):
        arc = required_rate_arc(200, 150, 0)
        assert arc.is_impossible
        assert arc.required_rate == 0.0

    def test_fractional_overs(self):
        arc = required_rate_arc(180, 90, 15)
        assert arc.required_rate == pytest.approx(36.0, abs=0.01)

    def test_returns_dataclass(self):
        assert isinstance(required_rate_arc(200, 100, 60), RequiredRateArc)

    def test_rounded_to_two_dp(self):
        arc = required_rate_arc(201, 100, 60)
        assert arc.required_rate == 10.1


# ── Singular/plural formatting tests ─────────────────────────────────────────

class TestPluralFormatting:

    def test_one_wicket_singular(self):
        packet = make_packet(delta_kwargs={"runs": 15, "wickets": 1, "overs": 3, "rpo": 5.0})
        h = headline(packet)
        assert "1 wicket" in h and "wickets" not in h

    def test_zero_wickets_plural(self):
        h = headline(make_packet(delta_kwargs={"runs": 15, "wickets": 0, "overs": 3, "rpo": 5.0}))
        assert "0 wickets" in h

    def test_one_over_singular(self):
        h = headline(make_packet(delta_kwargs={"runs": 8, "wickets": 0, "overs": 1, "rpo": 8.0}))
        assert "1 over" in h and "overs" not in h

    def test_multiple_overs_plural(self):
        h = headline(make_packet(delta_kwargs={"runs": 30, "wickets": 2, "overs": 5, "rpo": 6.0}))
        assert "5 overs" in h
