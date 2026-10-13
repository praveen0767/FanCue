"""Contract tests for EvidenceFact and MatchEvidencePacket."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.schemas.common import SportType
from backend.app.schemas.cricket import (
    CricketScoreSnapshot,
    CricketStateDelta,
)
from backend.app.schemas.evidence import (
    EvidenceFact,
    FactType,
    MatchEvidencePacket,
)
from backend.app.schemas.provenance import (
    PermittedUse,
    SourceProvenance,
)


@pytest.fixture
def sample_provenance():
    return SourceProvenance(
        source_id="cricsheet_historical_odi",
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=datetime.now(timezone.utc),
        dataset_revision="1",
        source_format="json",
        source_format_version="1.3.0",
        file_sha256="8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f",
        license_name="ODC-By-1.0",
        license_url="http://opendatacommons.org/licenses/by/1.0/",
        attribution_text="Data provided by Cricsheet under ODC-By v1.0.",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
    )


def test_valid_evidence_fact():
    """Verify standard EvidenceFact instantiation with event citations."""
    fact = EvidenceFact(
        fact_id="fact_1529229_ov2_w1",
        fact_type=FactType.WICKET,
        match_id="1529229",
        source_revision="1",
        referenced_event_ids=["1529229_inn0_ov2_b3"],
        description="Shubman Gill caught by SD Hope off JNT Seales for 8 runs.",
        structured_payload={"player_out": "Shubman Gill", "bowler": "JNT Seales", "score_at_fall": 12},
    )
    assert fact.fact_id == "fact_1529229_ov2_w1"
    assert fact.fact_type == FactType.WICKET
    assert len(fact.referenced_event_ids) == 1


def test_evidence_fact_requires_event_reference():
    """Evidence fact cannot exist without at least one underlying event reference."""
    with pytest.raises(ValidationError):
        EvidenceFact(
            fact_id="fact_invalid",
            fact_type=FactType.WICKET,
            match_id="1529229",
            source_revision="1",
            referenced_event_ids=[],  # Empty list forbidden
            description="Fabricated assertion with no events.",
        )


def test_valid_match_evidence_packet(sample_provenance):
    """Verify end-to-end evidence packet composition."""
    fact = EvidenceFact(
        fact_id="fact_1529229_ov2_w1",
        fact_type=FactType.WICKET,
        match_id="1529229",
        source_revision="1",
        referenced_event_ids=["1529229_inn0_ov2_b3"],
        description="Shubman Gill caught by SD Hope.",
    )
    packet = MatchEvidencePacket(
        packet_id="pkt_1529229_inn0_14_22",
        match_id="1529229",
        sport=SportType.CRICKET,
        interval_summary="Innings 0, Overs 15 to 22",
        state_before=CricketScoreSnapshot(runs=89, wickets=2, overs_completed=15, legal_balls_in_over=0),
        state_after=CricketScoreSnapshot(runs=142, wickets=3, overs_completed=23, legal_balls_in_over=0),
        state_delta=CricketStateDelta(
            runs_added=53,
            wickets_lost=1,
            completed_overs_delta=8,
            legal_balls_added=48,
            extras_added=2,
            interval_run_rate=6.62,
        ),
        key_facts=[fact],
        retrieved_knowledge_ids=["doc_cricket_powerplay_rules"],
        provenance=sample_provenance,
    )
    assert packet.packet_id == "pkt_1529229_inn0_14_22"
    assert len(packet.key_facts) == 1
    assert packet.provenance.source_id == "cricsheet_historical_odi"
