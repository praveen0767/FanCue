# FanCue

### Evidence-grounded cricket match catch-up

FanCue reconstructs a selected historical cricket interval from recorded ball-by-ball data, computes the score-state delta deterministically, and produces an explanation with inspectable evidence. The language model is not the source of truth for match facts.

**Product principle: evidence defines what happened; AI may help explain it.**

## What the prototype does

1. Load a supported historical cricket fixture.
2. Select a match interval.
3. Reconstruct score, wickets, legal balls, extras, and interval changes from the source ledger.
4. Identify key events and their evidence identifiers.
5. Generate an explanation when a provider is configured, verify it, and use a deterministic fallback when generation cannot be accepted.
6. Present generation and verification status so the user can distinguish verified AI prose from a fallback.

## Honest scope

- Historical cricket replay is the primary implemented vertical slice and depends on the supported fixtures being present in the deployed image.
- Near-live discovery and scorecards depend on CricketData.org configuration, quotas, and availability.
- Aggregate near-live scorecards do not provide delivery-level history; FanCue does not claim to create a true live ball-by-ball recap from aggregates.
- Qdrant is optional context retrieval, not the authority for scores or events. Production can disable retrieval.
- Football support is not represented as complete.

## Architecture

```text
Browser
  -> FastAPI request validation
  -> fixture-backed deterministic match engine
  -> state delta + evidence packet
  -> optional contextual retrieval
  -> configured LLM draft
  -> claim verification
  -> verified explanation OR deterministic fallback
  -> response with provenance/status
```

The engine owns numeric facts. Retrieval may add contextual knowledge but must not override the recorded match ledger. Model output is only suitable for display when it passes the verifier; fallback output must be labelled accurately.

## Deployment

- Frontend: configure Vercel project root as `frontend`, with `VITE_API_BASE_URL` set to the Render API URL (no trailing slash).
- Backend: deploy `render.yaml` from the repository root. Set `FANCUE_ENV=production` and `ALLOWED_ORIGINS` to the exact Vercel production origin.
- Provider credentials belong in Render environment variables/secret settings only, never in `VITE_*` variables or committed files.
- Confirm that fixture files are included in the Docker image. The existence of a local or ignored fixture folder does not prove deployment provisioning.
- Render free services may cold-start after inactivity. Measure the first and subsequent request latency.

## Pre-submission gate

Follow [docs/PUBLIC_DEMO_ACCEPTANCE.md](docs/PUBLIC_DEMO_ACCEPTANCE.md) before sharing a reviewer link. It covers liveness versus readiness, CORS, route inspection, public browser flow, response JSON, latency, fallback tests, cricket edge cases and honest scope.

## Quality and evaluation

Automated tests and CI validate the covered code paths on a particular revision. They do not prove production reliability by themselves. Publish only test counts from the exact current CI run, and interpret curated retrieval metrics only for the documented evaluation set. Future evaluation should measure state reconciliation, supported-claim precision, unsupported-claim detection, latency, fallback coverage and provider failure behaviour on named fixtures.

## Data licensing

Check [data/ATTRIBUTION.md](data/ATTRIBUTION.md) and [Cricsheet's current licensing guidance](https://cricsheet.org/licensing/) for the exact fixture format used. Keep the source, revision, license, hash and attribution with each fixture. Do not assume one license applies to all formats.

## Development

- Backend tests and integration checks are run by the repository's GitHub Actions workflow.
- Frontend check/build uses `npm ci` and `npm run build` within `frontend/`.
- For manual verification, see [docs/PUBLIC_DEMO_ACCEPTANCE.md](docs/PUBLIC_DEMO_ACCEPTANCE.md).

## Submission note

This repository documents implementation and test evidence, not a guarantee that a given hosted URL is currently healthy. Record the deployed commit and a successful end-to-end run before describing the public app as validated.
