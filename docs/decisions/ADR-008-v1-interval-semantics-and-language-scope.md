# ADR-008 — V1 Interval Semantics, Language Scope, and Historical Replay Baseline

**Status:** Accepted  
**Date:** 2026-10-11  
**Phase:** 01 — Product Specification  

---

## Context

Phase 00 established foundational architectural principles (ADR-001 through ADR-007). However, several key product-level decisions directly affect the data contracts (Phase 02), match engine implementation (Phase 03), Qdrant retrieval (Phase 04), and UI orchestration (Phase 06):

1. **Interval Representation:** Cricket over notation is frequently misunderstood as decimal numbers (e.g., treating "10.4 overs" as a float `10.4`), which breaks mathematical sorting, legal ball counts, and boundary comparisons. Furthermore, intervals could theoretically be delivery-based, ball-index-based, or over-based.
2. **Language Scope:** Early notes mentioned regional languages (specifically Hindi in initial vision drafts). However, the project owner can directly evaluate Tamil linguistic quality, while shipping unvalidated languages violates product trust rules.
3. **Data Freshness / Mode:** Ambiguity between live match ingestion and historical match replay could lead to premature complexity (WebSockets, real-time feed licenses, handling in-flight balls).
4. **Contextual Knowledge vs. Event Evidence:** Determining the boundary between authoritative match event logs and Qdrant semantic context documents.
5. **Metric Hierarchy:** Defining whether response latency, narrative fluency, or factual correctness takes precedence.

---

## Decision

1. **Whole-Over Interval Boundaries (V1):**  
   - Boundaries are specified as whole completed overs within a single innings: `after_over` integer index (`-1` represents innings start; `0` represents end of 1st completed over; `19` represents end of 20th over).
   - Start boundary is exclusive of previous action; end boundary is inclusive of final delivery of that over.
   - Ball-by-ball boundary selection is explicitly deferred to later iterations once source schemas are fully verified.
   - Decimal float representation of overs is strictly prohibited across all data models and database schemas.

2. **Language Scope — English Baseline with Evaluated Tamil Secondary:**  
   - English (`en`) is the normative baseline output language.
   - Tamil (`ta`) is the first additional evaluation language because the project owner possesses native competence to audit nuance, terminology, and factual translation fidelity.
   - Tamil support will only be promoted to active user-facing status if it passes the manual verification protocol defined in `AC-10`. Hindi and other regional languages are deferred.

3. **Historical Replay as Primary Source Mode:**  
   - V1 strictly operates in historical replay mode using curated, open-licensed Cricsheet match files.
   - Live streaming feeds and frame-synchronous broadcast hooks are deferred (P2). The UI must prominently display an immutable "HISTORICAL REPLAY" badge with data provenance.

4. **Separation of Event Evidence and Semantic Knowledge:**  
   - Event facts (runs, wickets, deliveries) are stored and processed exclusively by the deterministic match engine.
   - Qdrant stores only immutable background knowledge (cricket laws, glossary, tournament history, tactics).
   - The LLM prompt receives an assembled Evidence Packet that strictly separates deterministic delta facts from retrieved knowledge chunks.

5. **Strict Metric Hierarchy:**  
   - Factual Correctness (0 hallucinated score facts) > Evidence Traceability > Deterministic Fallback Availability > Response Latency (< 5s for fallback, < 30s for AI) > Narrative Fluency.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Delivery-level boundary selection (e.g., over 12.3 to 18.2) | Cricsheet delivery sequences include extras (wides/no-balls) that do not advance the legal ball count. Fractional over handling increases contract complexity before the engine is built. |
| Decimal float overs (`float: 12.4`) | IEEE 754 floating-point inaccuracies cause arithmetic bugs (e.g. `12.6` vs `13.0`); overs are base-6 counters, not tenths. |
| Hindi as first regional language | Project owner cannot directly evaluate Hindi linguistic accuracy with authoritative rigor. Shipping unverified LLM translations violates truth constraints. |
| Live feed simulation / mock streaming | Adds WebSocket state, backpressure, and jitter management without adding fundamental value to the core interval context problem. |
| Storing match events inside Qdrant | Vector databases perform approximate nearest-neighbor search, not deterministic aggregations or chronologically ordered event replays. |

---

## Consequences

- **Backend Contracts (Phase 02):** Pydantic models will represent interval boundaries as explicit integers (`after_over: int`), never floats.
- **Qdrant Schema (Phase 04):** Payloads must enforce `language: "en" | "ta"` and `sport: "cricket"` metadata tagging.
- **Verification Engine (Phase 05):** The verification pipeline will assert exact match against the deterministic delta; any discrepancy between LLM text and engine facts immediately routes to deterministic fallback.
- **UI (Phase 06):** Dropdowns or sliders will present whole-over options (e.g., "After Over 10" to "End of Over 15").

---

## Conditions for Revisiting

- Delivery-level boundaries may be introduced in Phase 07 if fan testing (`AC-12`) demonstrates that whole-over intervals fail to capture critical partial-over turning points (e.g. rain delays mid-over).
- Additional languages (Hindi, Kannada, Telugu) may be added if certified evaluators with domain knowledge are assigned to execute `AC-10` linguistic reviews.
