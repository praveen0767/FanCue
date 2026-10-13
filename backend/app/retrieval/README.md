# backend/app/retrieval/

Qdrant client interface, embedding provider, and retrieval logic.

Responsibilities:
- Maintain a swappable embedding-provider interface
- Construct Qdrant queries with mandatory sport and language filters
- Return ranked evidence chunks with provenance metadata
- Provide a retrieval evaluation harness

Qdrant is NOT an authoritative score store. This module must never be used
to look up match scores or event sequences.

Filter requirements:
- Every query must include a `sport` filter (cricket | football)
- Every query must include a `language` filter (ISO 639-1 code)
- Cross-sport result bleed is a bug, not a retrieval-quality issue

**Phase 00: Not implemented. Implementation begins Phase 04.**
