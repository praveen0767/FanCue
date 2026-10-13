# tests/contracts/

Contract validation tests for all FanCue data schemas.

These tests confirm that the Pydantic schema implementations in
`backend/app/schemas/` match the canonical contracts defined in `contracts/`.

Test structure:
- `cricket/` — cricket request, event, and response contract tests
- `football/` — football contract tests (Phase 08)
- `retrieval/` — retrieval query and evidence-packet contract tests

All contract tests must pass before AI or UI implementation begins (Phase 05 gate).

**Phase 00: No tests yet. Tests created in Phase 02.**
