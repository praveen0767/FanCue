# FanCue — Data Contracts Architecture

**Version:** 1.0.0  
**Phase:** 02 — Canonical Contracts & Governance  
**Status:** Normative for Phase 03 through Phase 06  
**Last updated:** 2026-10-11  

---

## 1. Architectural Philosophy

FanCue enforces explicit, typed contracts across all boundaries. Contracts are defined
**before** any domain logic, API endpoints, retrieval pipelines, or user interfaces are built.

Key governing principles (historical design baseline; optional components may be disabled in a deployment):
1. **Single Source of Truth:** Pydantic v2 models in `backend/app/schemas/` define canonical Python types; JSON Schemas in `contracts/` are generated directly from them without manual synchronization drift.
2. **Deterministic Truth Separation:** The match engine is the sole truth authority for match state, scores, and deltas. Neither LLM prose nor optional Qdrant vector similarity scores may mutate authoritative numbers. The current Render configuration disables retrieval.
3. **Sport Boundary Isolation:** Cricket and football contracts are completely separated. They share no scoring formulas, interval representations, or event types.
4. **Inspectable Evidence:** Every fact in an explanation must link back to an atomic `EvidenceFact` with verified source event IDs and dataset provenance.
5. **No `any` or Untyped Dictionaries:** Core state, intervals, deltas, and evidence packets use strict types and forbid unknown fields (`extra="forbid"`).

---

## 2. Contract Inventory

The FanCue contract architecture is organized into five distinct domain clusters:

```
+---------------------------------------------------------------------------------+
|                               COMMON CONTRACTS                                  |
|   SportType | LanguageCode | PerspectiveLens | MatchDescriptor | Correlation    |
+---------------------------------------------------------------------------------+
           |                                                      |
           v                                                      v
+-------------------------------+              +----------------------------------+
|       CRICKET CONTRACTS       |              |   PROVISIONAL FOOTBALL CONTRACTS |
| CricketInterval (whole-over)  |              | FootballInterval (minute-based)  |
| CricketCatchUpRequest         |              | FootballCatchUpRequest           |
| CricketScoreSnapshot          |              | FootballScoreSnapshot            |
| CricketStateDelta             |              | FootballStateDelta               |
| CricketDeliveryEvent          |              | FootballMatchEvent               |
+-------------------------------+              +----------------------------------+
           |                                                      |
           +--------------------------+---------------------------+
                                      |
                                      v
+---------------------------------------------------------------------------------+
|                             EVIDENCE CONTRACTS                                  |
|         FactType | EvidenceFact | MatchEvidencePacket | SourceProvenance        |
+---------------------------------------------------------------------------------+
           |                                                      |
           v                                                      v
+-------------------------------+              +----------------------------------+
|      RETRIEVAL CONTRACTS      |              |      EXPLANATION CONTRACTS       |
| RetrievalQuery                |              | StructuredClaim (fact citations) |
| RetrievedPassage              |              | GenerationMode | Verification    |
| RetrievalResult (status)      |              | CricketCatchUpResponse           |
+-------------------------------+              +----------------------------------+
                                      |
                                      v
+---------------------------------------------------------------------------------+
|                                ERROR CONTRACTS                                  |
|                  ErrorCode | ErrorDetail | ErrorResponse                        |
+---------------------------------------------------------------------------------+
```

---

## 3. Deep Domain Boundaries

### 3.1 Cricket Interval Boundary Semantics
Following [interval-model.md](file:///D:/FanCue/docs/product/interval-model.md) and [ADR-008](file:///D:/FanCue/docs/decisions/ADR-008-v1-interval-semantics-and-language-scope.md):
- An interval is bounded by **whole overs** within a single innings.
- `start_after_over`: 0-based integer, exclusive. The sentinel value `-1` explicitly denotes the innings start (prior to any delivery bowled).
- `end_after_over`: 0-based integer, inclusive.
- Constraint: `end_after_over > start_after_over`.
- Prohibitions: Decimal floats (e.g. `12.4`) are strictly rejected.

### 3.2 Evidence Packet Assembly
The `MatchEvidencePacket` is the immutable bridge between the deterministic match engine and the AI orchestrator:
- Assembled strictly from engine calculations; Qdrant context is optional and omitted when retrieval is disabled or unavailable.
- Carries full `SourceProvenance` (source ID, license, archive SHA-256, fixture SHA-256).
- Every atomic fact possesses a unique, reproducible `fact_id` and cites source event IDs.

### 3.3 Verification & Bounded Explanation
The `CricketCatchUpResponse` contains an `ExplanationPayload`:
- Contains granular `StructuredClaim` items.
- Factual claims must cite one or more `cited_fact_ids` belonging to the accompanying evidence packet.
- Background context claims may cite `cited_knowledge_ids` from Qdrant when retrieved passages are present; otherwise the response is grounded in deterministic match facts alone.
- If verification fails or LLM is disabled, `generation_mode` is set to `deterministic_fallback` and `verification_status` reflects the outcome with an explicit `fallback_reason`.

---

## 4. Schema Artifact Locations

| Canonical Pydantic Module | Authoritative JSON Schema |
|---|---|
| `backend/app/schemas/common.py` | `contracts/common.schema.json` |
| `backend/app/schemas/provenance.py` | `contracts/provenance.schema.json` |
| `backend/app/schemas/cricket.py` | `contracts/cricket_catchup_request.schema.json` |
| `backend/app/schemas/cricket.py` | `contracts/cricket_event_state.schema.json` |
| `backend/app/schemas/football.py` | `contracts/provisional_football.schema.json` |
| `backend/app/schemas/evidence.py` | `contracts/evidence_packet.schema.json` |
| `backend/app/schemas/retrieval.py` | `contracts/retrieval.schema.json` |
| `backend/app/schemas/explanation.py` | `contracts/explanation.schema.json` |
| `backend/app/schemas/explanation.py` | `contracts/cricket_catchup_response.schema.json` |
| `backend/app/schemas/errors.py` | `contracts/error_response.schema.json` |
