"""Regression test for a partial claim rejection leaking through the LLM summary."""

from backend.app.ai.models import AICandidateClaim, AIExplanationDraft
from backend.app.ai.provider import DeterministicFakeProvider
from backend.app.core.fixtures import get_engine
from backend.app.orchestration.cricket_catchup import CricketCatchUpOrchestrator
from backend.app.orchestration.evidence_builder import EvidencePacketBuilder
from backend.app.schemas.cricket import CricketCatchUpRequest, CricketInterval
from backend.app.schemas.evidence import FactType
from backend.app.schemas.explanation import (
    ClaimType,
    FallbackReason,
    GenerationMode,
)


def test_rejected_claim_forces_fallback_even_when_score_claim_is_valid():
    engine = get_engine("1529229")
    assert engine is not None
    request = CricketCatchUpRequest(
        match_id="1529229",
        interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
    )
    packet = EvidencePacketBuilder(engine, retrieval_service=None).build_packet(request)
    delta_fact = next(f for f in packet.key_facts if f.fact_type == FactType.STATE_MILESTONE)
    delta = packet.state_delta

    valid_score = AICandidateClaim(
        claim_id="valid_score",
        claim_type=ClaimType.SCORE_DELTA,
        text=f"During the interval, {delta.runs_added} runs were added.",
        cited_fact_ids=[delta_fact.fact_id],
        claimed_runs=delta.runs_added,
        claimed_wickets=delta.wickets_lost,
        claimed_overs=delta.completed_overs_delta,
    )
    unsupported_event = AICandidateClaim(
        claim_id="invented_wicket",
        claim_type=ClaimType.EVENT_CHRONOLOGY,
        text="WICKET: FAKEPLAYER_EVAL_XYZ was dismissed (bowled) in over 1.",
        cited_fact_ids=["fact_nonexistent_adversarial_eval"],
        claimed_player="FAKEPLAYER_EVAL_XYZ",
    )
    provider = DeterministicFakeProvider(
        preset_draft=AIExplanationDraft(
            summary="The interval included an invented wicket for FAKEPLAYER_EVAL_XYZ.",
            claims=[valid_score, unsupported_event],
        )
    )
    response = CricketCatchUpOrchestrator(
        engine=engine,
        retrieval_service=None,
        llm_provider=provider,
        skip_llm=False,
    ).catch_up(request)

    assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
    assert response.explanation.fallback_reason == FallbackReason.UNSUPPORTED_CLAIMS
    assert "FAKEPLAYER_EVAL_XYZ" not in response.explanation.summary
    assert "invented wicket" not in response.explanation.summary.lower()
