# FanCue — API Contract Specification (OpenAPI Preview)

> **Scope note:** This is a design-contract preview, not the active OpenAPI document. Current deployed routes are unversioned (`/catchup`, `/matches`, etc.). The Render blueprint uses Groq (`openai/gpt-oss-20b`) and disables Qdrant retrieval. Retrieval steps below are conditional and are not a claim about the production path.

**Version:** 1.0.0  
**Phase:** 02 — Canonical Contracts & Governance  
**Status:** Design Preview (No endpoints implemented in Phase 02)  
**Base URL:** `/v1`  
**Protocol:** HTTP/1.1 or HTTP/2 over TLS (JSON request/response)  

> **Implementation Notice:** This document specifies the binding HTTP contract for the future
> FastAPI service. In accordance with Phase 02 boundaries, **no endpoint handlers are implemented
> in this phase.**

---

## 1. Overview & Execution Model

The FanCue API is initially **synchronous request-response**:
- Match-state reconstruction and delta calculation are deterministic; latency has not been measured in this design document.
- Qdrant similarity search is optional and only runs when retrieval is configured and enabled.
- LLM latency depends on provider, model, network, and quota; do not interpret the design as a measured service-level target.
- As detailed in [ADR-007](file:///D:/FanCue/docs/decisions/ADR-007-conditional-infrastructure.md), background workers and queues (Redis/Celery) are unnecessary and avoided for V1 historical replay catch-ups.

---

## 2. Endpoint Specifications

### 2.1 `GET /v1/matches`
Lists all supported historical match fixtures ingested and available for interval exploration.

- **Execution Mode:** Synchronous (read-only)
- **Query Parameters:**
  - `sport` (optional, string): Filter by sport (`cricket` or `football`). Default: `cricket`.
  - `format` (optional, string): Filter by format (`ODI`, `T20`, etc.).
- **Response Headers:** `Content-Type: application/json`
- **200 OK Response Schema:**
  ```json
  {
    "matches": [
      {
        "match_id": "1529229",
        "sport": "cricket",
        "name": "India vs West Indies",
        "format": "ODI",
        "teams": ["India", "West Indies"],
        "date": "2026-10-03",
        "venue": "Sabina Park, Kingston",
        "mode": "replay",
        "source_id": "cricsheet_historical_odi",
        "source_revision": "1",
        "supported_innings": [0, 1]
      }
    ]
  }
  ```
- **Error Responses:**
  - `500 INTERNAL_ERROR`: Internal dataset index unavailable.

---

### 2.2 `GET /v1/matches/{match_id}`
Retrieves detailed metadata, supported innings, and dataset provenance for a specific match fixture.

- **Execution Mode:** Synchronous (read-only)
- **Path Parameters:**
  - `match_id` (string, required): Stable match ID (e.g. `1529229`).
- **200 OK Response Schema:**
  - Emits `MatchDescriptor` envelope with embedded `SourceProvenance`.
- **Error Responses:**
  - `404 MATCH_NOT_FOUND`: If match ID is not in the ingested dataset registry.
    ```json
    {
      "error": {
        "code": "MATCH_NOT_FOUND",
        "message": "Match '9999999' is not supported in the historical dataset index.",
        "field": "match_id",
        "context": {"match_id": "9999999"}
      },
      "correlation_id": "corr_abc123456",
      "timestamp": "2026-10-11T12:00:00Z"
    }
    ```

---

### 2.3 `POST /v1/catchups`
The primary fan journey endpoint. Validates interval boundaries, computes deterministic state differences, optionally retrieves Qdrant context when enabled, generates a structured explanation, verifies claims, and returns a verified response or a deterministic fallback when generation is unavailable or rejected.

- **Execution Mode:** Synchronous
- **Request Headers:**
  - `Content-Type: application/json`
  - `X-Correlation-ID` (optional, string): Tracing identifier.
- **Request Body:** [`CricketCatchUpRequest`](file:///D:/FanCue/backend/app/schemas/cricket.py)
  ```json
  {
    "match_id": "1529229",
    "interval": {
      "innings": 0,
      "start_after_over": 14,
      "end_after_over": 22
    },
    "lens": "match",
    "target_entity": null,
    "language": "en",
    "explanation_depth": "standard",
    "correlation_id": "corr_req_98765432"
  }
  ```
- **200 OK Response Schema:** [`CricketCatchUpResponse`](file:///D:/FanCue/backend/app/schemas/explanation.py)
  ```json
  {
    "match": {
      "match_id": "1529229",
      "sport": "cricket",
      "name": "India vs West Indies",
      "format": "ODI",
      "teams": ["India", "West Indies"],
      "date": "2026-10-03",
      "venue": null,
      "mode": "replay",
      "source_id": "cricsheet_historical_odi",
      "source_revision": "1",
      "supported_innings": [0, 1]
    },
    "interval": {
      "innings": 0,
      "start_after_over": 14,
      "end_after_over": 22
    },
    "state_before": {
      "runs": 89,
      "wickets": 2,
      "overs_completed": 15,
      "legal_balls_in_over": 0,
      "extras_total": 4,
      "run_rate": 5.93
    },
    "state_after": {
      "runs": 142,
      "wickets": 3,
      "overs_completed": 23,
      "legal_balls_in_over": 0,
      "extras_total": 6,
      "run_rate": 6.17
    },
    "state_delta": {
      "runs_added": 53,
      "wickets_lost": 1,
      "completed_overs_delta": 8,
      "legal_balls_added": 48,
      "extras_added": 2,
      "interval_run_rate": 6.62
    },
    "evidence_packet": { ... },
    "explanation": {
      "summary": "India added 53 runs across overs 15 to 22, losing 1 wicket...",
      "claims": [ ... ],
      "generation_mode": "llm_verified",
      "verification_status": "verified",
      "fallback_reason": "none"
    },
    "language": "en",
    "mode": "replay",
    "generated_at": "2026-10-11T12:00:01Z",
    "warnings": []
  }
  ```
- **Error Responses:**
  - `400 MALFORMED_REQUEST`: Schema syntax or type violation (e.g. decimal float over supplied).
  - `400 INVALID_INTERVAL`: Boundary violation (e.g. `start_after_over >= end_after_over` or negative index other than `-1`).
  - `404 MATCH_NOT_FOUND`: Target match ID does not exist in dataset.
  - `422 DATA_VALIDATION_FAILURE`: Requested overs exceed recorded innings completion.

---

### 2.4 `GET /v1/health/ready`
Liveness and readiness probe for orchestration and load balancer readiness.

- **Execution Mode:** Synchronous
- **200 OK Response Schema:**
  ```json
  {
    "status": "ready",
    "dataset_index": "loaded",
    "qdrant_status": "connected",
    "llm_status": "ready"
  }
  ```
- **503 SERVICE_UNAVAILABLE:** If local storage or dataset index is corrupt or unreadable.
