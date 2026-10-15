# FanCue — MVP Scope & Feature Prioritization (V1)

**Version:** 1.0  
**Phase:** 01 — Product Specification  
**Status:** Normative for Phase 02 through Phase 06  
**Last updated:** 2026-10-11  

> **Current implementation note (2026-10-14):** This is the original MVP plan; planned capabilities below are not proof they are enabled in production. The checked-in `render.yaml` sets `FANCUE_RETRIEVAL_ENABLED=false`, so production Qdrant retrieval is currently off.

> **Core Constraint:** The five-day assignment prioritizes **one working, verified fan artifact**
> over a large surface of incomplete features. A narrower, rigorously verified cricket implementation
> is strictly preferable to two partial or unverified sport implementations.

---

## 1. Product Scope Philosophy

FanCue is built on the discipline of deterministic match truth, bounded AI explanations, and inspectable evidence. To deliver a working, trustworthy product within the assignment timeframe, every potential feature is categorized into one of three strict priority tiers:

- **P0 (Assignment-Critical):** Without these capabilities, FanCue cannot fulfill its core promise. All engineering effort focuses here until the critical path passes its exit gates.
- **P1 (Conditional Polish):** Features that add meaningful value or evaluate secondary hypotheses, attempted **only** if the P0 path is healthy, verified, and ahead of schedule.
- **P2 (Explicitly Deferred):** Features, integrations, and architectural components that are permanent non-goals for V1 or deferred to future phases.

---

## 2. P0 — Assignment-Critical (Must Ship)

The P0 scope represents the complete, end-to-end historical cricket catch-up journey. Every item in this list is required for the V1 release:

| Area | Feature / Capability | Rationale |
|---|---|---|
| **Match Selection** | Historical cricket fixture selection from ingested Cricsheet datasets (with documented provenance). | Provides repeatable, authoritative match ground truth without live API dependencies. |
| **Interval Selection** | Whole-over interval boundaries within a single innings (e.g., overs 13 through 18). | Clear, unambiguous domain boundary model that avoids fractional over ambiguities. |
| **Deterministic State Engine** | Start state, end state, and state-difference computation (runs, wickets, overs, legal balls, partnerships, run rates). | Pure deterministic computation; sole truth authority; identical input yields identical output. |
| **Consequential Event Selection** | Algorithmic ranking and extraction of key interval events (wickets, milestone overs, high-run overs, maidens). | Separates noise from signal deterministically before any LLM prompt assembly. |

| **Evidence Packet Assembly** | Assembly of structured evidence packets containing exact event IDs, source scorecard references, and retrieved document IDs (`doc_id`). | Enables full provenance tracking and verification. |
| **Bounded AI Explanation** | Structured LLM generation (Pydantic contract) producing concise, factual summaries explaining *how* and *why* the interval changed. | Provides the narrative synthesis fans require while constraining output format. |
| **Automated Verification** | Post-generation verification comparing LLM assertions against deterministic engine delta and retrieved doc IDs. | Catches hallucinations and fabricated numbers before fan presentation. |
| **Deterministic Fallback** | Instant structured recap generated purely from engine state and key events if LLM fails, times out (>5s), or fails verification. | Ensures FanCue is always functional even with zero LLM API availability. |
| **Replay & Mode Disclosure** | Prominent visual badge stating: "HISTORICAL REPLAY — SOURCE: CRICSHEET". | Absolute transparency regarding data freshness; prevents false live claims. |
| **Inspectable Evidence UI** | Functional web interface displaying score delta, narrative summary, key events timeline, and expandable evidence drawer with provenance. | Allows the fan to inspect the underlying facts behind every assertion. |

---

**Deployment distinction:** Qdrant retrieval was implemented/evaluated as optional context enrichment, but is not a P0 production dependency. The checked-in Render declaration turns it off. Retrieval metrics below describe the documented development evaluation only; they do not show that Qdrant is connected in the deployed service.

## 3. P1 — Conditional (Only if P0 Critical Path is Healthy)

P1 capabilities will only be implemented if the P0 cricket pipeline passes its Phase 05/06 acceptance gates ahead of schedule:

| Feature | Condition for Attempting | Fallback / Mitigation if Deferred |
|---|---|---|
| **Tamil Language Evaluation** | Complete English baseline passes AI verification; manual linguistic review framework established. | Default to English (`en`) as the sole verified language; document Tamil evaluation results in validation report. |
| **Team / Player Perspective Lens** | Core deterministic recap and evidence assembly pass all integration tests. | Present neutral, match-centric summary by default without perspective weighting. |
| **State Delta Caching** | Performance profiling shows repeated queries for identical match intervals causing CPU bottlenecks. | Recompute state deterministically per request (data fits in memory for single matches). |
| **Structured Telemetry & Latency Instrumentation** | E2E request path functional; need granular breakdown of engine vs Qdrant vs LLM latencies. | Standard structured console logging with millisecond timestamps. |

---

## 4. P2 — Explicitly Deferred (Out of Scope for V1)

The following features, architectures, and integrations are **explicitly excluded** from the initial release:

| Capability | Category | Reason for Deferral |
|---|---|---|
| **Football Adapter Implementation** | Multi-sport | Cricket is the first complete slice (ADR-006). Football architecture is decoupled and reserved for Phase 08. |
| **Live Match Feeds & Streaming Ingestion** | Data source | Requires commercial feed licenses, websocket infrastructure, and out-of-order delivery handling. Historical Cricsheet data provides complete provenance for V1. |
| **Exact Broadcast Synchronization** | Media sync | Requires frame-accurate video clock sync and proprietary OTT watermarking. FanCue V1 operates on completed over boundaries. |
| **High-Concurrency Scale (50M users)** | Infrastructure | Premature optimization. V1 targets single-instance reliability and deterministic correctness. |
| **Redis / Celery Background Queues** | Infrastructure | Synchronous request-response is sufficient for V1; adding message brokers introduces unnecessary operational failure modes (ADR-007). |
| **Transactional Outbox / Event Sourcing** | Infrastructure | No distributed state writes in V1; queries are read-only match reconstructions. |
| **MCP (Model Context Protocol) on Request Path** | Infrastructure | Unnecessary indirection on fan-facing critical path; bounded internal function calls are faster and strictly typed. |
| **Multi-Agent Swarms / Autonomous Agents** | AI Architecture | Unbounded multi-agent loops introduce latency and hallucination cascade risks. V1 uses a single structured pipeline with verification. |
| **Betting, Wagering & Odds Integration** | Product Policy | Permanent non-goal. FanCue is an educational and contextual match platform, not a gambling or prediction service. |
| **Push Notifications & Gamified Engagement** | Growth / Retention | Avoid dark patterns and unverified engagement loops. FanCue is pull-based context on fan demand. |
| **User Authentication & Accounts** | Platform | Unnecessary friction for initial fan validation and core journey testing. |

---

## 5. Scope Boundary Matrix

```
+-------------------------------------------------------------------------+
|                              FANCUE V1                                  |
|                                                                         |
|  [ IN SCOPE - P0 ]                     [ CONDITIONAL - P1 ]            |
|  - Historical Cricket Matches (Cricsheet) - Tamil Language (after eval) |
|  - Whole-Over Intervals                - Perspective Lens (Team/Player)|
|  - Deterministic State Engine & Delta  - State Delta Caching           |
|  - Consequential Event Selection       - Granular Telemetry Latency    |
|  - Optional Qdrant Knowledge Retrieval (off in current Render config)                                |
|  - Structured AI Explanation (Pydantic)                                |
|  - Post-Generation Fact Verification                                   |
|  - Deterministic Fallback                                   |
|  - Replay / Source Transparency Badge                                  |
|  - Web UI with Evidence Drawer                                         |
|                                                                         |
+-------------------------------------------------------------------------+
                                    |
                                    v [ DEFERRED - P2 ]
                      - Football Adapter (Phase 08)
                      - Live Match Feeds / OTT Frame Sync
                      - Redis / Distributed Workers / Outbox
                      - Multi-Agent Autonomous Swarms
                      - Betting / Fantasy / Gambling
                      - Push Notifications / Dark Engagement
```

---

## 6. Traceability to Master Acceptance Criteria

Every P0 feature maps directly to one or more criteria in `docs/product/acceptance-criteria.md`:

- Match Selection → `AC-01`
- Interval Boundaries → `AC-02`, `ENG-01`, `ENG-02`
- Deterministic State Reconstruction → `AC-03`, `ENG-03`, `ENG-04`, `ENG-05`
- Evidence Traceability → `AC-04`, `ENG-07`
- Perspective Lens (P1) → `AC-05`
- Optional Context Retrieval (only when enabled) → `AC-06`, `RET-01`, `RET-02`
- AI Explanation & Verification → `AC-07`, `AI-01`, `AI-02`, `AI-03`
- Deterministic Fallback → `AC-08`, `OPS-02`
- Replay Disclosure → `AC-09`, `OPS-03`
- Tamil Language Review (P1) → `AC-10`
- Response Latency → `AC-11`, `OPS-01`
- Usability Testing → `AC-12`
