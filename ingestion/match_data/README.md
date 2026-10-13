# ingestion/match_data/

Match data ingestion and normalization pipeline.

Responsibilities:
- Download and validate match event data from licensed sources (Cricsheet, StatsBomb)
- Normalize events into the FanCue canonical event format
- Validate data against the canonical event schema contracts
- Store normalized data in `data/processed/` (gitignored)
- Record provenance in `data/sources.yml`

Requirements:
- No data may be ingested without a reviewed license entry in `data/sources.yml`
- Normalization must be fully tested (unit tests, not just smoke tests)
- Ingestion must be idempotent

**Phase 00: Not implemented. Implementation begins Phase 03.**
