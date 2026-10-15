#!/usr/bin/env python3
"""Measure live FanCue catch-up latency, fallback rate, and verifier rejection rate.

Default is 20 sequential requests, alternating between the two tracked fixtures.
The script calls the deployed API and appends measured results to docs/eval_results.md.
It makes no API key assumptions and uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import shlex
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.smoke_test import (
    DEFAULT_API_BASE_URL,
    SUPPORTED_FIXTURES,
    SmokeTestError,
    choose_interval,
    request_json,
)


VERIFIER_REJECTION_REASONS = {"fact_mismatch", "unsupported_claims"}
PLACEHOLDER_START = "<!-- LIVE_EVALUATION_NOT_RUN_START -->"
PLACEHOLDER_END = "<!-- LIVE_EVALUATION_NOT_RUN_END -->"


def percentile(values: list[float], quantile: float) -> float | None:
    """Return a linearly interpolated percentile; returns None for no observations."""
    if not values:
        return None
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def is_verifier_rejection(generation_mode: str | None, fallback_reason: str | None) -> bool:
    """Use the API's explicit fallback reason to identify drafts rejected by verification."""
    return (
        generation_mode == "deterministic_fallback"
        and fallback_reason in VERIFIER_REJECTION_REASONS
    )


def verifier_was_reached(generation_mode: str | None, fallback_reason: str | None) -> bool:
    """A verified LLM response passed the verifier; mismatch/unsupported fallback means rejection."""
    return (
        generation_mode == "llm_verified"
        or is_verifier_rejection(generation_mode, fallback_reason)
    )


def _command_line() -> str:
    """Prefer Python's original argv so the recorded command matches the invocation."""
    original = getattr(sys, "orig_argv", None)
    if original:
        return shlex.join(original)
    return shlex.join([Path(sys.executable).name, *sys.argv])


def _format_metric(value: float | None, unit: str = "s") -> str:
    return "n/a" if value is None else f"{value:.3f}{unit}"


def _load_intervals(api_base_url: str, timeout_seconds: float) -> dict[str, dict[str, Any]]:
    status, catalogue, _ = request_json(
        api_base_url, "/matches", timeout_seconds=timeout_seconds
    )
    if status != 200:
        raise SmokeTestError(f"GET /matches returned HTTP {status}.")

    available = {
        str(item.get("match_id"))
        for item in catalogue.get("matches", [])
        if isinstance(item, dict)
    }
    missing = sorted(set(SUPPORTED_FIXTURES) - available)
    if missing:
        raise SmokeTestError(
            "The deployed match catalogue is missing supported fixture IDs: "
            + ", ".join(missing)
        )

    chosen: dict[str, dict[str, Any]] = {}
    for match_id in SUPPORTED_FIXTURES:
        status, response, _ = request_json(
            api_base_url,
            f"/matches/{match_id}/intervals",
            timeout_seconds=timeout_seconds,
        )
        if status != 200:
            raise SmokeTestError(
                f"GET /matches/{match_id}/intervals returned HTTP {status}."
            )
        chosen[match_id] = choose_interval(response)
    return chosen


def _record_report(output_path: Path, run_section: str) -> None:
    """Replace the pending placeholder on first run; append each subsequent measured run."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        current = output_path.read_text(encoding="utf-8")
    else:
        current = "# FanCue Evaluation Results\n"

    if PLACEHOLDER_START in current and PLACEHOLDER_END in current:
        before = current.split(PLACEHOLDER_START, 1)[0]
        after = current.split(PLACEHOLDER_END, 1)[1]
        updated = before + run_section + after
    else:
        updated = current.rstrip() + "\n\n" + run_section
    output_path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def run_evaluation(
    api_base_url: str,
    request_count: int = 20,
    timeout_seconds: float = 90.0,
    delay_seconds: float = 1.0,
    output_path: Path | None = None,
) -> int:
    if not 1 <= request_count <= 50:
        raise ValueError("--requests must be between 1 and 50 to stay below the API's per-minute limit.")
    if timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive.")
    if delay_seconds < 0:
        raise ValueError("--delay-seconds cannot be negative.")

    intervals = _load_intervals(api_base_url, timeout_seconds)
    durations_seconds: list[float] = []
    successful: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    print("FanCue live catch-up evaluation")
    print(f"api_base_url={api_base_url.rstrip('/')}")
    print(f"requested_catchups={request_count}")
    print("latency_population=all POST attempts, including HTTP/transport failures")
    print("fallback_rate_denominator=HTTP 200 catch-up responses")
    print("verifier_rejection_rate_denominator=responses that reached verifier (verified or rejected)")

    for index in range(request_count):
        match_id = SUPPORTED_FIXTURES[index % len(SUPPORTED_FIXTURES)]
        interval = intervals[match_id]
        payload = {
            "match_id": match_id,
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
        status: int | None = None
        response: dict[str, Any] = {}
        error = ""
        try:
            status, response, _ = request_json(
                api_base_url,
                "/catchup",
                timeout_seconds=timeout_seconds,
                method="POST",
                payload=payload,
            )
            if status != 200:
                error = f"HTTP {status}"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        durations_seconds.append(elapsed)

        if status == 200 and not error:
            explanation = response.get("explanation", {})
            row = {
                "request": index + 1,
                "match_id": match_id,
                "http_status": status,
                "generation_mode": explanation.get("generation_mode"),
                "verification_status": explanation.get("verification_status"),
                "fallback_reason": explanation.get("fallback_reason"),
                "latency_seconds": elapsed,
                "error": "",
            }
            successful.append(row)
            print(
                f"request={index + 1:02d}/{request_count} HTTP={status} match_id={match_id} "
                f"generation_mode={row['generation_mode']} "
                f"verification_status={row['verification_status']} "
                f"fallback_reason={row['fallback_reason']} latency_seconds={elapsed:.3f}"
            )
        else:
            row = {
                "request": index + 1,
                "match_id": match_id,
                "http_status": status if status is not None else "transport_error",
                "generation_mode": None,
                "verification_status": None,
                "fallback_reason": None,
                "latency_seconds": elapsed,
                "error": error or "No successful JSON response",
            }
            failures.append(row)
            print(
                f"request={index + 1:02d}/{request_count} FAIL match_id={match_id} "
                f"latency_seconds={elapsed:.3f} error={row['error']}"
            )

        if index + 1 < request_count and delay_seconds:
            time.sleep(delay_seconds)

    p50 = percentile(durations_seconds, 0.50)
    p95 = percentile(durations_seconds, 0.95)
    fallback_count = sum(
        row["generation_mode"] == "deterministic_fallback" for row in successful
    )
    verifier_checked = [
        row for row in successful
        if verifier_was_reached(row["generation_mode"], row["fallback_reason"])
    ]
    verifier_rejected = sum(
        is_verifier_rejection(row["generation_mode"], row["fallback_reason"])
        for row in verifier_checked
    )
    fallback_rate = fallback_count / len(successful) if successful else None
    verifier_rejection_rate = (
        verifier_rejected / len(verifier_checked) if verifier_checked else None
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    command = _command_line()

    print(f"completed_requests={len(successful)}")
    print(f"failed_requests={len(failures)}")
    print(f"latency_p50_seconds={_format_metric(p50)}")
    print(f"latency_p95_seconds={_format_metric(p95)}")
    print(
        "fallback_rate="
        + ("n/a" if fallback_rate is None else f"{fallback_count}/{len(successful)} ({fallback_rate * 100:.1f}%)")
    )
    print(
        "verifier_rejection_rate="
        + (
            "n/a (no drafts reached verifier)"
            if verifier_rejection_rate is None
            else f"{verifier_rejected}/{len(verifier_checked)} ({verifier_rejection_rate * 100:.1f}%)"
        )
    )

    lines = [
        f"## Live catch-up evaluation — {timestamp}",
        "",
        f"- Exact command: {command}",
        f"- API base URL: {api_base_url.rstrip('/')}",
        f"- Requested catch-ups: {request_count}",
        f"- Successful HTTP 200 responses: {len(successful)}",
        f"- Failed/transport-error requests: {len(failures)}",
        f"- p50 client-observed POST latency (all attempts): {_format_metric(p50)}",
        f"- p95 client-observed POST latency (all attempts): {_format_metric(p95)}",
        f"- Deterministic fallback rate: {'n/a' if fallback_rate is None else f'{fallback_count}/{len(successful)} ({fallback_rate * 100:.1f}%)'}",
        (
            "- Verifier rejection rate among drafts that reached verification: "
            + (
                "n/a (no generated drafts reached verifier)"
                if verifier_rejection_rate is None
                else f"{verifier_rejected}/{len(verifier_checked)} ({verifier_rejection_rate * 100:.1f}%)"
            )
        ),
        "",
        "Verifier-rejection definition: fallback reason is fact_mismatch or unsupported_claims. "
        "Provider failures/timeouts and disabled generation are not counted as verifier attempts.",
        "",
        "| # | Fixture | HTTP | Generation mode | Verification status | Fallback reason | Latency (s) | Error |",
        "|---:|---|---:|---|---|---|---:|---|",
    ]
    for row in [*successful, *failures]:
        error = str(row["error"]).replace("|", "/")
        lines.append(
            f"| {row['request']} | {row['match_id']} | {row['http_status']} | "
            f"{row['generation_mode'] or 'n/a'} | {row['verification_status'] or 'n/a'} | "
            f"{row['fallback_reason'] or 'n/a'} | {row['latency_seconds']:.3f} | {error} |"
        )
    section = "\n".join(lines) + "\n"
    output_path = output_path or (Path(__file__).resolve().parents[1] / "docs" / "eval_results.md")
    _record_report(output_path, section)
    print(f"results_saved={output_path}")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "eval_results.md",
    )
    args = parser.parse_args()
    try:
        return run_evaluation(
            api_base_url=args.api_base_url,
            request_count=args.requests,
            timeout_seconds=args.timeout_seconds,
            delay_seconds=args.delay_seconds,
            output_path=args.output,
        )
    except (SmokeTestError, ValueError) as exc:
        print(f"Evaluation setup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
