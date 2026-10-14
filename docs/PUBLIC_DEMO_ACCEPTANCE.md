# FanCue Public Demo Acceptance Runbook

This runbook is the release gate for a public review. A green unit-test suite or a healthy process is not proof that the user-visible journey works.

## Deployment contract

- Frontend: `https://fan-cue.vercel.app`
- Backend: set `VITE_API_BASE_URL` in Vercel to the deployed Render service URL (no trailing slash).
- Backend: set `FANCUE_ENV=production`.
- Backend: set `ALLOWED_ORIGINS=https://fan-cue.vercel.app` (add any other exact, legitimate production origins as comma-separated values only when needed).
- LLM: configure the selected provider's server-side key in Render. Never put provider keys in `VITE_*` variables.
- Retrieval: optional. When disabled or unreachable, historical replay must still use authoritative fixture facts and clearly labelled deterministic output.
- Fixtures: ensure the Docker image contains all supported fixture files. Do not treat the repository's ignored `data/raw/` folder as proof that the Render image has them.

## Release gate

Run these checks against the deployed revision before submitting the link.

### 1. Process liveness and readiness

```bash
curl -sS -o /dev/null -w 'healthz status=%{http_code} elapsed=%{time_total}s\n' \
  https://fancue-api-o4r1.onrender.com/healthz
curl -sS -o /dev/null -w 'readyz status=%{http_code} elapsed=%{time_total}s\n' \
  https://fancue-api-o4r1.onrender.com/readyz
```

Interpret the endpoints separately:
- `/healthz` is process liveness only.
- `/readyz` reports fixture availability and whether retrieval is ready, bypassed, or unreachable. It does not prove that the browser can complete a catch-up.
- A slow first request may indicate a cold start. Record first-request and warm-request latency rather than assuming an uptime monitor fixes it.

### 2. Confirm endpoint contracts

```bash
curl -fsS https://fancue-api-o4r1.onrender.com/openapi.json \
  | python -c "import json,sys; d=json.load(sys.stdin); [print(m.upper(),p) for p,v in d['paths'].items() for m in v]"
```

The current application contract is `GET /healthz`, `GET /readyz`, `GET /matches`, `GET /matches/{match_id}/intervals`, and `POST /catchup`, with additional near-live routes where configured.

### 3. Check CORS preflight

```bash
curl -sS -D - -o /dev/null -X OPTIONS \
  https://fancue-api-o4r1.onrender.com/catchup \
  -H 'Origin: https://fan-cue.vercel.app' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type'
```

Confirm the response includes `Access-Control-Allow-Origin: https://fan-cue.vercel.app` and allows POST and the content-type header. A local/API-only test cannot substitute for this check.

### 4. Exercise the actual user journey

In an incognito/private browser window:
1. Open the deployed Vercel URL.
2. Confirm match list loads.
3. Select a bundled historical match and a valid interval.
4. Confirm catch-up returns successfully and the story renders.
5. Inspect the Network response. The generation status is under `explanation.generation_mode`; the verification status is under `explanation.verification_status`.
6. Confirm the displayed score delta agrees with `state_before`, `state_after`, and `state_delta`; inspect at least one event's evidence identifier.
7. Repeat once after the service has been idle to record cold-start behaviour.
8. Repeat with the configured LLM unavailable only in a safe staging/local test, not by changing production credentials during a submission window. Verify deterministic fallback and correct labels.

Record date/time, frontend URL, backend URL, deployed Git commit, status code, latency, generation mode, verification status, and screenshots. Do not record secrets or send provider keys in issue reports.

## Cricket correctness audit

Test intervals at innings start, exactly at an over boundary, partial last overs, wides/no-balls, retired hurt/retired out, and run-outs. Cricket overs use base-six legal balls: `16.5` means 16 overs and 5 legal balls, never decimal 16.5 overs. A run-out must not automatically credit a wicket to the bowler.

## Troubleshooting

- **Browser CORS error:** correct `ALLOWED_ORIGINS` in Render, redeploy, repeat preflight and browser test.
- **No matches / missing fixtures:** check `/readyz`, Render logs, Docker copy rules, and fixture provisioning; never invent fixtures to make the UI look populated.
- **LLM fails:** a deterministic summary is acceptable if the UI marks it as a fallback and scores remain engine-derived.
- **Retrieval fails:** keep retrieval optional; the engine remains the authority for match facts.
- **Cold start:** disclose the measured experience in the loading state. A monitor may reduce idle starts only within the host's rules and is not an availability guarantee.
- **CI passes but demo fails:** treat the public end-to-end test as failed. CI validates the tested commit, not the live deployment.

## Submission policy

Do not claim a public end-to-end test passed, a provider is live, retrieval is active, or specific test totals unless that statement is supported by the latest recorded run. Prefer a measured, honest limitation to an unverifiable claim.
