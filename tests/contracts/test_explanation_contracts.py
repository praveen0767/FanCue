"""Contract tests for StructuredClaim, ExplanationPayload, and CricketCatchUpResponse."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.schemas.common import (
    LanguageCode,
    MatchDescriptor,
    MatchMode,
    SportType,
)
from backend.app.schemas.cricket import (
    CricketInterval,
    CricketScoreSnapshot,
    CricketStateDelta,
)
from backend.app.schemas.evidence import (
    EvidenceFact,
    FactType,
    MatchEvidencePacket,
)
from backend.app.schemas.explanation import (
    ClaimType,
    CricketCatchUpResponse,
    ExplanationPayload,
    FallbackReason,
    GenerationMode,
    StructuredClaim,
    VerificationStatus,
)
from backend.app.schemas.provenance import (
    PermittedUse,
    SourceProvenance,
)


@pytest.fixture
def sample_match():
    return MatchDescriptor(
        match_id="1529229",
        sport=SportType.CRICKET,
        name="India vs West Indies",
        format="ODI",
        teams=["India", "West Indies"],
        date="2026-10-03",
        mode=MatchMode.REPLAY,
        source_id="cricsheet_historical_odi",
        source_revision="1",
        supported_innings=[0, 1],
    )


@pytest.fixture
def sample_evidence_packet():
    prov = SourceProvenance(
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
    return MatchEvidencePacket(
        packet_id="pkt_test_1",
        match_id="1529229",
        sport=SportType.CRICKET,
        interval_summary="Overs 15 to 22",
        state_before=CricketScoreSnapshot(runs=89, wickets=2, overs_completed=15),
        state_after=CricketScoreSnapshot(runs=142, wickets=3, overs_completed=23),
        state_delta=CricketStateDelta(
            runs_added=53,
            wickets_lost=1,
            completed_overs_delta=8,
            legal_balls_added=48,
        ),
        key_facts=[
            EvidenceFact(
                fact_id="fact_1",
                fact_type=FactType.WICKET,
                match_id="1529229",
                source_revision="1",
                referenced_event_ids=["e1"],
                description="Wicket fall.",
            )
        ],
        retrieved_knowledge_ids=["doc_1"],
        provenance=prov,
    )


def test_valid_structured_claim():
    """Verify structured claim with explicit fact citation."""
    claim = StructuredClaim(
        claim_id="clm_1",
        claim_type=ClaimType.SCORE_DELTA,
        text="India accumulated 53 runs in the interval.",
        cited_fact_ids=["fact_interval_delta"],
        cited_knowledge_ids=[],
    )
    assert claim.claim_id == "clm_1"
    assert claim.cited_fact_ids == ["fact_interval_delta"]


def test_valid_explanation_payload_verified():
    """Verify ExplanationPayload under normal verified LLM execution."""
    payload = ExplanationPayload(
        summary="India added 53 runs across 8 overs, losing Shubman Gill for 18.",
        claims=[
            StructuredClaim(
                claim_id="clm_1",
                claim_type=ClaimType.SCORE_DELTA,
                text="53 runs added.",
                cited_fact_ids=["fact_delta"],
            )
        ],
        generation_mode=GenerationMode.LLM_VERIFIED,
        verification_status=VerificationStatus.VERIFIED,
        fallback_reason=FallbackReason.NONE,
    )
    assert payload.generation_mode == GenerationMode.LLM_VERIFIED
    assert payload.verification_status == VerificationStatus.VERIFIED


def test_explanation_payload_deterministic_fallback():
    """Verify ExplanationPayload under deterministic fallback engagement."""
    payload = ExplanationPayload(
        summary="Interval recap: Runs: +53, Wickets: -1, Completed overs: 8.",
        claims=[],
        generation_mode=GenerationMode.DETERMINISTIC_FALLBACK,
        verification_status=VerificationStatus.UNVERIFIED_FALLBACK,
        fallback_reason=FallbackReason.TIMEOUT,
    )
    assert payload.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
    assert payload.fallback_reason == FallbackReason.TIMEOUT


def test_valid_cricket_catchup_response(sample_match, sample_evidence_packet):
    """Verify end-to-end catch-up response contract."""
    response = CricketCatchUpResponse(
        match=sample_match,
        interval=CricketInterval(innings=0, start_after_over=14, end_after_over=22),
        state_before=CricketScoreSnapshot(runs=89, wickets=2, overs_completed=15),
        state_after=CricketScoreSnapshot(runs=142, wickets=3, overs_completed=23),
        state_delta=CricketStateDelta(
            runs_added=53,
            wickets_lost=1,
            completed_overs_delta=8,
            legal_balls_added=48,
        ),
        evidence_packet=sample_evidence_packet,
        explanation=ExplanationPayload(
            summary="Interval recap summary.",
            generation_mode=GenerationMode.LLM_VERIFIED,
            verification_status=VerificationStatus.VERIFIED,
        ),
        language=LanguageCode.EN,
        mode=MatchMode.REPLAY,
    )
    assert response.match.match_id == "1529229"
    assert response.mode == MatchMode.REPLAY
    assert response.generated_at.tzinfo is not None
