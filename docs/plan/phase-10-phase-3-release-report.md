# Archived Deployment Report — Superseded

**Original report date:** 2026-10-13  
**Archived note updated:** 2026-10-14

This file is retained only as a historical artifact. It is **not** the current deployment guide or source of truth. The original report contains stale assumptions about repository state, OpenAI as the active provider, fixture tracking, and test counts. Do not use those statements for the Dream11 submission.

## Current source-controlled configuration

- `render.yaml` selects `LLM_PROVIDER=groq` and `GROQ_MODEL=openai/gpt-oss-20b`.
- `render.yaml` sets `FANCUE_RETRIEVAL_ENABLED=false`; Qdrant retrieval is off in the checked-in Render configuration.
- The two registered Cricsheet fixtures are tracked and the Dockerfile copies `data/` into the image.
- `docs/SUBMISSION_NOTE.md` is the short, current product submission note.
- `docs/PUBLIC_DEMO_ACCEPTANCE.md` is the current manual release gate.

## Validation boundary

The repository test suite and CI validate a particular commit. They do not establish that the currently deployed Render secrets match source configuration, that the live model provider responds, or that the browser can complete a cold-start catch-up on first click. Record those results only after testing the deployed application.

For current code, test counts, and architecture, use the root `README.md`, the latest GitHub Actions run, and the acceptance runbook—not the historical checklists or metrics originally recorded in this report.
