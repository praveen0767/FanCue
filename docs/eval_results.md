# FanCue Evaluation Results

**Status: NOT RUN against the live API.** No latency, fallback, or live verifier-rejection metrics are recorded in this file yet.

Run the following from the repository root in an environment with the project dependencies installed and network access to the deployed Render API:

```bash
python scripts/evaluate_catchup.py --base-url https://fancue-api-o4r1.onrender.com --requests 20 --timeout 90 --output docs/eval_results.md
```

The evaluator will overwrite this page with the actual execution timestamp, exact process command, per-request observations, nearest-rank p50/p95 latency for HTTP responses, fallback rate among successful catch-ups, and a documented verifier-rejection fallback proxy. It also runs a local adversarial set against the real verifier and the tracked Cricsheet fixture.

The public API exposes the final fallback reason, not a raw count of all verifier drafts rejected. Therefore, the live verifier-rejection metric is explicitly a proxy: responses where the final fallback reason is `fact_mismatch` or `unsupported_claims`, divided by successful catch-ups. The local adversarial rejection rate is measured separately on three deliberately incorrect drafts: wrong score, wrong player, and invented wicket.

Do not replace this status with estimates or copy metrics from older CI runs. The live evaluation must be run against the deployed revision and the generated result should be reviewed before submission.
