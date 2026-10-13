# ADR-002 — Modular Monolith Before Microservices

**Status:** Accepted
**Date:** 2026-10-11
**Phase:** 00

---

## Context

FanCue requires a backend that handles match state reconstruction, knowledge
retrieval, LLM orchestration, and verification. The question is whether these
responsibilities should be implemented as separate microservices from the start
or as a single deployable unit with internal module boundaries.

---

## Decision

FanCue begins as a **modular monolith**: all backend modules run in a single
Python process, but are organized into clearly bounded directories with
explicit interfaces and no shared global state between domain modules.

Module boundaries are designed so that a single module could be extracted into
an independent service later without changing its public interface.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| Microservices from day one | Premature operational complexity. Network partitions, distributed tracing, and service discovery add cost before the domain is proven. |
| Single unstructured monolith | No module boundaries = uncontrolled coupling. Extraction later becomes a rewrite. |
| Serverless functions per step | Orchestration complexity and cold-start latency are inappropriate for a synchronous fan-facing response path. |

---

## Consequences

- Deployment is simple in early phases: one Docker container for the backend.
- Module interfaces must be treated as if they were network APIs — no leaking
  of internal implementation details between modules.
- When a module needs to be scaled or isolated independently, extraction
  follows a documented extraction checklist (to be created in Phase 07).
- Operational simplicity is traded for some scaling inflexibility at high load.

---

## Conditions for Revisiting

- If a single module becomes a measured throughput or latency bottleneck that
  cannot be solved within the monolith.
- If two modules require independent deployment lifecycles (e.g., the
  knowledge ingestion pipeline vs. the fan-facing API).
- Extraction must be justified by measurement, not prediction.
