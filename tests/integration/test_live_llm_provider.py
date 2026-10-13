"""Optional live LLM provider integration test.

Enforces:
1. Skips by default unless RUN_LIVE_LLM_TESTS=true and valid non-placeholder OPENAI_API_KEY is configured.
2. Provider unit tests for offline/error handling with DeterministicFakeProvider.
3. When enabled, exercises OpenAILLMProvider against real match evidence, validating:
   - Output parses into canonical AIExplanationDraft.
   - All claims pass deterministic ClaimVerifier (or are safely rejected without crashing).
   - No fabricated scores survive into verified output.
"""

import os
import pytest

from backend.app.ai.models import AICandidateClaim, AIExplanationDraft
from backend.app.ai.provider import (
    DeterministicFakeProvider,
    GroqLLMProvider,
    LLMInvalidOutputError,
    LLMProviderError,
    LLMTimeoutError,
    LLMUnavailableError,
    OpenAILLMProvider,
)
from backend.app.core.fixtures import get_engine
from backend.app.orchestration.cricket_catchup import CricketCatchUpOrchestrator
from backend.app.schemas.cricket import CricketCatchUpRequest, CricketInterval
from backend.app.schemas.explanation import (
    ClaimType,
    FallbackReason,
    GenerationMode,
    VerificationStatus,
)
from backend.app.verification.claim_verifier import ClaimVerifier


# ---------------------------------------------------------------------------
# Offline & fake provider unit checks (always run)
# ---------------------------------------------------------------------------


def test_provider_interface_implemented():
    """Verify provider adapter interface contract."""
    fake = DeterministicFakeProvider()
    assert fake.provider_id == "deterministic_fake"
    assert fake.model_id == "fake-cricket-explainer-v1"
    assert fake.call_count == 0


def test_openai_provider_offline_validation():
    """Verify OpenAILLMProvider raises LLMUnavailableError when API key is missing/placeholder."""
    provider_no_key = OpenAILLMProvider(api_key="")
    with pytest.raises(LLMUnavailableError):
        provider_no_key.generate_explanation("prompt", "system")

    provider_placeholder = OpenAILLMProvider(api_key="REPLACE_WITH_OPENAI_KEY")
    with pytest.raises(LLMUnavailableError):
        provider_placeholder.generate_explanation("prompt", "system")


def test_groq_provider_offline_validation():
    """Verify GroqLLMProvider raises LLMUnavailableError when API key is missing/placeholder."""
    provider_no_key = GroqLLMProvider(api_key="")
    with pytest.raises(LLMUnavailableError):
        provider_no_key.generate_explanation("prompt", "system")

    provider_placeholder = GroqLLMProvider(api_key="REPLACE_WITH_GROQ_KEY")
    with pytest.raises(LLMUnavailableError):
        provider_placeholder.generate_explanation("prompt", "system")


def test_deterministic_fake_provider_simulates_timeout():
    """Verify fake provider simulates timeout properly for fallback testing."""
    provider = DeterministicFakeProvider(simulate_error=LLMTimeoutError("Timed out"))
    with pytest.raises(LLMTimeoutError):
        provider.generate_explanation("prompt", "system")


# ---------------------------------------------------------------------------
# Live LLM test (skipped by default; requires explicit authorization)
# ---------------------------------------------------------------------------

LIVE_ENABLED = (
    os.environ.get("RUN_LIVE_LLM_TESTS", "false").lower() in ("true", "1")
    and bool(os.environ.get("OPENAI_API_KEY"))
    and not os.environ.get("OPENAI_API_KEY", "").startswith("REPLACE_")
)


@pytest.mark.skipif(
    not LIVE_ENABLED,
    reason="Live LLM tests require RUN_LIVE_LLM_TESTS=true and valid OPENAI_API_KEY",
)
def test_live_openai_explanation_generation_and_verification():
    """Exercise real OpenAI provider with real cricket evidence packet and claim verifier.

    Must NOT assume the LLM output is correct; must pass through deterministic ClaimVerifier.
    """
    engine = get_engine("1529229")
    assert engine is not None

    request = CricketCatchUpRequest(
        match_id="1529229",
        interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
    )

    provider = OpenAILLMProvider()
    verifier = ClaimVerifier()

    orchestrator = CricketCatchUpOrchestrator(
        engine=engine,
        retrieval_service=None,
        llm_provider=provider,
        verifier=verifier,
        skip_llm=False,
    )

    response = orchestrator.catch_up(request)

    # Response must be contract-valid
    assert response.match.match_id == "1529229"
    assert response.explanation is not None

    # Either verified by ClaimVerifier OR fallen back deterministically
    assert response.explanation.generation_mode in (
        GenerationMode.LLM_VERIFIED,
        GenerationMode.DETERMINISTIC_FALLBACK,
    )
    if response.explanation.generation_mode == GenerationMode.LLM_VERIFIED:
        assert response.explanation.verification_status == VerificationStatus.VERIFIED
        # Ensure all surviving claims actually match deterministic facts
        for claim in response.explanation.claims:
            if claim.claim_type == ClaimType.SCORE_DELTA:
                assert claim.claimed_runs == 65
                assert claim.claimed_wickets == 0
