# backend/app/schemas/

Shared Pydantic models for all API requests, events, evidence packets, and responses.

All schema definitions must be explicit:
- No `Any` field types without a documented justification
- No optional fields that are semantically required
- Enum types for all categorical fields (sport, language, event_type)
- Source revision IDs on all event schemas

Schemas are the implementation of the contracts defined in `contracts/`.
Any divergence between `contracts/` and `schemas/` is a bug.

**Phase 00: Not implemented. Schemas defined in Phase 02.**
