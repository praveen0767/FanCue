# FanCue — Phase Roadmap

> **Status clarification (2026-10-14):** This is the original engineering phase/checklist history, not a live deployment dashboard. Unchecked items are not to be silently marked complete because the repository CI passes. In particular, public Vercel-to-Render end-to-end acceptance is not confirmed until the manual journey in [PUBLIC_DEMO_ACCEPTANCE.md](../PUBLIC_DEMO_ACCEPTANCE.md) is completed. The checked-in Render config uses Groq (`openai/gpt-oss-20b`) and disables Qdrant retrieval.

All phases are sequential. A later phase must not begin before its predecessor
passes its exit gate. "Planned" means the work is defined but not started.
"Not started" is the honest status for all phases beyond 00 at initialization.

---

## Phase 00 — Initialization and Governance

**Status:** In progress
**Objective:** Establish a clean, auditable FanCue foundation with governance
rules, architecture decisions, directory structure, and local infrastructure
configuration.

### Exit gate

- [ ] `D:\FanCue` is the sole repository root; no ARIV files present.
- [ ] Git initialized on `main` branch; no remote configured.
- [ ] All required Phase 00 files exist and are internally consistent.
- [ ] `docker-compose.yml` validates with `docker compose config`.
- [ ] `.env` is confirmed absent from Git tracking.
- [ ] No secrets or dataset files were created.
- [ ] All ADRs (ADR-001 through ADR-007) are present and complete.
- [ ] Phase 00 completion report is produced.

---

## Phase 01 — Product and Acceptance Specification

**Status:** Completed (2026-10-11)
**Objective:** Translate the product vision into measurable, testable acceptance
criteria for the cricket workflow. Define the first end-to-end user scenario
that will serve as the integration test target for Phase 05.

### Planned deliverables

- `docs/product/acceptance-criteria.md` — 12 categories of acceptance criteria (AC, ENG, RET, AI, OPS, SCALE)
- `docs/product/user-scenarios.md` — 3 documented fan scenarios (Interrupted Viewer, Team-Focused Fan, Explanatory Lens)
- `docs/product/interval-model.md` — formal definition of an "interval" for cricket (whole-over boundaries)
- `docs/product/fan-validation-plan.md` — interview plan and offline golden-set scenario validation
- `docs/product/mvp-scope.md` — P0, P1, and P2 feature categorization and scope boundary
- `docs/decisions/ADR-008-v1-interval-semantics-and-language-scope.md` — boundary and language decisions

### Exit gate

- [x] At least 5 acceptance criteria defined for the cricket workflow, each
  with a measurable pass/fail condition (12 criteria defined).
- [x] At least 3 fan scenarios described in enough detail to drive integration
  tests (Scenarios A, B, and C documented).
- [x] Interval model formally defined with boundary conditions and 8+ edge cases documented.
- [x] Phase 01 completion report produced (`docs/plan/phase-01-completion-report.md`).

---

## Phase 02 — Contracts and Data-Source Governance

**Status:** Completed (2026-10-11)
**Objective:** Define all data contracts (request, event, evidence-packet,
response) and establish the data-source provenance registry before any
implementation begins.

### Planned deliverables

- `backend/app/schemas/` — Pydantic v2 contract models across common, cricket, football, evidence, retrieval, explanation, and error domains
- `contracts/*.schema.json` — 10 canonical JSON Schema exports generated from Pydantic models
- `data/sources.yml` — provenance registry with reviewed ODC-By v1.0 license and SHA-256 fixture hashes
- `data/ATTRIBUTION.md` — explicit attribution notice for Cricsheet data
- `docs/architecture/data-contracts.md` & `schema-versioning.md` — architectural contract documentation
- `docs/architecture/api-contracts.md` — OpenAPI preview specification
- `tests/contracts/` — 39 automated contract tests

### Exit gate

- [x] All contracts defined with explicit types, no `any` fields.
- [x] Cricket and football schemas are fully separate (no shared event types).
- [x] Evidence-packet schema includes mandatory provenance fields.
- [x] Contract tests pass: `pytest tests/contracts/ -v` (39/39 passed).
- [x] `data/sources.yml` created with reviewed and documented candidate source (Cricsheet ODC-By v1.0, pinned fixture 1529229.json).
- [x] Phase 02 completion report produced (`docs/plan/phase-02-completion-report.md`).

---

## Phase 03 — Deterministic Cricket Engine

**Status:** Completed (2026-10-11)
**Objective:** Implement a fully tested, deterministic cricket match state
engine that can reconstruct match state for any over range from
Cricsheet-formatted ball-by-ball event data.

### Planned deliverables

- `backend/app/adapters/cricket/` — cricket event parser, normalizer, identifiers, and errors
- `backend/app/match_engine/` — state reconstruction, intervals, delta calculator, and engine
- `backend/tests/` — unit, interval, reconciliation, and idempotency test suites
- `pyproject.toml` — pinned Python >=3.12, dependencies, and pytest configuration
- Measured statement coverage: 100.00% across adapter and match-engine modules

### Exit gate

- [x] Engine correctly reconstructs match state for at least 2 real
  Cricsheet JSON matches with documented provenance (ODI 1529229 and T20 1552779).
- [x] State-diff calculation is deterministic: same input, same output, always.
- [x] Edge cases covered: innings start sentinel (-1), over boundaries, wides, no-balls, byes, dismissals, non-wicket dismissals (retired hurt), high scoring overs, maidens.
- [x] All engine and contract tests pass: `pytest -v --cov` (77/77 passed).
- [x] Coverage >= 90% for engine modules (100.00% achieved).
- [x] No match facts are invented or assumed; scorecard reconciliation confirmed.
- [x] Phase 03 completion report produced (`docs/plan/phase-03-completion-report.md`).

---

## Phase 04 — Qdrant Knowledge Ingestion and Retrieval

**Status:** Completed (2026-10-11)
**Objective:** Ingest a verified, licensed knowledge corpus into Qdrant and
demonstrate that sport- and language-filtered retrieval returns relevant
results for cricket match events.

### Planned deliverables

- `ingestion/knowledge/` — ingestion pipeline scripts, loader, validator, semantic chunker, embeddings, store adapter, CLI
- `backend/app/schemas/knowledge.py` — canonical metadata schemas and generated JSON Schema
- `tests/evaluation/` & `tests/ingestion/` — known-relevant question sets and comprehensive evaluation runner
- `docs/architecture/knowledge-ingestion.md`, `docs/architecture/embedding-profile.md`, `docs/evaluation/retrieval-evaluation.md`

### Exit gate

- [x] At least one licensed knowledge corpus ingested with documented provenance (23 approved notes under CC-BY-4.0 citing MCC & ICC).
- [x] Every ingested document has all mandatory metadata fields populated (doc_id, source_name, source_url, license, language, sport, topic, chunk_index, ingestion_date, permitted_use, plus extended provenance).
- [x] Sport filter verified: cricket queries do not return football documents (0 cross-sport leakage).
- [x] Retrieval evaluation: >= 80% recall/hit rate on known-relevant question set (100.00% HitRate@3, MRR@5 = 0.9524).
- [x] Embedding provider interface is swappable (configuration-driven `EmbeddingProvider` interface with local FastEmbed ONNX implementation).
- [x] Phase 04 completion report produced (`docs/plan/phase-04-completion-report.md`).

---

## Phase 05 — Bounded AI Orchestration and Verification

**Status:** Not started
**Objective:** Implement the full orchestration pipeline: evidence packet
assembly, LLM explanation generation, claim verification, and deterministic
fallback.

### Planned deliverables

- `backend/app/context/` — evidence packet assembler
- `backend/app/explanation/` — LLM orchestration
- `backend/app/verification/` — claim verifier and fallback generator
- Integration tests for the full pipeline including LLM-unavailable scenarios

### Exit gate

- [ ] Full pipeline produces a verified explanation for at least 2 cricket
  interval queries end-to-end.
- [ ] Verification step correctly blocks a fabricated claim.
- [ ] Deterministic fallback activates and produces a useful output when the
  LLM is disabled (`SKIP_LLM_IN_TESTS=true`).
- [ ] No LLM output mutates the authoritative engine output.
- [ ] Phase 05 completion report produced.

---

## Phase 06 — Fan-Facing UI and API Integration

**Status:** Not started
**Objective:** Build the Next.js frontend and wire it to the FastAPI backend
to produce a working, fan-usable product for the cricket workflow.

### Planned deliverables

- `frontend/` — Next.js application with match selector and interval picker
- `backend/app/api/` — HTTP endpoints for the fan request flow
- Responsive, mobile-first UI with explanation display and fallback display
- End-to-end test: fan journey from interval selection to explanation display

### Exit gate

- [ ] Fan can specify a match and interval through the UI.
- [ ] Explanation displays correctly, including evidence sources.
- [ ] Fallback UI displays correctly when LLM is disabled.
- [ ] Mobile-first layout verified at 375px viewport.
- [ ] Phase 06 completion report produced.

---

## Phase 07 — Reliability and Justified Infrastructure

**Status:** Not started
**Objective:** Evaluate the working system under load, document any
infrastructure gaps, and introduce justified additional components (PostgreSQL
schema, Redis, workers) only with documented rationale per ADR-007.

### Planned deliverables

- PostgreSQL schema and migration files (if Phase 07 confirms the need)
- Load test results and documented thresholds
- Monitoring and observability plan
- Updated ADR-007 if any conditional infrastructure is adopted

### Exit gate

- [ ] Load test conducted and results documented.
- [ ] Any infrastructure addition justified against ADR-007 criteria.
- [ ] Fallback path verified under simulated LLM outage.
- [ ] Phase 07 completion report produced.

---

## Phase 08 — Football Adapter

**Status:** Not started (conditional on Phase 07 gate passing)
**Objective:** Implement the football match engine adapter and demonstrate
the full fan workflow for a football interval query, without modifying any
cricket adapter code.

### Exit gate

- [ ] Football adapter passes its own test suite independently.
- [ ] Cricket adapter test suite still passes with no changes.
- [ ] Full football pipeline produces a verified explanation end-to-end.
- [ ] Phase 08 completion report produced.

---

## Phase 09 — Evaluation, Deployment, and Submission

**Status:** Not started
**Objective:** Conduct user evaluation with real fans, document results, prepare
a clean deployment, and produce the assignment submission artifact.

### Exit gate

- [ ] At least 3 real fans complete the full cricket journey without assistance.
- [ ] Explanation accuracy: 0 verifiable factual errors in 10 manually reviewed
  test queries.
- [ ] Deployment documented and reproducible from a clean environment.
- [ ] Assignment submission artifact produced with evidence for all phase gates.
- [ ] All phase completion reports present and internally consistent.

---

*Roadmap version: Phase 00 initialization — 2026-10-11*
*No phase beyond 00 is in progress. Status must not be updated without
  an accompanying phase completion report.*
