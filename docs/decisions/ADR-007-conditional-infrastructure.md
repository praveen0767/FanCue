# ADR-007 — Conditional Adoption of Redis, Workers, Transactional Outbox, and MCP

**Status:** Accepted
**Date:** 2026-10-11
**Phase:** 00

---

## Context

Distributed systems components (Redis, message queues, transactional outboxes,
background workers, MCP servers) add operational complexity, failure modes, and
testing overhead. Their value is real — but only when they solve a documented,
measured problem that simpler synchronous processing cannot solve.

Adding them preemptively produces infrastructure that must be operated,
monitored, and debugged before it has earned its place in the system.

---

## Decision

Redis, background workers, a transactional outbox, durable queues, and MCP
are **not included** in the initial docker-compose.yml or backend architecture.
They may be added in Phase 07 or later **only** if all four adoption conditions
are documented and verified:

1. **Workload or failure mode**: Describe the specific scenario that requires
   the component (e.g., "LLM call takes 8 seconds; fan-facing request cannot
   block for 8 seconds without timeout").
2. **Why synchronous is insufficient**: Explain why the problem cannot be
   solved by increasing timeout limits, optimistic caching, or pre-computation.
3. **Delivery and idempotency guarantees**: State exactly what at-least-once,
   at-most-once, or exactly-once semantics are required and why.
4. **How guarantees will be tested**: Describe the test that confirms the
   guarantee holds under failure (worker crash, network partition, duplicate
   delivery).

### MCP

MCP is explicitly **not** on the fan-facing request path. It may be considered
in a later phase for authorized, typed operational tooling (e.g., a
knowledge-ingestion management tool). Any MCP adoption requires a separate ADR.

### PostgreSQL (special case)

PostgreSQL **is** included in the initial docker-compose.yml because:
- Durable storage for match metadata, dataset revisions, and evaluation records
  is a foreseeable and documented need (Phase 07).
- Including it in Docker Compose now costs nothing operationally (no application
  code depends on it yet).
- Its absence later would require migrating from an interim solution.

PostgreSQL must not be used by application code until Phase 07 defines its
schema, migration strategy, and access patterns.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| Include Redis from day one | No documented current requirement. Adds auth, persistence config, and failure mode with no current benefit. |
| Background worker for every LLM call | Premature. Fan-facing requests are synchronous in the initial design. |
| Message queue for event ingestion | No live feed ingestion in Phase 00-06. When ingestion is introduced, evaluate then. |
| MCP on fan-facing path | Adds an extra hop and operational component for no fan-facing benefit. |

---

## Consequences

- The docker-compose.yml remains minimal (Qdrant + PostgreSQL only).
- Phase 07 is the earliest point where Redis or workers may be introduced.
- Every infrastructure addition requires updating this ADR with the four
  adoption conditions filled in.
- The current synchronous architecture must be load-tested before claiming
  it is insufficient and adding async components.

---

## Conditions for Revisiting

- When a measured latency or throughput problem is documented with data.
- When the ingestion pipeline introduces genuine fan-facing consistency
  requirements that synchronous processing cannot meet.
