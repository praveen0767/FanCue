# FanCue — Phase 02 Completion Report

**Phase:** 02 — Canonical Contracts, Typed Domain Schemas, Data Provenance, Licensing Governance, and Contract Testing  
**Date:** 2026-10-11  
**Author:** Principal Software Architect / Data Governance Engineer  
**Status:** Completed & Ready for Review  

---

## 1. Executive Summary

Phase 02 established the formal contract boundaries and data-source governance foundation for FanCue. It converted the product specifications and whole-over interval semantics from Phase 01 into typed Pydantic v2 domain schemas, exported 10 authoritative JSON Schemas, established the Cricsheet historical data provenance registry with audited licensing terms (ODC-By v1.0), acquired and cryptographically verified a real historical ODI match fixture (India vs West Indies), drafted an OpenAPI-compatible HTTP contract preview, and implemented a comprehensive suite of 39 automated contract tests—all passing offline on Python 3.12.

No match engine code, API endpoint implementation, UI components, Qdrant pipelines, or LLM providers were created.

---

## 2. Changed and Created Files

### Contract Source Models (Pydantic v2)
- `backend/app/schemas/common.py` — Common enums (`SportType`, `LanguageCode`, `PerspectiveLens`, `ExplanationDepth`, `MatchMode`), `MatchDescriptor`, and `RequestCorrelation`.
- `backend/app/schemas/provenance.py` — `SourceProvenance` and `PermittedUse` with strict timezone-aware validation and SHA-256 formatting.
- `backend/app/schemas/cricket.py` — `CricketInterval` (whole-over boundaries, -1 sentinel, progression validation), `CricketCatchUpRequest`, `CricketScoreSnapshot`, `CricketStateDelta`, and normalized `CricketDeliveryEvent`.
- `backend/app/schemas/football.py` — Provisional, decoupled `FootballInterval`, `FootballCatchUpRequest`, `FootballScoreSnapshot`, `FootballStateDelta`, and `FootballMatchEvent`.
- `backend/app/schemas/evidence.py` — `FactType`, `EvidenceFact` (atomic event citations), and `MatchEvidencePacket`.
- `backend/app/schemas/retrieval.py` — `RetrievalQuery`, `RetrievedPassage`, `RetrievalResult`, and `RetrievalStatus`.
- `backend/app/schemas/explanation.py` — `ClaimType`, `StructuredClaim`, `ExplanationPayload`, and `CricketCatchUpResponse`.
- `backend/app/schemas/errors.py` — `ErrorCode`, `ErrorDetail`, and `ErrorResponse`.
- `backend/app/schemas/__init__.py` — Unified package exports.
- `backend/__init__.py` & `backend/app/__init__.py` — Package markers.

### Generated JSON Schema Artifacts
- `contracts/common.schema.json`
- `contracts/provenance.schema.json`
- `contracts/cricket_catchup_request.schema.json`
- `contracts/cricket_event_state.schema.json`
- `contracts/evidence_packet.schema.json`
- `contracts/retrieval.schema.json`
- `contracts/explanation.schema.json`
- `contracts/cricket_catchup_response.schema.json`
- `contracts/provisional_football.schema.json`
- `contracts/error_response.schema.json`
- `contracts/export_schemas.py` — Schema export generator script.

### Data Governance & Architecture Documentation
- `data/sources.yml` — Canonical provenance registry recording Cricsheet ODC-By v1.0 terms, archive hash, and fixture hash.
- `data/ATTRIBUTION.md` — Mandatory legal attribution notice.
- `docs/architecture/data-contracts.md` — Contract architecture guide and component boundary matrix.
- `docs/architecture/schema-versioning.md` — SemVer 2.0.0 evolution and compatibility rules.
- `docs/architecture/api-contracts.md` — OpenAPI preview for `/v1/matches`, `/v1/matches/{match_id}`, `/v1/catchups`, `/v1/health/ready`.
- `pyproject.toml` — Pinned Python `>=3.12`, dependencies, and pytest configuration.

### Contract Test Suite
- `tests/contracts/test_common_contracts.py` (6 tests)
- `tests/contracts/test_cricket_contracts.py` (15 tests)
- `tests/contracts/test_provenance_contracts.py` (5 tests)
- `tests/contracts/test_evidence_contracts.py` (3 tests)
- `tests/contracts/test_explanation_contracts.py` (4 tests)
- `tests/contracts/test_football_contracts.py` (6 tests)

### Roadmap & Status Updates
- `README.md` — Updated status table and architecture documentation links.
- `docs/plan/roadmap.md` — Marked Phase 02 complete and exit gate checked off.
- `docs/plan/phase-02-completion-report.md` — This report.

---

## 3. Contract Inventory & Versioning

All schemas are versioned at `1.0.0` with JSON Schema Draft 2020-12 IDs (`https://fancue.org/schemas/v1/...`):

| Cluster | Models | Schema File |
|---|---|---|
| Common | `SportType`, `LanguageCode`, `MatchDescriptor`, `RequestCorrelation` | `contracts/common.schema.json` |
| Provenance | `SourceProvenance`, `PermittedUse` | `contracts/provenance.schema.json` |
| Cricket Request | `CricketInterval`, `CricketCatchUpRequest` | `contracts/cricket_catchup_request.schema.json` |
| Cricket Engine | `CricketScoreSnapshot`, `CricketStateDelta`, `CricketDeliveryEvent` | `contracts/cricket_event_state.schema.json` |
| Evidence | `EvidenceFact`, `MatchEvidencePacket` | `contracts/evidence_packet.schema.json` |
| Retrieval | `RetrievalQuery`, `RetrievedPassage`, `RetrievalResult` | `contracts/retrieval.schema.json` |
| Explanation | `StructuredClaim`, `ExplanationPayload` | `contracts/explanation.schema.json` |
| Response | `CricketCatchUpResponse` | `contracts/cricket_catchup_response.schema.json` |
| Provisional Football | `FootballCatchUpRequest`, `FootballScoreSnapshot`, `FootballMatchEvent` | `contracts/provisional_football.schema.json` |
| Errors | `ErrorResponse`, `ErrorDetail`, `ErrorCode` | `contracts/error_response.schema.json` |

---

## 4. Data-Source Licensing Findings & Fixture Selection

### 4.1 Legal Licensing Review
- **Source:** Cricsheet ([https://cricsheet.org/](https://cricsheet.org/))
- **License:** Open Data Commons Attribution License (ODC-By v1.0).
- **License Text:** [http://opendatacommons.org/licenses/by/1.0/](http://opendatacommons.org/licenses/by/1.0/)
- **Permitted Use:** Open sharing, copying, adapting, and creating works from the dataset, subject to attribution.
- **Attribution Statement:**
  > *"Data provided by Cricsheet (https://cricsheet.org/), licensed under the Open Data Commons Attribution License (ODC-By v1.0)."*
- **Redistribution Policy:** Raw data files remain strictly inside gitignored `data/raw/` and are not committed to Git.

### 4.2 Selected Fixture Provenance
To avoid downloading massive archives, the targeted 118 KB archive `recently_added_2_json.zip` was audited. A complete historical ODI fixture directly supporting Scenario A (overs 15–22 catch-up) was selected and verified:

- **Match ID:** `1529229`
- **Fixture:** Men's One-Day International — India vs West Indies (50 overs per side)
- **Match Date:** `2026-10-03`
- **Format:** Cricsheet JSON Format v1.3.0
- **Created Date:** `2026-10-06` (Revision 1)
- **Local Location:** `data/raw/1529229.json` (gitignored)
- **Fixture SHA-256:** `8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f`
- **Archive SHA-256:** `282b4543e36aae90bf14ab9e2cbd0f8829dfdd8b3e4a97b711b0336d69b5ba74`

---

## 5. Contract Validation Rules Implemented

1. **Integer Over Boundaries:** Rejects decimal floats (e.g. `12.4`); enforces `start_after_over >= -1` and `end_after_over > start_after_over`.
2. **Sentinels:** `-1` explicitly accepted as innings start; boundaries `< -1` rejected.
3. **Perspective Constraints:** Team and player lenses require non-null `target_entity`.
4. **Strict Isolation:** Football schemas strictly reject cricket concepts (such as `after_over`).
5. **No Unknown Fields:** `extra="forbid"` enforced across all domain models to prevent silent data corruption.
6. **Timezone Awareness:** All datetimes must be timezone-aware UTC.
7. **Hash Formatting:** Cryptographic hashes validated against 64 lowercase hex characters.

---

## 6. Tests Executed & Results

Command executed:
```powershell
.venv\Scripts\pytest tests/contracts -v
```

Observed output:
```
tests/contracts/test_common_contracts.py::test_valid_match_descriptor PASSED
tests/contracts/test_common_contracts.py::test_match_descriptor_invalid_sport PASSED
tests/contracts/test_common_contracts.py::test_match_descriptor_invalid_date_format PASSED
tests/contracts/test_common_contracts.py::test_match_descriptor_forbids_extra_fields PASSED
tests/contracts/test_common_contracts.py::test_valid_request_correlation PASSED
tests/contracts/test_common_contracts.py::test_request_correlation_too_short PASSED
tests/contracts/test_cricket_contracts.py::test_valid_whole_over_interval PASSED
tests/contracts/test_cricket_contracts.py::test_valid_interval_innings_start PASSED
tests/contracts/test_cricket_contracts.py::test_invalid_interval_negative_boundary_other_than_sentinel PASSED
tests/contracts/test_cricket_contracts.py::test_invalid_reversed_interval PASSED
tests/contracts/test_cricket_contracts.py::test_invalid_identical_interval_boundaries PASSED
tests/contracts/test_cricket_contracts.py::test_decimal_float_over_prohibited PASSED
tests/contracts/test_cricket_contracts.py::test_valid_cricket_catchup_request PASSED
tests/contracts/test_cricket_contracts.py::test_request_missing_match_id PASSED
tests/contracts/test_cricket_contracts.py::test_request_negative_innings PASSED
tests/contracts/test_cricket_contracts.py::test_request_perspective_lens_requires_target_entity PASSED
tests/contracts/test_cricket_contracts.py::test_request_unsupported_language PASSED
tests/contracts/test_cricket_contracts.py::test_request_forbids_unexpected_fields PASSED
tests/contracts/test_cricket_contracts.py::test_cricket_score_snapshot PASSED
tests/contracts/test_cricket_contracts.py::test_cricket_state_delta PASSED
tests/contracts/test_cricket_contracts.py::test_cricket_delivery_event_normalized PASSED
tests/contracts/test_evidence_contracts.py::test_valid_evidence_fact PASSED
tests/contracts/test_evidence_contracts.py::test_evidence_fact_requires_event_reference PASSED
tests/contracts/test_evidence_contracts.py::test_valid_match_evidence_packet PASSED
tests/contracts/test_explanation_contracts.py::test_valid_structured_claim PASSED
tests/contracts/test_explanation_contracts.py::test_valid_explanation_payload_verified PASSED
tests/contracts/test_explanation_contracts.py::test_explanation_payload_deterministic_fallback PASSED
tests/contracts/test_explanation_contracts.py::test_valid_cricket_catchup_response PASSED
tests/contracts/test_football_contracts.py::test_valid_football_interval PASSED
tests/contracts/test_football_contracts.py::test_invalid_football_interval_reversed PASSED
tests/contracts/test_football_contracts.py::test_invalid_football_interval_identical PASSED
tests/contracts/test_football_contracts.py::test_valid_football_catchup_request PASSED
tests/contracts/test_football_contracts.py::test_football_match_event PASSED
tests/contracts/test_football_contracts.py::test_football_schemas_do_not_accept_cricket_fields PASSED
tests/contracts/test_provenance_contracts.py::test_valid_source_provenance PASSED
tests/contracts/test_provenance_contracts.py::test_provenance_rejects_naive_timestamp PASSED
tests/contracts/test_provenance_contracts.py::test_provenance_rejects_invalid_sha256_format PASSED
tests/contracts/test_provenance_contracts.py::test_provenance_requires_meaningful_attribution PASSED
tests/contracts/test_provenance_contracts.py::test_data_sources_yaml_registry_validates PASSED

============================= 39 passed in 0.34s ==============================
```

---

## 7. Unresolved Questions & Technical Risks

1. **Cricsheet Penalty Runs Accounting:**  
   *Risk:* Rare penalty runs (5 penalty runs awarded for ball hitting helmet on ground) are recorded in Cricsheet at the delivery level. The deterministic engine in Phase 03 must credit these to team extras without crediting the batter or advancing legal balls.  
   *Resolution Plan:* Phase 03 test suite will include a specific synthetic delivery test verifying penalty runs calculation against authoritative scorecard reconciliation.
2. **Football Dataset Licensing (Phase 08):**  
   *Risk:* StatsBomb Open Data is non-commercial only. If FanCue requires commercial redistribution in future phases, a different data provider or synthetic benchmark may be required.  
   *Resolution Plan:* Football remains provisional and isolated. No football data has been ingested or committed.

---

## 8. Next Acceptance Gate: Phase 03 (Deterministic Cricket Match Engine)

Phase 02 is complete. Implementation of Phase 03 will begin only after explicit approval.

### Phase 03 Entry Gate Conditions:
1. Implement `backend/app/adapters/cricket/` (parser and normalizer for Cricsheet JSON v1.3.0).
2. Implement `backend/app/match_engine/` (pure deterministic state reconstruction and state-difference calculator).
3. Verify state reconstruction against at least 2 real Cricsheet fixtures (including pinned match `1529229`).
4. Reconcile computed match state against authoritative match scorecards.
5. Unit test coverage target: >= 90% across match engine modules.
