"""Deterministic explanation builder generating structured fallbacks directly from engine facts."""

from typing import List

from backend.app.schemas.evidence import FactType, MatchEvidencePacket
from backend.app.schemas.explanation import (
    ClaimType,
    ExplanationPayload,
    FallbackReason,
    GenerationMode,
    StructuredClaim,
    VerificationStatus,
)


def pluralize(count: int, singular: str, plural: str = None) -> str:
    """Return '<count> <word>' with correct singular/plural agreement.

    Handles the required forms '1 wicket', '1 over', '1 six' and their plurals.
    English pluralization rule: words ending in consonant+y take '-ies';
    everything else takes '-s'.
    """
    plural = plural or (singular[:-1] + "ies" if singular.endswith("y") else singular + "s")
    return f"{count} {singular if count == 1 else plural}"


def build_deterministic_fallback(
    packet: MatchEvidencePacket,
    fallback_reason: FallbackReason = FallbackReason.NONE,
) -> ExplanationPayload:
    """Construct an objective, factually verified explanation strictly from evidence facts."""
    delta = packet.state_delta
    state_before = packet.state_before
    state_after = packet.state_after

    delta_fact = next(
        (f for f in packet.key_facts if f.fact_type == FactType.STATE_MILESTONE),
        None,
    )
    delta_fact_id = delta_fact.fact_id if delta_fact else "fact_delta"

    # 1. State Delta Claim
    start_str = "the innings opening" if state_before.overs_completed == 0 else f"over {state_before.overs_completed}"
    end_str = f"over {state_after.overs_completed}"

    # Runs, wickets and completed overs with singular/plural agreement.
    delta_claim_text = (
        f"From {start_str} through {end_str}, the batting side "
        f"added {delta.runs_added} {'run' if delta.runs_added == 1 else 'runs'} "
        f"for the loss of {pluralize(delta.wickets_lost, 'wicket')} in "
        f"{pluralize(delta.completed_overs_delta, 'completed over')} "
        f"(scoring rate: {delta.interval_run_rate:.2f} runs per over)."
    )

    claims: List[StructuredClaim] = [
        StructuredClaim(
            claim_id="fallback_claim_1",
            claim_type=ClaimType.SCORE_DELTA,
            text=delta_claim_text,
            cited_fact_ids=[delta_fact_id],
            cited_knowledge_ids=[],
        )
    ]

    # 2. Event Chronology Claims (Wickets, boundaries, over summaries)
    event_sentences = []
    wicket_facts = [f for f in packet.key_facts if f.fact_type == FactType.WICKET]
    for i, w_fact in enumerate(wicket_facts, start=1):
        claim_id = f"fallback_claim_wicket_{i}"
        claims.append(
            StructuredClaim(
                claim_id=claim_id,
                claim_type=ClaimType.EVENT_CHRONOLOGY,
                text=w_fact.description,
                cited_fact_ids=[w_fact.fact_id],
                cited_knowledge_ids=[],
            )
        )
        event_sentences.append(w_fact.description)

    six_facts = [f for f in packet.key_facts if f.fact_type == FactType.BOUNDARY]
    for i, s_fact in enumerate(six_facts, start=1):
        claim_id = f"fallback_claim_six_{i}"
        claims.append(
            StructuredClaim(
                claim_id=claim_id,
                claim_type=ClaimType.EVENT_CHRONOLOGY,
                text=s_fact.description,
                cited_fact_ids=[s_fact.fact_id],
                cited_knowledge_ids=[],
            )
        )
        event_sentences.append(s_fact.description)

    # 3. Contextual Rule/Concept Citation if available in packet
    if packet.retrieved_passages:
        top_passage = packet.retrieved_passages[0]
        context_text = f"Contextual match rules for this interval align with {top_passage.source_name}."
        claims.append(
            StructuredClaim(
                claim_id="fallback_claim_context_1",
                claim_type=ClaimType.TACTICAL_CONTEXT,
                text=context_text,
                cited_fact_ids=[],
                cited_knowledge_ids=[top_passage.doc_id],
            )
        )

    # Keep the fallback readable on a phone: two concise, factual sentences.
    # Event-by-event details remain in the evidence and turning-moment cards below.
    run_word = "run" if delta.runs_added == 1 else "runs"
    if delta.wickets_lost:
        wicket_clause = f"and lost {pluralize(delta.wickets_lost, 'wicket')}"
    else:
        wicket_clause = "without losing a wicket"

    summary = (
        f"Deterministic recap: The score moved from "
        f"{state_before.runs}/{state_before.wickets} to "
        f"{state_after.runs}/{state_after.wickets} across "
        f"{pluralize(delta.completed_overs_delta, 'over')}. "
        f"The batting side added {delta.runs_added} {run_word} {wicket_clause}, "
        f"scoring at {delta.interval_run_rate:.2f} runs per over."
    )

    return ExplanationPayload(
        summary=summary,
        claims=claims,
        generation_mode=GenerationMode.DETERMINISTIC_FALLBACK,
        verification_status=VerificationStatus.VERIFIED,
        fallback_reason=fallback_reason,
    )
