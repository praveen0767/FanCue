# FanCue Backend Runbook

The API exposes:
- `GET /healthz`: process liveness only.
- `GET /readyz`: fixture presence and configured retrieval/LLM operating mode.
- `GET /matches`: supported matches that can be loaded from the deployed fixture directory.
- `POST /catchup`: a historical interval response with authoritative state, evidence and an explanation status.

## Deployment requirements

- Build context must be the repository root because `backend/Dockerfile` copies `backend/`, `ingestion/`, `contracts/`, and `data/`.
- Required historical JSON fixtures must exist at `data/raw/<match_id>.json` inside the image. The repository intentionally excludes raw data; verify packaging/provisioning explicitly.
- Set `FANCUE_ENV=production` and an explicit `ALLOWED_ORIGINS` value containing the exact production Vercel origin.
- Set the LLM provider and provider key together in the Render environment. Current `render.yaml` selects Groq; adding only an OpenAI key does not override that explicit provider selection.
- `FANCUE_RETRIEVAL_ENABLED=false` is a supported production mode. It avoids Qdrant/embedding initialization on the critical catch-up path.
- `/healthz` is configured for platform liveness checks. It must remain cheap. Use `/readyz` as an operator diagnostic, not as proof that all user journeys work.

## Validate locally

Install project dependencies and run the repo's CI commands:

```bash
pip install -e ".[dev]"
pytest --cov=backend/app --cov=ingestion --cov-report=term-missing tests backend/tests
cd frontend && npm ci && npm run build
```

For an internet-connected environment, the public HTTP/CORS smoke check is:

```bash
bash scripts/public-smoke-test.sh
```

That script checks process health, readiness, match-list availability, and CORS preflight. It deliberately does not fabricate a POST body or claim to prove end-to-end catch-up. Use the [public demo acceptance runbook](../docs/PUBLIC_DEMO_ACCEPTANCE.md) to complete the browser validation.
