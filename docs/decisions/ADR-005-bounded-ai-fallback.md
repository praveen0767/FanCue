# ADR-005 — Bounded AI with Evidence Validation and Deterministic Fallback

**Status:** Accepted
**Date:** 2026-10-11
**Phase:** 00

---

## Context

FanCue uses a language model to produce readable explanations. LLMs can
hallucinate, produce unverifiable claims, or become unavailable. The fan
experience must not depend entirely on LLM availability or correctness.

---

## Decision

The LLM is bounded by an evidence packet (authoritative engine output +
retrieved Qdrant chunks). After generation, a **verification step** checks
the LLM output against authoritative facts. If verification fails or the LLM
is unavailable, the system returns a **deterministic fallback** — a structured
summary built from the engine output and evidence packet without LLM prose.

The system must be usefully functional without any LLM API key configured.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| Trust LLM output unconditionally | Hallucination risk on precise scores and statistics is unacceptable for a fact-dependent product. |
| Retry LLM on failure | Retries mask systematic failure and increase latency. A deterministic fallback is faster and more reliable. |
| Use LLM to verify its own output | Self-verification is not independent. A separate, rules-based verification step is required. |
| Show error page on LLM failure | Unacceptable fan experience. The fan asked a question and deserves a useful answer regardless of AI status. |

---

## Consequences

- Every LLM output must be checked: score claims vs. engine output, cited
  sources vs. evidence packet, absence of fabricated statistics.
- Verification is rules-based Python code, not another LLM call.
- The deterministic fallback must be designed and tested before the LLM
  integration is built (Phase 05).
- The fallback response must clearly label itself as non-AI-generated.
- LLM provider is configurable via environment variable. Multiple providers
  must be swappable behind a common interface.
- Test suite must include scenarios where the LLM is unavailable, times out,
  and produces a claim that fails verification.

---

## Conditions for Revisiting

- If a sufficiently capable LLM becomes available with contractually guaranteed
  accuracy on sports statistics (unlikely near-term).
- If verification false-positive rates (blocking correct outputs) become
  measurably high enough to degrade the fan experience — at that point,
  the verification rules require refinement, not removal.
