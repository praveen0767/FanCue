# FanCue

> **"Catch the moment. Understand the game."**

FanCue is an AI-powered, evidence-grounded, cross-sport match-context platform.
It helps fans understand what happened during a match interval they missed —
with explanations grounded in inspectable, deterministic evidence rather than
opaque AI guesswork.

---

## The Fan Problem

You return to a match after an interruption. The scoreboard shows the current
state. It does not tell you:

- What happened during the time you were away?
- Which events were decisive?
- How did the match momentum shift?
- Why do those events matter in this format and context?

FanCue answers those questions.

---

## Intended User Journey

1. Fan opens FanCue and selects a match.
2. Fan specifies an interval ("I missed overs 12–18" or "I missed 55'–72'").
3. FanCue reconstructs the interval deterministically from authoritative data.
4. FanCue retrieves contextual knowledge relevant to the events.
5. FanCue assembles an evidence packet and generates a structured explanation.
6. Explanation is verified against authoritative match facts.
7. Fan receives a concise, evidence-linked summary in their preferred language
   and detail level.
8. If AI generation fails, the fan receives a deterministic structured summary
   (never a blank screen or error page).

---

## AI and Data-Truth Boundaries

FanCue is AI-powered but not AI-authoritative:

- **Deterministic sport engines** establish match facts. The engine is the
  single source of truth for scores, events, and state.
- **Qdrant** retrieves relevant contextual knowledge (rules, historical
  context, player profiles). It is not an authoritative score store.
- **The language model** produces readable explanations bounded by verified
  facts. It cannot change authoritative match state.
- **Verification** checks every LLM output against authoritative facts before
  it reaches the fan.
- **Deterministic fallback** ensures the product works without an LLM API key.

---

## Sport Strategy

| Sport | Status |
|---|---|
| Cricket | First complete implementation |
| Football | Second adapter — later vertical slice |

Cricket and football have separate adapters. They do not share scoring
formulas or event boundaries. A working cricket flow is the Phase 03 target.
Football follows in Phase 08.

---

## Planned Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript |
| Backend | Python 3.12+, FastAPI, Pydantic |
| Knowledge retrieval | Qdrant (semantic vector search) |
| Persistence | PostgreSQL (planned, Phase 07) |
| Async / cache | Redis, task queues (conditional, Phase 07) |
| Containerisation | Docker, Docker Compose |
| Testing | pytest (backend), Jest / Playwright (frontend) |

---

## Local Setup Status

**Current status: Phase 04 — Qdrant Knowledge Ingestion & Retrieval Pipeline Completed.**

Phases 00–04 are complete:
- **Phase 00:** Workspace Initialization & Governance Foundation
- **Phase 01:** Product Logic & Interval Semantics
- **Phase 02:** Canonical Contracts, Domain Schemas & Data Provenance
- **Phase 03:** Deterministic Cricket Engine & Scorecard Reconciliation (100% coverage)
- **Phase 04:** Qdrant Knowledge Ingestion, Curated Corpus, Local Embedding & Retrieval Evaluation (100% HitRate@3)

To set up local development infrastructure (after Phase 01 completes and
requirements are confirmed):

```bash
# Copy environment template
cp .env.example .env
# Edit .env with your local values

# Start local infrastructure
docker compose up -d

# Verify services
docker compose ps
```

> **Do not run these commands yet.** Application code does not exist.
> Local setup instructions will be updated progressively with each phase.

---

## Repository Structure

```
FanCue/
├── AGENTS.md              # Engineering constitution (read first)
├── README.md              # This file
├── .gitignore
├── .dockerignore
├── .env.example           # Environment template (no secrets)
├── docker-compose.yml     # Local infrastructure (Qdrant + PostgreSQL)
├── frontend/              # Next.js application (Phase 06)
├── backend/               # FastAPI modular monolith (Phase 03+)
│   └── app/
│       ├── api/           # HTTP endpoints
│       ├── core/          # Config, logging, startup
│       ├── domain/        # Sport-agnostic domain types
│       ├── adapters/
│       │   ├── cricket/   # Cricket-specific engine
│       │   └── football/  # Football-specific engine (Phase 08)
│       ├── match_engine/  # Deterministic state reconstruction
│       ├── context/       # Evidence packet assembly
│       ├── retrieval/     # Qdrant interface
│       ├── explanation/   # LLM orchestration
│       ├── verification/  # Claim verification + fallback
│       └── schemas/       # Shared Pydantic schemas
├── tests/
│   ├── contracts/         # Schema contract tests
│   ├── evaluation/        # Retrieval evaluation sets
│   └── integration/       # End-to-end tests
├── ingestion/             # Knowledge ingestion pipelines
├── data/                  # Licensed datasets (see data/README.md)
├── contracts/             # Canonical schema definitions
├── docs/
│   ├── product/           # Vision, personas, user journeys
│   ├── architecture/      # System context, component diagrams
│   ├── decisions/         # Architecture Decision Records
│   ├── plan/              # Roadmap and phase plans
│   └── evaluation/        # Retrieval and explanation quality metrics
└── infra/                 # Infrastructure configuration
```

---

## Architecture and Phase Documentation

- [Architecture: System Context](docs/architecture/system-context.md)
- [Architecture Decisions](docs/decisions/) (ADR-001 through ADR-008)
- [Data Contracts Architecture](docs/architecture/data-contracts.md)
- [Schema Versioning Policy](docs/architecture/schema-versioning.md)
- [API Contracts Preview](docs/architecture/api-contracts.md)
- [Product Vision](docs/product/vision.md)
- [Interval Model Specification](docs/product/interval-model.md)
- [Product Acceptance Criteria](docs/product/acceptance-criteria.md)
- [User Scenarios](docs/product/user-scenarios.md)
- [MVP Scope & Priority](docs/product/mvp-scope.md)
- [Fan Validation Plan](docs/product/fan-validation-plan.md)
- [Phase Roadmap](docs/plan/roadmap.md)

---

## Current Status

| Item | State |
|---|---|
| Repository initialized | ✅ Phase 00 |
| Engineering constitution | ✅ AGENTS.md |
| Architecture decisions | ✅ ADR-001 through ADR-008 |
| Product specification & interval model | ✅ Phase 01 complete |
| Acceptance criteria & scenarios | ✅ Phase 01 complete |
| Data contracts & provenance | ✅ Phase 02 complete (39 tests passing) |
| Deterministic cricket match engine | ✅ Phase 03 complete (100% coverage, 77 tests passing) |
| Docker Compose (local infra) | ✅ Defined, not started |
| Qdrant knowledge ingestion | ⏳ Next — Phase 04 |
| AI orchestration & verification | ❌ Not yet — Phase 05 |
| Frontend application code | ❌ Not yet — Phase 06 |
| Football adapter | ❌ Not yet — Phase 08 |

---

*Phase 03 completed: 2026-10-11*  
*Next: Phase 04 — Qdrant Knowledge Ingestion & Retrieval Pipeline*
# FanCue
