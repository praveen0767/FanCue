# backend/app/context/

Evidence packet assembler.

Combines authoritative match engine output with retrieval results from Qdrant
to produce a typed `EvidencePacket` that is passed to the explanation module.

The context planner:
- Selects the most relevant retrieved chunks for the interval events
- Deduplicates and ranks evidence items
- Attaches provenance metadata to every item
- Ensures no evidence item enters the packet without a `doc_id` and `source_url`

The context planner does NOT:
- Call the match engine directly (receives its output as a parameter)
- Call the LLM
- Modify retrieved chunks

**Phase 00: Not implemented. Implementation begins Phase 05.**
