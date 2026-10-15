# FanCue Evaluation Results

These are measured results from named runs. The adversarial subset is an intentionally small diagnostic, not a statistical estimate of general verifier accuracy.

## Offline adversarial verifier evaluation — 2026-10-15

- Exact command executed by GitHub Actions: python scripts/evaluate_verifier_adversarial.py --report /tmp/fancue-adversarial-eval.md
- Workflow: https://github.com/praveen0767/FanCue/actions/runs/38697311068
- Tested commit: 95a95d4e5f3fabb675234f0fbb2df0d1ed912e52
- Method: three hand-authored fake LLM drafts run through the real fixture-backed evidence builder, claim verifier, and catch-up orchestrator. No live LLM or public network request was used.
- Draft rejection: 3/3 (100.0%) on this specific adversarial set.
- Fabricated summary leaks: 0.

| Adversarial case | Resulting mode | Fallback reason | Draft rejected | Fabricated summary leaked |
|---|---|---|---|---|
| Wrong score | deterministic_fallback | fact_mismatch | yes | no |
| Wrong player | deterministic_fallback | fact_mismatch | yes | no |
| Invented wicket / unknown evidence ID | deterministic_fallback | unsupported_claims | yes | no |

The orchestrator now fails closed when the verifier rejects any claim, even if another score claim passes. This prevents unverified draft summary text from bypassing claim-level filtering. The result only covers these three constructed cases and does not imply a general 100% rejection rate.

## Live catch-up evaluation — not yet run

The repository authoring environment could not resolve the public Render hostname (DNS/network unavailable). **No live latency, fallback-rate, or verifier-rejection numbers are claimed here.**

Run this from a machine with internet access to send 20 catch-up requests to both supported fixtures. The script will append the measured result to this file:

    python scripts/evaluate_catchups.py --api-base-url https://fancue-api-o4r1.onrender.com --requests 20 --output docs/eval_results.md

The live evaluation reports p50/p95 client-observed POST latency, request failures, deterministic fallback rate, and verifier rejection rate among responses that show a draft reached verification. It uses a one-second delay by default and caps a run at 50 requests to leave margin below the API's in-process per-minute limit.

For first-click, CORS, and both-fixture validation, run:

    python scripts/smoke_test.py --api-base-url https://fancue-api-o4r1.onrender.com --frontend-origin https://fan-cue.vercel.app

That smoke script prints HTTP status, generation_mode, verification_status, fallback_reason, and the observed duration for each catch-up. It is not represented as passed until you run it against the live deployment.
