#!/usr/bin/env python3
"""Smoke-test the deployed FanCue API against both supported historical fixtures.

Example:
  python scripts/smoke_test.py --api-base-url https://fancue-api-o4r1.onrender.com \\
      --frontend-origin https://fan-cue.vercel.app

Uses only the Python standard library. This script performs real HTTP requests.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_API_BASE_URL = "https://fancue-api-o4r1.onrender.com"
DEFAULT_FRONTEND_ORIGIN = "https://fan-cue.vercel.app"
SUPPORTED_FIXTURES = ("1529229", "1552779")


class SmokeTestError(RuntimeError):
    """Raised when a deployed API check fails."""


def request_json(
    api_base_url: str,
    path: str,
    *,
    timeout_seconds: float = 90.0,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
):
    """Issue one JSON HTTP request and return (status, decoded body, headers)."""
    url = f"{api_base_url.rstrip('/')}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError as exc:
                raise SmokeTestError(f"{method} {path} returned invalid JSON.") from exc
            return response.status, body, response.headers
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SmokeTestError(f"{method} {path} returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SmokeTestError(f"{method} {path} could not connect: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SmokeTestError(f"{method} {path} timed out after {timeout_seconds:g}s.") from exc


def choose_interval(interval_response: dict[str, Any]) -> dict[str, Any]:
    """Pick a valid API-advertised interval closest to five overs; never invent bounds."""
    intervals = interval_response.get("intervals")
    if not isinstance(intervals, list) or not intervals:
        raise SmokeTestError(
            f"No valid intervals returned for match {interval_response.get('match_id', '?')}."
        )

    valid = [
        item for item in intervals
        if isinstance(item, dict)
        and isinstance(item.get("start_after_over"), int)
        and isinstance(item.get("end_after_over"), int)
        and isinstance(item.get("innings"), int)
        and item["end_after_over"] > item["start_after_over"]
    ]
    if not valid:
        raise SmokeTestError("API returned no well-formed, non-empty intervals.")

    return min(
        valid,
        key=lambda item: (
            abs((item["end_after_over"] - item["start_after_over"]) - 5),
            item["start_after_over"],
            item["end_after_over"],
        ),
    )


def check_cors(api_base_url: str, frontend_origin: str, timeout_seconds: float) -> None:
    """Check an actual browser-style preflight response for the exact frontend origin."""
    url = f"{api_base_url.rstrip('/')}/catchup"
    request = Request(
        url,
        data=None,
        headers={
            "Origin": frontend_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        method="OPTIONS",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = response.status
            allowed_origin = response.headers.get("Access-Control-Allow-Origin")
            allowed_methods = response.headers.get("Access-Control-Allow-Methods", "")
    except HTTPError as exc:
        raise SmokeTestError(f"CORS preflight returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise SmokeTestError(f"CORS preflight could not connect: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SmokeTestError(f"CORS preflight timed out after {timeout_seconds:g}s.") from exc

    print(f"CORS preflight: HTTP {status}; allow-origin={allowed_origin!r}")
    if status not in (200, 204):
        raise SmokeTestError(f"CORS preflight returned unexpected HTTP status {status}.")
    if allowed_origin != frontend_origin:
        raise SmokeTestError(
            f"CORS origin mismatch: expected {frontend_origin!r}, received {allowed_origin!r}."
        )
    if "POST" not in allowed_methods.upper():
        raise SmokeTestError(f"CORS does not advertise POST in allowed methods: {allowed_methods!r}.")


def run_smoke(api_base_url: str, frontend_origin: str, timeout_seconds: float) -> int:
    print("FanCue deployed smoke test")
    print(f"api_base_url={api_base_url.rstrip('/')}")
    print(f"frontend_origin={frontend_origin}")
    print(f"timeout_seconds={timeout_seconds:g}")

    status, health, _ = request_json(
        api_base_url, "/healthz", timeout_seconds=timeout_seconds
    )
    print(f"GET /healthz: HTTP {status} status={health.get('status')!r}")
    if status != 200 or health.get("status") != "ok":
        raise SmokeTestError("Health check did not report status=ok.")

    status, catalogue, _ = request_json(
        api_base_url, "/matches", timeout_seconds=timeout_seconds
    )
    matches = catalogue.get("matches", [])
    match_ids = {str(item.get("match_id")) for item in matches if isinstance(item, dict)}
    print(f"GET /matches: HTTP {status}; fixture_ids={','.join(sorted(match_ids))}")
    if status != 200:
        raise SmokeTestError("Match catalogue did not return HTTP 200.")

    missing = sorted(set(SUPPORTED_FIXTURES) - match_ids)
    if missing:
        raise SmokeTestError(f"Supported fixture IDs missing from deployed API: {', '.join(missing)}")

    check_cors(api_base_url, frontend_origin, timeout_seconds)

    for match_id in SUPPORTED_FIXTURES:
        status, intervals_response, _ = request_json(
            api_base_url,
            f"/matches/{match_id}/intervals",
            timeout_seconds=timeout_seconds,
        )
        if status != 200:
            raise SmokeTestError(f"Interval discovery for {match_id} returned HTTP {status}.")
        interval = choose_interval(intervals_response)
        body = {
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
        status, response, _ = request_json(
            api_base_url,
            "/catchup",
            timeout_seconds=timeout_seconds,
            method="POST",
            payload=body,
        )
        elapsed = time.perf_counter() - started
        explanation = response.get("explanation", {})
        generation_mode = explanation.get("generation_mode")
        verification_status = explanation.get("verification_status")
        fallback_reason = explanation.get("fallback_reason")
        print(
            f"POST /catchup match_id={match_id} HTTP {status} "
            f"interval=({interval['start_after_over']},{interval['end_after_over']}] "
            f"generation_mode={generation_mode!r} "
            f"verification_status={verification_status!r} "
            f"fallback_reason={fallback_reason!r} elapsed_seconds={elapsed:.3f}"
        )
        if status != 200:
            raise SmokeTestError(f"Catch-up for fixture {match_id} returned HTTP {status}.")
        if not generation_mode or not verification_status:
            raise SmokeTestError(
                f"Catch-up for fixture {match_id} omitted generation/verification status."
            )

    print("RESULT: PASS — both supported fixtures returned a catch-up response.")
    print("Note: deterministic_fallback is a valid degraded path; inspect its label in the UI.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--frontend-origin", default=DEFAULT_FRONTEND_ORIGIN)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    args = parser.parse_args()
    try:
        return run_smoke(args.api_base_url, args.frontend_origin, args.timeout_seconds)
    except SmokeTestError as exc:
        print(f"RESULT: FAIL — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
