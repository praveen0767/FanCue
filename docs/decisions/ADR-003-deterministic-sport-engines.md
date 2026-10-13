# ADR-003 — Deterministic Sport-Specific Engines as Match-Truth Authorities

**Status:** Accepted
**Date:** 2026-10-11
**Phase:** 00

---

## Context

FanCue's core feature is explaining what happened during a match interval.
To do this reliably, the system needs an authoritative, reproducible source of
match facts: scores, events, and state changes. These facts must be correct
before any AI-generated explanation is produced.

Two options exist: (a) treat the LLM as the source of match facts by asking it
to infer state from raw data, or (b) build a deterministic domain engine that
calculates match state from structured event data and treat its output as
authoritative.

---

## Decision

FanCue uses **deterministic, sport-specific engines** as the sole authority
for match state. Each sport (cricket, football) has a separate engine
implemented in typed Python with explicit state-machine logic. The engine
receives structured event data and produces authoritative state snapshots and
state differences. No language model may modify or override this output.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| LLM infers match state from raw commentary | Non-deterministic. Cannot be reliably tested. Hallucination risk on precise statistics. |
| Single shared engine for all sports | Cricket and football have fundamentally different event models, legal-ball rules, clock representations, and state keys. A shared formula would require so many conditionals that it would become untestable. |
| Pre-computed static match summaries | Cannot reconstruct arbitrary user-specified intervals. |
| Third-party score API as authority | External dependency; licensing and rate-limit risks; not reproducible in tests. |

---

## Consequences

- Cricket and football each require a dedicated, tested engine module.
- Every engine function must be deterministic: same input always produces same output.
- Engine output is passed to all downstream components as a read-only fact set.
- Tests for the engine must cover boundary conditions: innings transitions,
  final-over edge cases (cricket), extra-time periods (football).
- The engine must function without network access (pure computation on
  provided event data).

---

## Conditions for Revisiting

- If a licensed real-time data provider offers a contractually guaranteed
  authoritative feed with a tested SDK, that feed could replace the engine''s
  input source — but the deterministic calculation layer must remain.
- If a new sport is added, a new separate engine adapter is required. Existing
  engines must not be modified to accommodate it.
