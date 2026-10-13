# backend/app/explanation/

LLM orchestration — prompt construction, API call, structured response parsing.

Responsibilities:
- Accept an `EvidencePacket` from the context planner
- Construct a bounded prompt using the evidence packet (no free-form LLM access to external data)
- Call the configured LLM provider via a swappable provider interface
- Parse the LLM response into a typed `ExplanationResponse`
- Never call the match engine or Qdrant directly

The explanation module must:
- Respect the `LLM_TIMEOUT_SECONDS` configuration
- Propagate timeouts and API errors to the verification layer (not swallow them)
- Support `SKIP_LLM_IN_TESTS=true` to return a deterministic stub in tests

**Phase 00: Not implemented. Implementation begins Phase 05.**
