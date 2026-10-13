# backend/app/verification/

Claim verification against authoritative facts, and deterministic fallback generator.

Responsibilities:
- Receive: authoritative engine output (read-only) + LLM explanation response
- Verify:
    1. All score/event claims in the explanation match the engine output
    2. All cited `doc_id` values exist in the evidence packet
    3. No statistics appear that were not present in the evidence packet
- On verification failure (or LLM unavailability): produce a deterministic fallback
- Label fallback responses clearly as non-AI-generated

The verifier must:
- Be entirely rules-based Python (no LLM calls in the verification step)
- Have tests that confirm it correctly blocks a fabricated claim
- Have tests that confirm fallback output is useful and complete

**Phase 00: Not implemented. Implementation begins Phase 05.**
