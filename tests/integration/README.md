# tests/integration/

End-to-end integration tests covering the full fan request pipeline.

These tests require:
- A running Qdrant instance (local Docker or test container)
- A loaded knowledge corpus (at least minimal)
- The complete backend pipeline (engine + retrieval + explanation + verification)

LLM calls are bypassed using `SKIP_LLM_IN_TESTS=true` in all integration tests
unless explicitly testing the LLM integration path.

**Phase 00: No integration tests yet. Created in Phase 05.**
