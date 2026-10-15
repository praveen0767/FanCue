# FanCue Evaluation Results

## Live API evaluation

**Status: NOT RUN against the live API by this change.** No live latency, fallback-rate, or live verifier-rejection-proxy metrics are recorded yet. The live Render endpoints were not accessible from the authoring environment, so the real 20-request evaluation must be run by the operator.

Run the following from the repository root in an environment with the project dependencies installed and network access to Render:

```bash
python scripts/evaluate_catchup.py --base-url https://fancue-api-o4r1.onrender.com --requests 20 --timeout 90 --output docs/eval_results.md
```

The script overwrites this file with the execution timestamp, exact process argv, per-request observations, nearest-rank p50/p95 latency for HTTP responses, fallback rate among successful catch-ups, and a documented verifier-rejection fallback proxy. It also runs a local adversarial set against the real verifier and the tracked Cricsheet fixture.

The public API exposes the final fallback reason, not a raw count of every verifier draft rejected. Therefore, the live verifier-rejection metric is a proxy: responses where the final fallback reason is `fact_mismatch` or `unsupported_claims`, divided by successful catch-ups. This is not a direct per-draft rejection rate.

## Local adversarial verifier checks

**Recorded CI run date (UTC):** 2026-10-15  
**Exact test command:** `pytest --cov=backend/app --cov=ingestion --cov-report=term-missing tests backend/tests`  
**Workflow run:** [PR #19 evaluation-harness CI](https://github.com/praveen0767/FanCue/actions/runs/38697069816)

Observed warning emitted by the real fixture-backed verifier test:

```text
Observed local adversarial verifier result: 3/3 rejected; rate=100.00%; wrong_score=rejected[score_runs_mismatch]; wrong_player=rejected[player_name_mismatch]; invented_wicket=rejected[score_wickets_mismatch]
```

This result is limited to the three named adversarial drafts in the test. It is not a broad red-team benchmark and does not claim that all possible hallucinations will be rejected.

The CI run reported the entire suite separately; see the workflow log for the exact run summary. Current Render configuration disables Qdrant retrieval, so this evaluation does not measure production retrieval.
