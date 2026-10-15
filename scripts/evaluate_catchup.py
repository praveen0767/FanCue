#!/usr/bin/env python3
"""Measure deployed catch-up latency/fallbacks and run local adversarial verifier cases.

Run from the repository root after installing project dependencies:
  python scripts/evaluate_catchup.py --base-url https://fancue-api-o4r1.onrender.com --requests 20

This intentionally makes real POST /catchup calls. No API key is accepted on the
command line and no response metrics are fabricated. The report is overwritten
with the observed results of that exact invocation.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_IDS = ("1529229", "1552779")
DEFAULT_API_BASE = "https://fancue-api-o4r1.onrender.com"


class EvaluationRequestError(RuntimeError):
    """Transport or response-shape error during a live API measurement."""


def http_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 90.0,
) -> tuple[int, Any, float]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        elapsed = time.perf_counter() - started
        raise EvaluationRequestError(
            f"{method} {path} transport error after {elapsed:.3f}s: {type(exc).__name__}: {exc}"
        ) from exc
    elapsed = time.perf_counter() - started
    try:
        return status, json.loads(raw.decode("utf-8")) if raw else {}, elapsed
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        snippet = raw[:300].decode("utf-8", errors="replace")
        raise EvaluationRequestError(
            f"{method} {path} returned non-JSON data (HTTP {status}): {snippet!r}"
        ) from exc


def nearest_rank_percentile(values: list[float], percentile: float) -> float | None:
    """Nearest-rank percentile, with 1-based rank ceil(p * n)."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def make_local_adversarial_report() -> dict[str, Any]:
    """Run three intentionally incorrect drafts through the real ClaimVerifier."""
    from backend.app.ai.models import AICandidateClaim, AIExplanationDraft
    from backend.app.match_engine.cricket import CricketMatchEngine
    from backend.app.orchestration.evidence_builder import EvidencePacketBuilder
    from backend.app.schemas.common import LanguageCode
    from backend.app.schemas.cricket import CricketCatchUpRequest, CricketInterval
    from backend.app.schemas.explanation import ClaimType
    from backend.app.schemas.provenance import PermittedUse, SourceProvenance
    from backend.app.verification.claim_verifier import ClaimVerifier

    fixture_path = ROOT / "data" / "raw" / "1529229.json"
    if not fixture_path.is_file():
        raise FileNotFoundError(f"Required tracked fixture is missing: {fixture_path}")

    provenance = SourceProvenance(
        source_id="cricsheet_historical_odi",
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=datetime.now(timezone.utc),
        dataset_revision="1",
        source_format="json",
        source_format_version="1.3.0",
        file_sha256="8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f",
        license_name="Open Data Commons Attribution License (ODC-By v1.0)",
        license_url="https://opendatacommons.org/licenses/by/1.0/",
        attribution_text=(
            "Data provided by Cricsheet (https://cricsheet.org/), licensed under "
            "the Open Data Commons Attribution License (ODC-By v1.0)."
        ),
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
    )
    engine = CricketMatchEngine.from_fixture(
        file_path=str(fixture_path),
        match_id="1529229",
        provenance=provenance,
    )
    request = CricketCatchUpRequest(
        match_id="1529229",
        interval=CricketInterval(
            innings=0,
            start_after_over=14,
            end_after_over=21,
        ),
        language=LanguageCode.EN,
    )
    packet = EvidencePacketBuilder(engine=engine, retrieval_service=None).build_packet(request)
    delta = packet.state_delta
    delta_fact = next(
        (fact for fact in packet.key_facts if "runs_added" in fact.structured_payload),
        None,
    )
    if delta_fact is None:
        raise RuntimeError("The engine evidence packet did not contain a state-delta fact.")
    verifier = ClaimVerifier(reject_on_any_core_failure=True)

    cases = [
        {
            "name": "wrong_score",
            "summary": "Adversarial draft with an incorrect score.",
            "claim": AICandidateClaim(
                claim_id="eval_wrong_score",
                claim_type=ClaimType.SCORE_DELTA,
                text=(
                    f"During this interval, {delta.runs_added + 999} runs were added "
                    f"for {delta.wickets_lost} wickets."
                ),
                cited_fact_ids=[delta_fact.fact_id],
                claimed_runs=delta.runs_added + 999,
                claimed_wickets=delta.wickets_lost,
                claimed_overs=delta.completed_overs_delta,
            ),
        },
        {
            "name": "wrong_player",
            "summary": "Adversarial draft with an invented player.",
            "claim": AICandidateClaim(
                claim_id="eval_wrong_player",
                claim_type=ClaimType.EVENT_CHRONOLOGY,
                text="FAKEPLAYER_XYZ was dismissed during the interval.",
                cited_fact_ids=[delta_fact.fact_id],
                claimed_player="FAKEPLAYER_XYZ",
            ),
        },
        {
            "name": "invented_wicket",
            "summary": "Adversarial draft with an invented wicket count.",
            "claim": AICandidateClaim(
                claim_id="eval_invented_wicket",
                claim_type=ClaimType.SCORE_DELTA,
                text=(
                    f"During this interval, {delta.runs_added} runs were added "
                    f"for the loss of {delta.wickets_lost + 1} wickets."
                ),
                cited_fact_ids=[delta_fact.fact_id],
                claimed_runs=delta.runs_added,
                claimed_wickets=delta.wickets_lost + 1,
                claimed_overs=delta.completed_overs_delta,
            ),
        },
    ]

    results = []
    for case in cases:
        draft = AIExplanationDraft(summary=case["summary"], claims=[case["claim"]])
        report = verifier.verify(draft, packet)
        reasons = sorted({item.reason.value for item in report.rejected_claims})
        rejected = (not report.is_verified) and bool(report.rejected_claims)
        results.append(
            {
                "case": case["name"],
                "rejected": rejected,
                "is_verified": report.is_verified,
                "rejection_reasons": reasons,
                "rejected_claim_count": len(report.rejected_claims),
            }
        )

    rejected_count = sum(1 for item in results if item["rejected"])
    return {
        "fixture": "1529229",
        "interval": {
            "innings": request.interval.innings,
            "start_after_over": request.interval.start_after_over,
            "end_after_over": request.interval.end_after_over,
        },
        "adversarial_cases": len(results),
        "rejected_cases": rejected_count,
        "rejection_rate_percent": 100.0 * rejected_count / len(results) if results else None,
        "results": results,
    }


def choose_interval(intervals: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [
        item for item in intervals
        if isinstance(item.get("start_after_over"), int)
        and isinstance(item.get("end_after_over"), int)
        and item["end_after_over"] > item["start_after_over"]
    ]
    if not valid:
        raise EvaluationRequestError("The API returned no valid whole-over intervals.")
    return min(
        valid,
        key=lambda item: (
            item["end_after_over"] - item["start_after_over"],
            1 if item["start_after_over"] < 0 else 0,
            item["end_after_over"],
        ),
    )


def run_live_evaluation(
    base_url: str,
    request_count: int,
    timeout: float,
) -> dict[str, Any]:
    """Run real catch-ups; request POSTs are deliberately not retried."""
    result: dict[str, Any] = {
        "base_url": base_url.rstrip("/"),
        "requested_catchups": request_count,
        "attempts": [],
        "completed_http_responses": 0,
        "successful_catchups": 0,
        "failed_attempts": 0,
        "fallback_count": 0,
        "verifier_rejection_proxy_count": 0,
        "latencies_seconds": [],
        "error": None,
    }
    base = base_url.rstrip("/")
    try:
        health_status, health_payload, health_elapsed = http_json(
            base, "/healthz", timeout=timeout
        )
        result["health"] = {
            "status": health_status,
            "elapsed_seconds": health_elapsed,
            "reported_status": health_payload.get("status") if isinstance(health_payload, dict) else None,
        }
        matches_status, matches_payload, _ = http_json(base, "/matches", timeout=timeout)
        if matches_status != 200:
            raise EvaluationRequestError(f"GET /matches returned HTTP {matches_status}.")
        available = {
            str(item.get("match_id")): item
            for item in (matches_payload.get("matches", []) if isinstance(matches_payload, dict) else [])
        }
        intervals_by_fixture: dict[str, dict[str, Any]] = {}
        for fixture_id in FIXTURE_IDS:
            if fixture_id not in available:
                raise EvaluationRequestError(f"Fixture {fixture_id} is not listed by the deployed API.")
            status, payload, _ = http_json(
                base, f"/matches/{fixture_id}/intervals", timeout=timeout
            )
            if status != 200 or not isinstance(payload, dict):
                raise EvaluationRequestError(
                    f"GET /matches/{fixture_id}/intervals returned HTTP {status}."
                )
            intervals = payload.get("intervals", [])
            intervals_by_fixture[fixture_id] = choose_interval(intervals)
    except Exception as exc:
        result["error"] = f"Setup failed before benchmarking: {type(exc).__name__}: {exc}"
        result["failed_attempts"] = request_count
        return result

    for index in range(request_count):
        fixture_id = FIXTURE_IDS[index % len(FIXTURE_IDS)]
        interval = intervals_by_fixture[fixture_id]
        body = {
            "match_id": fixture_id,
            "interval": {
                "innings": interval["innings"],
                "start_after_over": interval["start_after_over"],
                "end_after_over": interval["end_after_over"],
            },
            "lens": "match",
            "language": "en",
            "explanation_depth": "standard",
        }
        started = time.perf_counter()
        attempt: dict[str, Any] = {
            "index": index + 1,
            "match_id": fixture_id,
            "interval": body["interval"],
        }
        try:
            status, response, elapsed = http_json(
                base, "/catchup", method="POST", payload=body, timeout=timeout
            )
            attempt["http_status"] = status
            attempt["elapsed_seconds"] = elapsed
            result["completed_http_responses"] += 1
            result["latencies_seconds"].append(elapsed)

            if status != 200 or not isinstance(response, dict):
                attempt["outcome"] = "http_error"
                attempt["error_body"] = response
                result["failed_attempts"] += 1
            else:
                explanation = response.get("explanation") or {}
                mode = explanation.get("generation_mode")
                verification = explanation.get("verification_status")
                fallback_reason = explanation.get("fallback_reason")
                attempt.update(
                    {
                        "outcome": "success",
                        "generation_mode": mode,
                        "verification_status": verification,
                        "fallback_reason": fallback_reason,
                        "runs_added": (response.get("state_delta") or {}).get("runs_added"),
                        "wickets_lost": (response.get("state_delta") or {}).get("wickets_lost"),
                    }
                )
                if mode == "deterministic_fallback":
                    result["fallback_count"] += 1
                # The API exposes fallback_reason, not a raw verifier rejection count.
                # Treat these reasons as a documented proxy, not an exact per-draft rate.
                if fallback_reason in ("fact_mismatch", "unsupported_claims"):
                    result["verifier_rejection_proxy_count"] += 1
                result["successful_catchups"] += 1
        except Exception as exc:
            attempt["elapsed_seconds"] = time.perf_counter() - started
            attempt["outcome"] = "transport_or_parse_error"
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            result["failed_attempts"] += 1
        result["attempts"].append(attempt)

    latencies = result["latencies_seconds"]
    result["latency_definition"] = (
        "p50/p95 are nearest-rank percentiles of attempts that returned an HTTP response "
        "(including non-200 responses); transport failures without an HTTP response are excluded."
    )
    result["p50_seconds"] = nearest_rank_percentile(latencies, 0.50)
    result["p95_seconds"] = nearest_rank_percentile(latencies, 0.95)
    denominator = result["successful_catchups"]
    result["fallback_rate_percent"] = (
        100.0 * result["fallback_count"] / denominator if denominator else None
    )
    result["verifier_rejection_proxy_rate_percent"] = (
        100.0 * result["verifier_rejection_proxy_count"] / denominator if denominator else None
    )
    return result


def percent(value: float | None) -> str:
    return "NOT AVAILABLE" if value is None else f"{value:.2f}%"


def seconds(value: float | None) -> str:
    return "NOT AVAILABLE" if value is None else f"{value:.3f} s"


def render_report(
    command: str,
    base_url: str,
    request_count: int,
    live: dict[str, Any],
    adversarial: dict[str, Any] | None,
    adversarial_error: str | None,
) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# FanCue Evaluation Results",
        "",
        f"- **Execution date (UTC):** {now}",
        f"- **Exact command:** {command}",
        f"- **API base URL:** {base_url}",
        f"- **Requested live catch-ups:** {request_count}",
        "- **Status:** results below are written by the evaluator; unavailable values are explicitly marked.",
        "",
        "## Deployed API measurements",
        "",
    ]
    if live.get("error"):
        lines.extend(
            [
                f"- **Live API run:** INCOMPLETE — {live['error']}",
                "- **p50 latency:** NOT AVAILABLE",
                "- **p95 latency:** NOT AVAILABLE",
                "- **Fallback rate:** NOT AVAILABLE",
                "- **Verifier rejection proxy rate:** NOT AVAILABLE",
            ]
        )
    else:
        lines.extend(
            [
                f"- **HTTP catch-up responses:** {live['completed_http_responses']} / {live['requested_catchups']}",
                f"- **Successful catch-ups (HTTP 200 + JSON object):** {live['successful_catchups']}",
                f"- **Failed attempts:** {live['failed_attempts']}",
                f"- **p50 latency:** {seconds(live['p50_seconds'])}",
                f"- **p95 latency:** {seconds(live['p95_seconds'])}",
                f"- **Fallback rate among successful catch-ups:** {percent(live['fallback_rate_percent'])}",
                f"- **Verifier-rejection fallback proxy rate:** {percent(live['verifier_rejection_proxy_rate_percent'])}",
                "",
                "**Metric definitions:** fallback rate = responses whose generation_mode is deterministic_fallback divided by successful catch-ups. The API does not expose raw verifier draft counts; the verifier-rejection proxy counts responses whose fallback_reason is fact_mismatch or unsupported_claims. This is not a direct per-draft rejection rate. p50/p95 use nearest-rank percentiles of attempts with an HTTP response; transport failures are excluded from latency percentiles.",
            ]
        )

    lines.extend(["", "### Per-request observations", ""])
    attempts = live.get("attempts", [])
    if not attempts:
        lines.append("No catch-up attempts produced request observations.")
    else:
        lines.extend(
            [
                "| # | Fixture | Interval | HTTP | Seconds | Generation mode | Verification | Fallback reason | Outcome |",
                "|---:|---|---|---:|---:|---|---|---|---|",
            ]
        )
        for a in attempts:
            iv = a.get("interval", {})
            interval_label = f"{iv.get('start_after_over')}→{iv.get('end_after_over')} (inn {iv.get('innings')})"
            lines.append(
                f"| {a.get('index')} | {a.get('match_id')} | {interval_label} | "
                f"{a.get('http_status', '—')} | {a.get('elapsed_seconds', 0):.3f} | "
                f"{a.get('generation_mode', '—')} | {a.get('verification_status', '—')} | "
                f"{a.get('fallback_reason', '—')} | {a.get('outcome', '—')} |"
            )

    lines.extend(["", "## Local adversarial verifier checks", ""])
    if adversarial_error:
        lines.append(f"- **Status:** NOT RUN — {adversarial_error}")
    elif adversarial:
        lines.extend(
            [
                f"- **Fixture-derived packet:** {adversarial['fixture']} interval "
                f"{adversarial['interval']}",
                f"- **Rejected fake drafts:** {adversarial['rejected_cases']} / {adversarial['adversarial_cases']}",
                f"- **Measured adversarial rejection rate:** {percent(adversarial['rejection_rate_percent'])}",
                "",
                "| Adversarial draft | Rejected | Verification returned | Rejection reasons |",
                "|---|---|---|---|",
            ]
        )
        for item in adversarial["results"]:
            lines.append(
                f"| {item['case']} | {'yes' if item['rejected'] else 'no'} | "
                f"{'verified' if item['is_verified'] else 'not verified'} | "
                f"{', '.join(item['rejection_reasons']) or 'none'} |"
            )
    lines.extend(
        [
            "",
            "## Reproducibility and limitations",
            "",
            "- Live requests are real calls to the configured API. Catch-up POST requests are not retried.",
            "- This is a small evaluation sample, not a general performance guarantee or a fan-engagement study.",
            "- The adversarial set is a small fixed set of deliberately incorrect drafts, not a broad red-team benchmark.",
            "- Current Render configuration disables Qdrant retrieval; this run does not measure production retrieval.",
            "",
        ]
    )
    return "\\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("FANCUE_API_BASE_URL", DEFAULT_API_BASE),
        help="Live API base URL; defaults to FANCUE_API_BASE_URL or the Render URL.",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=20,
        help="Number of live POST /catchup requests to attempt (default: 20; maximum: 100).",
    )
    parser.add_argument("--timeout", type=float, default=90.0, help="Per-request timeout in seconds.")
    parser.add_argument(
        "--output",
        default="docs/eval_results.md",
        help="Markdown report path (default: docs/eval_results.md).",
    )
    args = parser.parse_args()
    if not 1 <= args.requests <= 100:
        parser.error("--requests must be between 1 and 100.")
    if args.timeout <= 0:
        parser.error("--timeout must be positive.")

    # This records the exact CLI argument vector used to launch the evaluator.
    command = shlex.join([sys.executable, *sys.argv])
    base_url = args.base_url.rstrip("/")
    print(f"Live evaluation: base_url={base_url} requested_catchups={args.requests}")
    live = run_live_evaluation(base_url, args.requests, args.timeout)
    if live.get("error"):
        print(f"LIVE API SETUP INCOMPLETE: {live['error']}")
    else:
        print(f"HTTP responses: {live['completed_http_responses']}/{args.requests}")
        print(f"Successful catch-ups: {live['successful_catchups']}")
        print(f"Failed attempts: {live['failed_attempts']}")
        print(f"p50 latency: {seconds(live['p50_seconds'])}")
        print(f"p95 latency: {seconds(live['p95_seconds'])}")
        print(f"fallback rate: {percent(live['fallback_rate_percent'])}")
        print(
            "verifier rejection fallback proxy rate: "
            + percent(live["verifier_rejection_proxy_rate_percent"])
        )

    adversarial = None
    adversarial_error = None
    try:
        adversarial = make_local_adversarial_report()
        print(
            f"Local adversarial verifier: {adversarial['rejected_cases']}/"
            f"{adversarial['adversarial_cases']} drafts rejected "
            f"({percent(adversarial['rejection_rate_percent'])})"
        )
        for item in adversarial["results"]:
            print(
                f"  {item['case']}: rejected={item['rejected']} "
                f"reasons={','.join(item['rejection_reasons']) or 'none'}"
            )
    except Exception as exc:
        adversarial_error = f"{type(exc).__name__}: {exc}"
        print(f"LOCAL ADVERSARIAL CHECK INCOMPLETE: {adversarial_error}")

    report = render_report(
        command=command,
        base_url=base_url,
        request_count=args.requests,
        live=live,
        adversarial=adversarial,
        adversarial_error=adversarial_error,
    )
    output_path = (ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Report written to: {output_path}")

    return 0 if not live.get("error") and live["successful_catchups"] > 0 and not adversarial_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
