# ADR-006 — Cricket-First Implementation with a Separate Football Adapter

> **Current deployment note (2026-10-15):** The shared orchestration architecture can include contextual retrieval, but Qdrant is optional and disabled in the current Render blueprint. This decision record does not imply retrieval is active in production.

**Status:** Accepted
**Date:** 2026-10-11
**Phase:** 00

---

## Context

FanCue targets both cricket and football fans. Building both sports
simultaneously risks delivering neither well. Cricket and football have
fundamentally different event models, scoring structures, and contextual
knowledge requirements, which makes a shared implementation approach
technically incorrect.

---

## Decision

Cricket is the **first complete implementation**. All phases from 03 to 07
establish and verify the full cricket workflow end-to-end. Football is
implemented as a separate adapter in Phase 08, reusing the shared orchestration
framework but not sharing any sport-specific logic.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| Build both sports simultaneously | Risk of neither being production-quality by the assignment deadline. |
| Football first | Football data (StatsBomb) requires more preprocessing. Cricket (Cricsheet) is better documented for ball-by-ball reconstruction, making it a faster first proof. |
| Abstract shared sport interface from day one | Correct long-term, but premature abstraction before either sport is implemented leads to over-engineering. The shared interface will emerge naturally after cricket is working. |
| Only cricket (no football plan) | Assignment requires multi-sport architecture. Football must be planned even if deferred. |

---

## Consequences

- No football code may be merged before the cricket workflow passes its
  Phase 07 acceptance gate.
- The `adapters/football/` directory exists but contains only a README in
  Phase 00 through Phase 07.
- The shared orchestration framework (context planner, retrieval, explanation,
  verification) must not contain cricket-specific assumptions.
- When the football adapter is introduced (Phase 08), it must demonstrate
  that adding it did not require modifying any cricket adapter code.
- Football tests must pass independently of cricket tests.

---

## Conditions for Revisiting

- If a strategic need to demonstrate football capability is required before
  Phase 08, a minimal proof-of-concept (not production) may be created under
  a `spike/` branch with no merge to `main` until the cricket gate passes.
