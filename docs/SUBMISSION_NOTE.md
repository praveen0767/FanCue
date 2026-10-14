# FanCue Submission Note

FanCue is an evidence-grounded cricket match catch-up prototype built with FastAPI and React/Vite.

## Problem

A fan returning to a match after a break can see that the score changed without knowing which events drove that change. FanCue lets a user choose a historical match interval and builds a recap from the recorded delivery ledger.

## Engineering approach

- **Deterministic match facts:** the match engine owns score-state reconstruction, wickets, extras, over boundaries, and interval deltas.
- **Evidence packet:** the response carries structured key facts and source provenance so a recap can be inspected.
- **Constrained language generation:** the configured LLM explains supplied facts; it is not the authority for match scores.
- **Verification and graceful degradation:** the orchestrator verifies generated claims and uses a deterministic summary when generation fails or the draft cannot be accepted.
- **Optional retrieval:** Qdrant is contextual support only. It may be disabled in the constrained deployment and must never become the source of truth for scores or events.

## Current scope

- Historical cricket replay using supported, provisioned match fixtures.
- Near-live discovery and aggregate scorecards where the CricketData.org integration is configured and within the provider's limits.
- Near-live aggregate scorecards are **not** delivery-level live catch-up. No such capability is claimed.

## Validation status

Source code, tests and a successful CI workflow are useful engineering evidence, but they do not independently prove the public Vercel-to-Render user journey. Before submission, run the [Public Demo Acceptance Runbook](PUBLIC_DEMO_ACCEPTANCE.md), record the deployed commit and latency, and verify a real catch-up response.

Do not state that live generation, retrieval, public acceptance, or a particular test count is verified unless it was confirmed on the exact revision being submitted. The deployed environment depends on provider environment variables and fixture provisioning which are not visible from this repository.

## Licensing

Data use and attribution must be checked against the exact downloaded Cricsheet data format and its current terms. See [data/ATTRIBUTION.md](../data/ATTRIBUTION.md) and the [Cricsheet licensing page](https://cricsheet.org/licensing/). Do not imply one license applies to every format without verification.

## Recommended reviewer path

1. Open the deployed frontend.
2. Select a supported historical fixture and a valid interval.
3. Inspect the score delta and a cited event in the evidence panel.
4. Inspect `explanation.generation_mode` and `explanation.verification_status` in the network response.
5. Confirm a deterministic fallback is clearly labelled when the AI path is unavailable.

**Product principle:** evidence defines what happened; AI may help explain it.
