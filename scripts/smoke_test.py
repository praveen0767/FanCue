#!/usr/bin/env python3
"""Smoke-test the deployed FanCue API against both registered cricket fixtures.

This script sends real requests to the configured API. It does not mock providers
or write evaluation results. Catch-up calls are intentionally not retried because
a retry could make a second paid/rate-limited LLM request.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API_BASE = "https://fancue-api-o4r1.onrender.com"
DEFAULT_FRONTEND_ORIGIN = "https://fan-cue.vercel.app"
FIXTURE_IDS = ("1529229", "1552779")


class SmokeError(RuntimeError):
    """A request failed before a useful HTTP response could be inspected."""


def request_raw(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 90.0,
) -> tuple[int, Any, bytes, float]:
    """Return HTTP status, headers, body, elapsed seconds, including HTTP error bodies."""
    url = f"{base_url.rstrip('/')}{path}"
    request_headers = {"Accept": "application/json", **(headers or {})}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    req = Request(url, data=data, headers=request_headers, method=method)
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read()
            return response.status, response.headers, body, time.perf_counter() - started
    except HTTPError as exc:
        body = exc.read()
        return exc.code, exc.headers, body, time.perf_counter() - started
    except (URLError, TimeoutError, OSError) as exc:
        raise SmokeError(f"{method} {path}: {type(exc).__name__}: {exc}") from exc


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 90.0,
) -> tuple[int, Any, float]:
    status, _headers, body, elapsed = request_raw(
        base_url, path, method=method, payload=payload, timeout=timeout
    )
    try:
        parsed = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        snippet = body[:300].decode("utf-8", errors="replace")
        raise SmokeError(f"{method} {path} returned non-JSON body: {snippet!r}") from exc
    return status, parsed, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run real public API catch-up checks for both supported FanCue fixtures."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("FANCUE_API_BASE_URL", DEFAULT_API_BASE),
        help="Render API base URL (defaults to FANCUE_API_BASE_URL or the known Render URL).",
    )
    parser.add_argument(
        "--frontend-origin",
        default=os.environ.get("FANCUE_FRONTEND_ORIGIN", DEFAULT_FRONTEND_ORIGIN),
        help="Exact production browser origin for the CORS preflight check.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Per-request timeout in seconds (default: 90; allow for a Render cold start).",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    frontend_origin = args.frontend_origin
    failures = 0

    print("FanCue deployed API smoke test")
    print(f"API base URL: {base_url}")
    print(f"Expected frontend origin: {frontend_origin}")
    print(f"Fixtures: {', '.join(FIXTURE_IDS)}")
    print(f"Per-request timeout: {args.timeout:g}s")
    print("Note: catch-up POST requests are not retried.\n")

    # Warm the sleeping service first. Retry health once because this GET is safe.
    health_ok = False
    for attempt in range(1, 3):
        try:
            status, payload, elapsed = request_json(
                base_url, "/healthz", timeout=args.timeout
            )
            print(
                f"healthz attempt={attempt} status={status} "
                f"elapsed={elapsed:.2f}s payload={json.dumps(payload, sort_keys=True)}"
            )
            if status == 200 and payload.get("status") == "ok":
                health_ok = True
                break
            print("  FAIL: /healthz did not return HTTP 200 with status=ok.")
        except SmokeError as exc:
            print(f"healthz attempt={attempt} FAIL: {exc}")
        if attempt == 1:
            print("  Retrying the safe health request once after a short pause...")
            time.sleep(2)

    if not health_ok:
        failures += 1

    # CORS is checked separately from Python API requests; Python itself is not
    # blocked by browser CORS enforcement.
    try:
        status, headers, _body, elapsed = request_raw(
            base_url,
            "/catchup",
            method="OPTIONS",
            headers={
                "Origin": frontend_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
            timeout=args.timeout,
        )
        allowed_origin = headers.get("Access-Control-Allow-Origin")
        allowed_methods = headers.get("Access-Control-Allow-Methods", "")
        cors_ok = (
            status in (200, 204)
            and allowed_origin == frontend_origin
            and "POST" in allowed_methods
        )
        print(
            f"CORS preflight status={status} elapsed={elapsed:.2f}s "
            f"allow_origin={allowed_origin!r} allow_methods={allowed_methods!r} "
            f"result={'PASS' if cors_ok else 'FAIL'}"
        )
        if not cors_ok:
            failures += 1
    except SmokeError as exc:
        print(f"CORS preflight FAIL: {exc}")
        failures += 1

    try:
        status, matches_payload, elapsed = request_json(
            base_url, "/matches", timeout=args.timeout
        )
        print(f"matches status={status} elapsed={elapsed:.2f}s")
        if status != 200:
            print(f"  FAIL: {json.dumps(matches_payload, sort_keys=True)}")
            return 1
        matches = matches_payload.get("matches", [])
        available_ids = {str(item.get("match_id")) for item in matches}
        print(f"matches returned={len(matches)} fixture_ids={','.join(sorted(available_ids))}")
    except (SmokeError, AttributeError, TypeError) as exc:
        print(f"GET /matches FAIL: {exc}")
        return 1

    for match_id in FIXTURE_IDS:
        print(f"\n--- fixture {match_id} ---")
        if match_id not in available_ids:
            print(f"FAIL: fixture {match_id} is not listed by GET /matches.")
            failures += 1
            continue

        try:
            status, interval_payload, elapsed = request_json(
                base_url, f"/matches/{match_id}/intervals", timeout=args.timeout
            )
            intervals = interval_payload.get("intervals", []) if isinstance(interval_payload, dict) else []
            print(
                f"intervals status={status} elapsed={elapsed:.2f}s "
                f"available={len(intervals)}"
            )
            if status != 200 or not intervals:
                print(f"FAIL: no usable interval: {json.dumps(interval_payload, sort_keys=True)}")
                failures += 1
                continue

            # Use a valid interval returned by the deployed engine; never invent
            # or hardcode a score or an interval boundary.
            interval = intervals[0]
            request_payload = {
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
            status, result, elapsed = request_json(
                base_url,
                "/catchup",
                method="POST",
                payload=request_payload,
                timeout=args.timeout,
            )
            if status != 200 or not isinstance(result, dict):
                print(
                    f"catchup status={status} elapsed={elapsed:.2f}s "
                    f"FAIL body={json.dumps(result, sort_keys=True)}"
                )
                failures += 1
                continue

            explanation = result.get("explanation") or {}
            delta = result.get("state_delta") or {}
            generation_mode = explanation.get("generation_mode", "MISSING")
            verification_status = explanation.get("verification_status", "MISSING")
            fallback_reason = explanation.get("fallback_reason", "MISSING")
            has_evidence = bool((result.get("evidence_packet") or {}).get("key_facts"))
            fields_ok = generation_mode in ("llm_verified", "deterministic_fallback") and verification_status != "MISSING" and has_evidence
            print(f"interval={json.dumps(request_payload['interval'], sort_keys=True)}")
            print(f"catchup status={status} elapsed={elapsed:.2f}s")
            print(f"generation_mode={generation_mode}")
            print(f"verification_status={verification_status}")
            print(f"fallback_reason={fallback_reason}")
            print(
                "state_delta="
                + json.dumps(
                    {
                        "runs_added": delta.get("runs_added"),
                        "wickets_lost": delta.get("wickets_lost"),
                        "completed_overs_delta": delta.get("completed_overs_delta"),
                    },
                    sort_keys=True,
                )
            )
            print(f"evidence_key_facts={len((result.get('evidence_packet') or {}).get('key_facts') or [])}")
            if not fields_ok:
                print("FAIL: response is missing an expected explanation status or evidence.")
                failures += 1
            else:
                print("Result: PASS (HTTP contract/status fields present; review story and score manually).")
        except (SmokeError, KeyError, TypeError, AttributeError) as exc:
            print(f"catchup FAIL: {exc}")
            failures += 1

    print(f"\nSmoke test result: {'PASS' if failures == 0 else 'FAIL'}; failures={failures}")
    print("This script does not prove the UI renders correctly. Open the Vercel app and complete the browser gate in docs/PUBLIC_DEMO_ACCEPTANCE.md.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
