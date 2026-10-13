# backend/app/domain/

Sport-agnostic domain types and interfaces.

Contains pure Python types and abstract interfaces shared across sport adapters.
No framework imports (no FastAPI, no Pydantic v2 validators) allowed here —
this layer must be testable with plain `pytest` and zero external dependencies.

Examples of what lives here:
- `SportAdapter` abstract base class
- `MatchInterval` value object
- `StateSnapshot` and `StateDiff` types
- `EvidencePacket` type

**Phase 00: Not implemented. Types defined in Phase 02 (contracts).**
