#!/usr/bin/env python3
"""Small offline adversarial evaluation using the real FanCue verifier pipeline.

This is a diagnostic over three hand-authored drafts, not a statistical estimate of
real-world verifier accuracy. It uses tracked fixtures and makes no network calls.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from backend.app.ai.models import AICandidateClaim, AIExplanationDraft
from backend.app.ai.provider import DeterministicFakeProvider
from backend.app.core.fixtures import get_engine
from backend.app.orchestration.cricket_catchup import CricketCatchUpOrchestrator
from backend.app.orchestration.evidence_builder import EvidencePacketBuilder
from backend.app.schemas.cricket import CricketCatchUpRequest, CricketInterval
from backend.app.schemas.evidence import FactType
from backend.app.schemas.explanation import ClaimType, FallbackReason, GenerationMode


MATCH_ID = "1529229"
FAKE_PLAYER = "FAKEPLAYER_EVAL_XYZ"
REQUEST = CricketCatchUpRequest(
    match_id=MATCH_ID,
    interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
)


def _fixture_context():
    engine = get_engine(MATCH_ID)
    if engine is None:
        raise RuntimeError(f"Required tracked fixture {MATCH_ID} is unavailable.")
    packet = EvidencePacketBuilder(engine, retrieval_service=None).build_packet(REQUEST)
    delta_fact = next(
        (fact for fact in packet.key_facts if fact.fact_type == FactType.STATE_MILESTONE),
        None,
    )
    event_fact = next(
        (
            fact for fact in packet.key_facts
            if fact.fact_type in {FactType.WICKET, FactType.BOUNDARY, FactType.OVER_SUMMARY}
        ),
        None,
    )
    if delta_fact is None:
        raise RuntimeError("Evidence packet has no authoritative state-delta fact.")
    if event_fact is None:
        raise RuntimeError("Selected fixture interval has no event fact for the wrong-player draft.")
    return engine, packet, delta_fact, event_fact


def _valid_score_claim(packet, delta_fact) -> AICandidateClaim:
    delta = packet.state_delta
    return AICandidateClaim(
        claim_id="grounded_score_delta",
        claim_type=ClaimType.SCORE_DELTA,
        text=f"During the interval, {delta.runs_added} runs were added.",
        cited_fact_ids=[delta_fact.fact_id],
        claimed_runs=delta.runs_added,
        claimed_wickets=delta.wickets_lost,
        claimed_overs=delta.completed_overs_delta,
    )


def _adversarial_drafts(packet, delta_fact, event_fact):
    delta = packet.state_delta
    valid_score = _valid_score_claim(packet, delta_fact)
    over = event_fact.structured_payload.get("over", 1)

    wrong_score = AICandidateClaim(
        claim_id="wrong_score",
        claim_type=ClaimType.SCORE_DELTA,
        text=f"During the interval, {delta.runs_added + 100} runs were added.",
        cited_fact_ids=[delta_fact.fact_id],
        claimed_runs=delta.runs_added + 100,
        claimed_wickets=delta.wickets_lost,
        claimed_overs=delta.completed_overs_delta,
    )
    wrong_player = AICandidateClaim(
        claim_id="wrong_player",
        claim_type=ClaimType.EVENT_CHRONOLOGY,
        text=f"{FAKE_PLAYER} appeared in the event recorded in over {over}.",
        cited_fact_ids=[event_fact.fact_id],
        claimed_player=FAKE_PLAYER,
    )
    invented_wicket = AICandidateClaim(
        claim_id="invented_wicket",
        claim_type=ClaimType.EVENT_CHRONOLOGY,
        text=f"WICKET: {FAKE_PLAYER} was dismissed (bowled) in over 1.",
        cited_fact_ids=["fact_nonexistent_adversarial_eval"],
        claimed_player=FAKE_PLAYER,
    )
    return [
        ("wrong_score", AIExplanationDraft(
            summary=f"Adversarial summary: {delta.runs_added + 100} runs were added.",
            claims=[wrong_score],
        )),
        ("wrong_player", AIExplanationDraft(
            summary=f"Adversarial summary: {FAKE_PLAYER} appeared in the interval.",
            claims=[valid_score, wrong_player],
        )),
        ("invented_wicket", AIExplanationDraft(
            summary=f"Adversarial summary: {FAKE_PLAYER} was dismissed for a wicket.",
            claims=[valid_score, invented_wicket],
        )),
    ]


def run_evaluation():
    engine, packet, delta_fact, event_fact = _fixture_context()
    results = []
    for case, draft in _adversarial_drafts(packet, delta_fact, event_fact):
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine,
            retrieval_service=None,
            llm_provider=DeterministicFakeProvider(preset_draft=draft),
            skip_llm=False,
        )
        response = orchestrator.catch_up(REQUEST)
        rejected = (
            response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
            and response.explanation.fallback_reason
            in {FallbackReason.FACT_MISMATCH, FallbackReason.UNSUPPORTED_CLAIMS}
        )
        summary_leaked = (
            FAKE_PLAYER in response.explanation.summary
            or "Adversarial summary" in response.explanation.summary
        )
        results.append({
            "case": case,
            "generation_mode": response.explanation.generation_mode.value,
            "fallback_reason": response.explanation.fallback_reason.value,
            "draft_rejected": rejected,
            "fabricated_summary_leaked": summary_leaked,
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="", help="Optional Markdown report file.")
    args = parser.parse_args()

    results = run_evaluation()
    rejected = sum(bool(row["draft_rejected"]) for row in results)
    leaked = sum(bool(row["fabricated_summary_leaked"]) for row in results)
    rejection_rate = (rejected / len(results) * 100.0) if results else 0.0
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print("FanCue adversarial verifier evaluation")
    print(f"date_utc={timestamp}")
    for row in results:
        print(
            f"case={row['case']} mode={row['generation_mode']} "
            f"fallback_reason={row['fallback_reason']} "
            f"draft_rejected={str(row['draft_rejected']).lower()} "
            f"fabricated_summary_leaked={str(row['fabricated_summary_leaked']).lower()}"
        )
    print(f"adversarial_drafts={len(results)}")
    print(f"drafts_rejected={rejected}")
    print(f"draft_rejection_rate={rejection_rate:.1f}%")
    print(f"fabricated_summary_leaks={leaked}")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# FanCue Adversarial Verifier Evaluation",
            "",
            f"- Date: {timestamp}",
            f"- Command: python scripts/evaluate_verifier_adversarial.py --report {report_path}",
            "- Method: three hand-authored drafts run through the real fixture-backed evidence builder, verifier, and catch-up orchestrator. No network or live LLM call is used.",
            f"- Draft rejection: **{rejected}/{len(results)} ({rejection_rate:.1f}%)** on this small adversarial set.",
            f"- Fabricated summary leakage: **{leaked}**.",
            "",
            "| Case | Generation mode | Fallback reason | Draft rejected | Fabricated summary leaked |",
            "|---|---|---|---|---|",
        ]
        for row in results:
            lines.append(
                f"| {row['case']} | {row['generation_mode']} | {row['fallback_reason']} | "
                f"{'yes' if row['draft_rejected'] else 'no'} | "
                f"{'yes' if row['fabricated_summary_leaked'] else 'no'} |"
            )
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"report_written={report_path}")
    return 0 if rejected == len(results) and leaked == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
