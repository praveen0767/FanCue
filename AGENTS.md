# AGENTS.md — FanCue Engineering Constitution

> **Binding for all phases. Every agent, contributor, and automated process must
> read and honour this document before touching any file in this repository.**

---

## 1. Repository Identity and Isolation

| Property | Value |
|---|---|
| Product name | FanCue |
| Repository root | `D:\FanCue` |
| Tagline | "Catch the moment. Understand the game." |
| Category | AI-powered, evidence-grounded, cross-sport match-context platform |

### Absolute isolation rules

- FanCue is a **standalone project**. It must never be nested inside, merged
  with, or linked as a subtree of any other repository (including ARIV).
- **Never** read, clone, modify, import, copy, move, or delete files from ARIV
  or any other external project.
- ARIV is a conceptual reference only — its engineering principles
  (deterministic authority, bounded AI, idempotency, validation, auditability,
  failure recovery) may inform design decisions here, but no ARIV source file
  may ever enter this repository.
- All file writes must remain inside `D:\FanCue`. Any agent or process that
  attempts to write outside this root must stop immediately and report the
  violation.
- Do **not** create a GitHub remote, publish code, or push commits without
  explicit written authorization from the project owner.
- Never delete directories, reset Git history, force-update branches, or
  execute destructive cleanup commands (`git reset --hard`, `git clean -fd`,
  `rm -rf`, etc.).
- If any isolation condition cannot be confirmed, **stop and report** instead
  of proceeding.

---

## 2. Product Scope

### Core problem

A fan returns to a match after an interruption. The current scoreboard shows
the present state but does not explain what happened during the interval. The
fan needs:

1. A chronological reconstruction of the interval events.
2. Identification of important moments.
3. An explanation of how and why the match state changed.
4. Output in a preferred language and level of detail.

### Core product promise

FanCue reconstructs a selected historical match interval, calculates the state
difference deterministically, retrieves relevant contextual knowledge, and
produces a concise explanation grounded in inspectable evidence.

### Explicit non-goals (permanent)

Do **not** build or claim:

- A complete production API or application feature set in Phase 00.
- Fabricated cricket or football datasets that impersonate real matches.
- A chatbot disconnected from the match engine.
- Autonomous agent swarms without explicit typed contracts.
- Licensed live-feed integrations.
- Exact OTT or broadcast frame synchronisation.
- Real-money betting, prediction, or gambling features.
- Claims of supporting 50 million concurrent users without verified load tests.
- Dream11 integrations or assumptions about its internal systems.

---

## 3. Sport Domain Boundaries

### Shared workflow, separate adapters

The product uses one shared orchestration workflow. Sport-specific behaviour
lives entirely inside isolated adapters. The two adapters must never share a
scoring formula or assume that event boundaries are interchangeable.

### Cricket adapter — authoritative concepts

| Concept | Notes |
|---|---|
| Match formats | Test, ODI, T20 |
| Structural units | Innings → Overs → Deliveries |
| Legal-ball count | Excludes wides and no-balls |
| Scoring events | Runs (bat, extras), wickets, partnerships |
| Extras | Wides, no-balls, byes, leg-byes, penalties |
| State keys | Runs, wickets, overs, partnerships, required rate |

### Football adapter — authoritative concepts

| Concept | Notes |
|---|---|
| Periods | First half, second half, extra time, penalties |
| Clock | Additive (90+5 notation), not countdown |
| Scoring events | Goals, own-goals |
| Disciplinary | Yellow cards, red cards, second yellows |
| Roster events | Substitutions (with player IDs) |
| State keys | Score, possession, disciplinary record |

### Implementation priority

Cricket is the **first complete implementation**. Football is a second adapter
and a later vertical slice. Football is not a reason to delay a verified cricket
workflow.

---

## 4. Authoritative Data Requirements

- Match facts (scores, events, wickets, goals) must come from explicitly
  licensed, recorded sources with documented provenance.
- Every dataset record must carry: `source_name`, `source_url`, `license`,
  `retrieved_date`, `revision_id`.
- Do **not** invent match data, invent player statistics, or use unverified
  third-party summaries as authoritative input.
- Candidate sources are listed in `data/README.md`. They must be reviewed for
  licensing terms before any data is downloaded.
- The deterministic sport engine is the **sole truth authority** for match
  state. No language model output may mutate authoritative score state.

---

## 5. Coding and Architecture Conventions

### General

- Use **explicit types** everywhere (Pydantic models on the backend,
  TypeScript interfaces on the frontend).
- Contracts (request schemas, event schemas, evidence-packet schemas, response
  schemas) must be defined **before** AI or UI implementation begins.
- Every public function must have a docstring stating its purpose, inputs,
  outputs, and failure behaviour.
- Raise domain-specific, named exceptions. Never swallow exceptions silently.
- No `print()` as a logging mechanism in production paths; use structured
  logging with severity levels.

### Backend (Python / FastAPI)

- Python version: `3.12+` (pinned in `pyproject.toml` or `.python-version`).
- Dependency management: `uv` or `pip-tools` with pinned lockfiles.
- All API request and response bodies: Pydantic `BaseModel` with explicit
  field types and validators.
- No raw SQL strings; use a query builder or ORM with parameterized queries.
- Domain logic must be testable without a running HTTP server.

### Frontend (Next.js / TypeScript)

- Node version: pinned in `.nvmrc` or `package.json` `engines` field.
- All data contracts: TypeScript interfaces generated from or aligned with
  backend Pydantic schemas.
- No `any` types without a documented justification comment.
- Responsive, mobile-first layout using the defined design system.

### Dependency version policy

- Pin **exact versions** in all lockfiles and Dockerfiles. No floating
  `latest` tags.
- Record the reason for each major dependency choice in the relevant ADR.
- Review official changelogs before upgrading across major versions.

---

## 6. Qdrant Retrieval and Provenance Rules

- Qdrant is the **semantic knowledge-retrieval component**. It is not an
  authoritative store for dynamic match scores or event chronology.
- Every document ingested into Qdrant must carry these metadata fields:

  ```
  doc_id          # deterministic, content-addressed identifier
  source_name     # human-readable source name
  source_url      # canonical URL or file path
  license         # SPDX identifier or free-text license name
  language        # ISO 639-1 code
  sport           # "cricket" | "football"
  topic           # e.g., "batting_technique", "offside_rule"
  chunk_index     # position within the source document
  ingestion_date  # ISO 8601
  permitted_use   # "non_commercial" | "commercial" | "evaluation_only"
  ```

- `doc_id` must be deterministic and reproducible from content. Do not use
  random UUIDs.
- Retrieval queries must pass sport and language filters to prevent cross-sport
  context bleed.
- Retrieval results must be included in the evidence packet with their
  `doc_id`, `source_name`, and `source_url` so that explanation outputs can
  be traced to their sources.
- Retrieval evaluation with known-relevant test questions must be maintained in
  `tests/evaluation/`.

---

## 7. Bounded AI and Fallback Requirements

### AI strategy

- The system is retrieval-augmented and AI-powered, but **deterministic domain
  logic remains authoritative**.
- The controlled orchestration flow is:

  ```
  Validate request
    -> Reconstruct match state (deterministic engine)
    -> Calculate state difference (deterministic)
    -> Retrieve contextual knowledge (Qdrant)
    -> Select and assemble evidence packet
    -> Generate structured explanation (LLM)
    -> Verify claims against authoritative facts and retrieved sources
    -> Return verified output OR deterministic fallback
  ```

- A language model must **never** mutate authoritative score state.
- No step may be skipped or short-circuited without a documented, tested
  justification.

### Deterministic fallback

- If the LLM API is unavailable, times out, or produces an output that fails
  verification, the system must return a deterministic fallback:
  a structured summary built from the match-engine output and evidence packet,
  without LLM-generated prose.
- The fallback response must be clearly labelled as non-AI-generated.
- The system must be usefully functional without an LLM API key.

### Verification

- After LLM generation, a verification step must check that:
  - All score claims match the deterministic engine's authoritative output.
  - All cited sources exist in the evidence packet with matching `doc_id`.
  - No fabricated statistics appear (hallucination detection).
- Failed verification triggers the deterministic fallback, not a retry loop.

---

## 8. Security and Secret Management

- **Never** commit secrets, API keys, tokens, passwords, or database
  credentials to this repository.
- `.env` is listed in `.gitignore` and must never be committed.
- `.env.example` contains only safe placeholder values and is the only
  environment-template file committed to Git.
- All secrets are loaded at runtime from environment variables.
- Use `python-dotenv` (backend) and Next.js `env` conventions (frontend) to
  load environment configuration.
- Database URLs and Qdrant credentials must include only the minimum required
  privileges.
- Ports exposed by `docker-compose.yml` must bind to `127.0.0.1` only in
  development.

---

## 9. Test Requirements and Evidence Standards

- Every domain module must have unit tests before it is considered
  implemented.
- Tests must be runnable without external network access (mock external
  dependencies).
- A test that asserts behaviour must fail if the behaviour is broken. Tests
  that always pass are not tests.
- Required test categories:

  | Category | Location | Notes |
  |---|---|---|
  | Domain unit tests | `backend/tests/` | Match engine, adapters, state calculation |
  | Contract tests | `tests/contracts/` | Schema validation for cricket and football |
  | Retrieval evaluation | `tests/evaluation/` | Known-relevant question sets |
  | Integration tests | `tests/integration/` | End-to-end flow with real components |

- Test coverage must be measured and reported. A coverage gate (minimum %)
  must be defined before Phase 03 begins.
- No phase may be marked complete without executed, passing test evidence.

---

## 10. Phase-Gate Behaviour

Each implementation phase has an explicit exit gate. A phase must not be
marked complete, and the next phase must not begin, until:

1. All required files for the phase exist and are internally consistent.
2. All tests for the phase pass with evidence (command output, coverage
   report).
3. A list of changed files is recorded.
4. Observed results match stated acceptance criteria.
5. Unresolved risks are documented.
6. The next phase's acceptance gate is stated.

**Required deliverable for every phase completion report:**

```
## Phase [N] Completion Report

### Changed files
- [list every changed or created file]

### Tests executed
- [command] -> [result]

### Observed results
- [what actually happened, not what was planned]

### Unresolved risks
- [honest list]

### Next acceptance gate
- [Phase N+1 entry conditions]
```

---

## 11. Prohibitions Against Unsupported Claims

- Do not claim a feature is implemented because it appears in the roadmap.
- Do not claim a test passes without running it and capturing its output.
- Do not claim a service is healthy without a confirmed health check.
- Do not claim a dataset is licensed without reviewing its actual license.
- Do not claim the system handles a load without a measured load test.
- Do not claim AI output is verified without a verification step that can fail.

---

## 12. Conditional Infrastructure Adoption

Before adding Redis, background workers, a transactional outbox, or MCP
to the stack, document:

1. The actual workload or failure mode that requires it.
2. Why simpler synchronous processing is insufficient.
3. The required delivery and idempotency guarantees.
4. How those guarantees will be tested.
5. The measured cost (latency, complexity, operational burden).

MCP is not required on the fan-facing request path. It may be added later for
explicitly authorized, typed operational tools if a genuine use case is
documented.

---

*Last updated: Phase 00 initialization -- 2026-10-11*
*This document supersedes any conflicting instruction in a phase prompt.*
