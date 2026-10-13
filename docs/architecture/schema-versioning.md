# FanCue — Schema Versioning & Compatibility Policy

**Version:** 1.0.0  
**Phase:** 02 — Canonical Contracts & Governance  
**Status:** Normative  
**Last updated:** 2026-10-11  

---

## 1. Principles of Contract Evolution

Contracts represent binding agreements across internal components (Deterministic Engine, Qdrant Retrieval, LLM Orchestration, Verification, Web UI). In accordance with [AGENTS.md](file:///D:/FanCue/AGENTS.md), contracts must not change casually or silently.

FanCue follows strict **Semantic Versioning (SemVer 2.0.0)** for all schema definitions:
`MAJOR.MINOR.PATCH` (e.g. `1.0.0`).

---

## 2. Change Classification & Compatibility Rules

### 2.1 Backward-Compatible Additions (MINOR Version Bump: `1.0.0` -> `1.1.0`)
A schema change is backward-compatible if and only if existing producers and consumers can operate without code modifications:
- Adding a new optional field with an explicit default value.
- Adding a new enum member to a non-exhaustive internal response type, provided all consumers handle unknown members gracefully.
- Adding new standalone endpoints or response variants that do not mutate existing request paths.

**Procedure:**
1. Update Pydantic model in `backend/app/schemas/`.
2. Re-run `contracts/export_schemas.py` to regenerate JSON Schemas.
3. Update contract test suite with assertions for both with and without the new field.
4. Increment `MINOR` version.

### 2.2 Breaking Changes (MAJOR Version Bump: `1.0.0` -> `2.0.0`)
A schema change is breaking if existing consumers would fail validation or misinterpret data:
- Changing the semantics or representation of an existing field (e.g. changing `after_over` integer index to a delivery float).
- Adding a mandatory required field without a default.
- Removing or renaming an existing field.
- Changing field constraints (e.g. tightening `min_length`, removing supported enum values).
- Altering boundary inclusion/exclusion rules.

**Rule:**
> **Breaking changes to core interval boundaries, score calculation fields, or provenance records are strictly forbidden within a release phase.** Any proposed breaking change requires an Architecture Decision Record (ADR), owner review, and a new schema version URI.

### 2.3 Documentation & Patch Fixes (PATCH Version Bump: `1.0.0` -> `1.0.1`)
- Clarifications to field descriptions or schema docstrings.
- Adding non-functional metadata annotations.
- Bug fixes in schema export tooling that do not alter schema constraints.

---

## 3. Schema Artifact Distribution

- Canonical schemas are maintained in `backend/app/schemas/*.py`.
- Authoritative JSON Schema exports reside in `contracts/*.schema.json`.
- Schema URIs follow the stable format:
  `https://fancue.org/schemas/v{MAJOR}/{contract_name}.schema.json`
- Each exported schema explicitly specifies `"version": "1.0.0"` and `"$schema": "https://json-schema.org/draft/2020-12/schema"`.
