# FanCue Public Demo Acceptance Runbook

This is the release gate for a public review. Passing unit tests or a healthy process does not prove that the deployed user journey works.

## Deployment contract

- Frontend: `https://fan-cue.vercel.app`
- Backend: set `VITE_API_BASE_URL` in Vercel to the Render API URL (no trailing slash).
- Backend: set `FANCUE_ENV=production`.
- Backend: set `ALLOWED_ORIGINS=https://fan-cue.vercel.app` (add other exact production origins only when required).
- LLM credentials belong in Render environment variables/secret settings, never in `VITE_*` variables.
- Retrieval is optional. If disabled or unreachable, historical replay should still use authoritative fixture facts and label deterministic output accurately.
- Confirm fixtures are included in the deployed Docker image. An ignored local `data/raw/` directory is not proof of deployed fixture availability.

## Release gate

### 1. Liveness and readiness

```bash
curl -sS -o /dev/null -w 'healthz status=%{http_code} elapsed=%{time_total}s\n' \
  https://fancue-api-o4r1.onrender.com/healthz
curl -sS -o /dev/null -w 'readyz status=%{http_code} elapsed=%{time_total}s\n' \
  https://fancue-api-o4r1.onrender.com/readyz
```

Interpret endpoints separately:
- `/healthz` confirms the process is responding only.
- `/readyz` reports fixtures, retrieval mode, and LLM mode; it does not prove a browser catch-up succeeds.
- Record first-request and warm-request latency. A monitor is not a guarantee of availability.

### 2. Inspect routes

```bash
curl -fsS https://fancue-api-o4r1.onrender.com/openapi.json \
  | python -c "import json,sys; d=json.load(sys.stdin); [print(m.upper(),p) for p,v in d['paths'].items() for m in v]"
```

The contract includes `GET /healthz`, `GET /readyz`, `GET /matches`, `GET /matches/{match_id}/intervals`, and `POST /catchup`, plus optional near-live routes.

### 3. CORS preflight

```bash
curl -sS -D - -o /dev/null -X OPTIONS \
  https://fancue-api-o4r1.onrender.com/catchup \
  -H 'Origin: https://fan-cue.vercel.app' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type'
```

Confirm exact `Access-Control-Allow-Origin: https://fan-cue.vercel.app` and that POST/content-type are allowed. Use the actual frontend origin if it differs.

### 4. Exercise the real user journey

In a private/incognito browser window:
1. Open the deployed frontend.
2. Confirm the match catalogue loads.
3. Select a supported historical match and a valid interval.
4. Confirm the response succeeds and the story renders.
5. Inspect the response: statuses are under `explanation.generation_mode` and `explanation.verification_status`.
6. Reconcile displayed deltas with `state_before`, `state_after`, and `state_delta`; inspect an event's evidence reference.
7. Repeat after inactivity and record cold-start and warm-request latency.
8. Simulate LLM/retrieval failure in a safe test environment and verify labelled deterministic fallback. Do not change production credentials during a submission window to test failure.

Record timestamp, frontend/backend URLs, deployed commit, HTTP status, latency, generation mode, verification status and screenshots. Never include secrets.

## Cricket correctness audit

Test innings start, complete and partial over boundaries, wides/no-balls, retired hurt/retired out, and run-outs. Cricket overs use base-six legal balls: `16.5` means 16 overs and 5 legal balls, not decimal 16.5. A run-out must not automatically credit the bowler with a wicket.

## Troubleshooting

- **CORS failure:** correct `ALLOWED_ORIGINS` in Render, redeploy, repeat preflight and browser test.
- **Missing matches/fixtures:** check `/readyz`, Render logs, Docker copy rules and fixture provisioning. Never invent fixtures to populate the UI.
- **LLM failure:** deterministic output is acceptable when labelled as fallback and scores remain engine-derived.
- **Retrieval failure:** keep retrieval optional; the match engine remains authoritative.
- **Cold start:** disclose measured waiting in the loading state. An uptime monitor may reduce idle starts within host rules but is not an availability guarantee.
- **CI green but demo broken:** end-to-end acceptance has failed; CI covers only the tested code revision and paths.

## Submission policy

Do not claim public end-to-end validation, live provider operation, active retrieval, or exact test totals unless the latest run against the relevant revision supports the claim.

## Automated smoke test and live evaluation

From the repository root, run the smoke test against the public service:

    python scripts/smoke_test.py --api-base-url https://fancue-api-o4r1.onrender.com --frontend-origin https://fan-cue.vercel.app

It checks /healthz, the match catalogue, the exact CORS preflight origin, and one real POST /catchup for each registered fixture (1529229 and 1552779). It prints each response's generation_mode, verification_status, fallback_reason, and observed request duration. A deterministic fallback is a valid degraded response; inspect the UI label rather than treating fallback as a successful AI generation.

To run the live operational sample (20 catch-ups by default) and append measured results to docs/eval_results.md:

    python scripts/evaluate_catchups.py --api-base-url https://fancue-api-o4r1.onrender.com --requests 20 --output docs/eval_results.md

The evaluator alternates across both fixtures and selects only intervals advertised by the deployed API. It reports p50/p95 client-observed latency, request failures, deterministic fallback rate, and verifier rejection rate among responses that show a draft reached verification. It uses a one-second delay by default and caps a run at 50 requests to leave margin under the API's in-process per-minute rate limit.

Both scripts use Python's standard library only. They make real public API calls; run them from a machine with internet access. Do not report latency or fallback rates until the command has completed, and commit the generated docs/eval_results.md after reviewing the actual output.
