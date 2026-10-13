# backend/

FanCue Python backend — FastAPI modular monolith.

## Responsibility

This directory contains the entire Python backend. It is structured as a
modular monolith: all modules run in a single process initially, but are
organized so that individual modules could be extracted into independent
services later without changing their public interfaces.

## Module Boundaries

| Directory | Responsibility |
|---|---|
| `app/api/` | FastAPI routers and HTTP endpoint definitions. Thin layer only — no business logic here. |
| `app/core/` | Application startup, configuration loading, logging setup, dependency injection. |
| `app/domain/` | Sport-agnostic domain types and interfaces. Pure Python, no framework imports. |
| `app/adapters/cricket/` | Cricket-specific event parsing, state reconstruction, and interval logic. |
| `app/adapters/football/` | Football-specific event parsing, state reconstruction, and interval logic. |
| `app/match_engine/` | Deterministic match state reconstruction and state-difference calculation. Authoritative source of match facts. |
| `app/context/` | Evidence packet assembly — combines match engine output with retrieval results. |
| `app/retrieval/` | Qdrant client interface, embedding provider, and sport/language-aware query logic. |
| `app/explanation/` | LLM orchestration — constructs prompts, calls LLM, returns structured output. |
| `app/verification/` | Claim verification against authoritative facts. Triggers deterministic fallback on failure. |
| `app/schemas/` | Shared Pydantic models for requests, events, evidence packets, and responses. |
| `tests/` | Backend unit tests. One test module per source module. |

## Component Interaction Rules

- `api/` calls `core/` and `app/` modules only. Never imports domain logic directly.
- `match_engine/` is the single source of truth for match state. No other module writes match facts.
- `explanation/` receives an evidence packet. It must never call the match engine directly.
- `verification/` has read access to the match engine output and the explanation output. It must never modify either.
- `retrieval/` must apply sport and language filters on every query to prevent cross-sport context bleed.

## Implementation Status

**Phase 00 — Structure defined. No application code implemented.**

Implementation begins in Phase 03 (cricket match engine). See `docs/plan/roadmap.md`.

## Local Development (future)

```bash
# Create virtual environment
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies (after pyproject.toml is created in Phase 03)
uv pip install -e ".[dev]"

# Run tests
pytest backend/tests/ -v

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
