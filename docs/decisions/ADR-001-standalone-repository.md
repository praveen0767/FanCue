# ADR-001 — Independent FanCue Repository and Product Boundary

**Status:** Accepted
**Date:** 2026-10-11
**Phase:** 00

---

## Context

FanCue is being initialized as a new AI-powered sports product. The engineer
responsible also maintains or has access to ARIV, an existing project whose
engineering principles (deterministic authority, bounded AI, idempotency,
validation, auditability, failure recovery) are conceptually relevant.

The question is whether FanCue should live inside the ARIV repository, share
its Git history, or otherwise be co-located with any existing project.

---

## Decision

FanCue is a completely standalone repository at `D:\FanCue`. It has its own
Git history, its own dependency graph, its own deployment lifecycle, and its
own product boundary. No ARIV source file may ever enter this repository.
ARIV is a conceptual reference only.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| FanCue as a subdirectory of ARIV | Conflates two separate products. Dependency and deployment coupling. |
| FanCue as a Git submodule of ARIV | Shared history complexity; no clean fan-facing product identity. |
| Shared monorepo (ARIV + FanCue) | Premature; introduces tooling overhead before FanCue has a stable shape. |
| Importing ARIV modules into FanCue | Licensing, versioning, and conceptual coupling risks. |

---

## Consequences

- Every file write must be confirmed to reside under `D:\FanCue`.
- No agent or process may access ARIV paths.
- FanCue can evolve its stack, dependencies, and architecture independently.
- A future decision to open-source or transfer FanCue is unencumbered by ARIV.

---

## Conditions for Revisiting

- If FanCue and ARIV genuinely need to share a runtime component, evaluate
  extracting that component into an independently versioned library.
- If a monorepo toolchain (e.g., Turborepo, Nx) provides measurable benefit,
  evaluate it as a separate ADR with explicit justification.
