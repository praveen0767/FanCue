# contracts/

## Purpose

This directory holds the canonical schema definitions for all data contracts
in FanCue: request shapes, event types, evidence packets, and API responses.

Contracts are defined **before** AI or UI implementation begins (Phase 02).
No module may be implemented against an undefined or informal contract.

---

## Why Explicit Contracts

- **Isolation**: Frontend, backend, and AI orchestration can be developed
  independently once contracts are agreed.
- **Verifiability**: Contract tests can confirm that each component produces
  and consumes the correct shape.
- **Sport isolation**: Cricket and football contracts are strictly separate.
  No shared scoring formula or shared event type.
- **Evidence traceability**: Evidence-packet contracts require source provenance
  fields (`doc_id`, `source_name`, `source_url`) on every retrieved item.

---

## Planned Contract Types

| Contract | File (planned) | Phase |
|---|---|---|
| Fan request (cricket) | `contracts/cricket/fan_request.json` | Phase 02 |
| Fan request (football) | `contracts/football/fan_request.json` | Phase 02 |
| Cricket delivery event | `contracts/cricket/delivery_event.json` | Phase 02 |
| Football match event | `contracts/football/match_event.json` | Phase 02 |
| Evidence packet | `contracts/evidence_packet.json` | Phase 02 |
| Explanation response | `contracts/explanation_response.json` | Phase 02 |
| Retrieval query | `contracts/retrieval_query.json` | Phase 02 |

---

## Contract Requirements

Every contract schema must specify:

- **Explicit field types** — no untyped or `any` fields.
- **Required vs optional** — all fields must be explicitly categorised.
- **Enum constraints** — all categorical fields use defined value sets.
- **Source IDs** — event and retrieval schemas must carry source revision IDs.
- **Sport specificity** — cricket and football schemas must not share
  event-type fields; create separate schemas per sport.

---

## Validation

Contract schemas will be validated in `tests/contracts/`. These tests must
pass before AI or UI implementation begins.

---

## Current Status

**Phase 00 — Contracts directory established. No schemas defined yet.**
Schema definition begins in Phase 02.
