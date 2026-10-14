"""Unit tests for GroqLLMProvider adapter, provider selection, and orchestration fallback.

All external network calls are mocked with unittest.mock; no real API keys or
network requests are used.
"""

import json
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request
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
    create_llm_provider,
)
from backend.app.core.config import AppSettings
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
# Provider Interface & Offline Checks
# ---------------------------------------------------------------------------


def test_groq_provider_interface():
    """Verify GroqLLMProvider exposes correct identifiers."""
    provider = GroqLLMProvider(api_key="gsk-test-key-123", model="openai/gpt-oss-20b")
    assert provider.provider_id == "groq"
    assert provider.model_id == "openai/gpt-oss-20b"


def test_groq_provider_offline_validation():
    """Verify GroqLLMProvider raises LLMUnavailableError when key is missing or placeholder."""
    provider_no_key = GroqLLMProvider(api_key="")
    with pytest.raises(LLMUnavailableError) as exc_info:
        provider_no_key.generate_explanation("prompt", "system")
    assert "Groq API key not configured" in str(exc_info.value)

    provider_placeholder = GroqLLMProvider(api_key="REPLACE_WITH_YOUR_GROQ_API_KEY")
    with pytest.raises(LLMUnavailableError) as exc_info:
        provider_placeholder.generate_explanation("prompt", "system")
    assert "contains placeholder" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Mocked Request Construction & Successful Parsing
# ---------------------------------------------------------------------------


def test_groq_provider_request_format_and_parsing():
    """Verify correct URL, headers, JSON body and response parsing."""
    valid_draft_json = {
        "summary": "India scored 65 runs in 7 overs without losing any wickets.",
        "claims": [
            {
                "claim_id": "c1",
                "claim_type": "score_delta",
                "text": "India scored 65 runs in 7 overs without losing any wickets.",
                "cited_fact_ids": ["fact_interval_delta"],
                "claimed_runs": 65,
                "claimed_wickets": 0,
                "claimed_overs": 7,
            }
        ],
    }
    mock_resp_body = {
        "id": "chatcmpl-mock-groq-123",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(valid_draft_json),
                },
                "finish_reason": "stop",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_body).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    provider = GroqLLMProvider(
        api_key="gsk-test-secret-456",
        model="openai/gpt-oss-20b",
        base_url="https://api.groq.com/openai/v1",
    )

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        draft = provider.generate_explanation(
            prompt="User prompt here",
            system_prompt="System prompt here",
            timeout_seconds=25.0,
        )

        assert mock_urlopen.call_count == 1
        call_req, = mock_urlopen.call_args[0]
        call_timeout = mock_urlopen.call_args[1]["timeout"]

        assert call_req.full_url == "https://api.groq.com/openai/v1/chat/completions"
        assert call_req.headers["Authorization"] == "Bearer gsk-test-secret-456"
        assert call_req.headers["Content-type"] == "application/json"
        assert call_timeout == 25.0

        sent_body = json.loads(call_req.data.decode("utf-8"))
        assert sent_body["model"] == "openai/gpt-oss-20b"
        assert sent_body["response_format"] == {"type": "json_object"}
        assert sent_body["include_reasoning"] is False
        assert sent_body["messages"][0]["content"] == "System prompt here"
        assert sent_body["messages"][1]["content"] == "User prompt here"

        assert draft.summary == valid_draft_json["summary"]
        assert len(draft.claims) == 1
        assert draft.claims[0].claimed_runs == 65


# ---------------------------------------------------------------------------
# Error Handling & Status Code Categorization
# ---------------------------------------------------------------------------


def test_groq_provider_http_401():
    """Verify HTTP 401 translates to sanitized authentication error."""
    provider = GroqLLMProvider(api_key="gsk-invalid-key")
    err = urllib.error.HTTPError(
        url="https://api.groq.com/openai/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=MagicMock(read=lambda: b'{"error": {"type": "invalid_api_key"}}'),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_explanation("prompt", "system")
        assert "Groq authentication failed (HTTP 401)" in str(exc_info.value)


def test_groq_provider_http_400_has_safe_diagnostic():
    """A bad request gives a safe category without exposing request credentials."""
    provider = GroqLLMProvider(api_key="gsk-test-secret")
    err = urllib.error.HTTPError(
        url="https://api.groq.com/openai/v1/chat/completions",
        code=400,
        msg="Bad Request",
        hdrs={},
        fp=MagicMock(read=lambda: b'{"error": {"type": "invalid_request_error", "code": "json_mode"}}'),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_explanation("prompt", "system")
    assert "HTTP 400, json_mode" in str(exc_info.value)
    assert "gsk-test-secret" not in str(exc_info.value)


def test_groq_provider_http_429_quota():
    """Verify HTTP 429 with insufficient_quota is categorized distinctly."""
    provider = GroqLLMProvider(api_key="gsk-quota-exhausted")
    err = urllib.error.HTTPError(
        url="https://api.groq.com/openai/v1/chat/completions",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=MagicMock(read=lambda: b'{"error": {"type": "insufficient_quota", "code": "insufficient_quota"}}'),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_explanation("prompt", "system")
        assert "Groq quota exhausted (insufficient_quota) (HTTP 429)" in str(exc_info.value)


def test_groq_provider_http_500():
    """Verify HTTP 500 raises LLMUnavailableError."""
    provider = GroqLLMProvider(api_key="gsk-valid")
    err = urllib.error.HTTPError(
        url="https://api.groq.com/openai/v1/chat/completions",
        code=503,
        msg="Service Unavailable",
        hdrs={},
        fp=MagicMock(read=lambda: b'Service unavailable'),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(LLMUnavailableError) as exc_info:
            provider.generate_explanation("prompt", "system")
        assert "Groq upstream service error (HTTP 503)" in str(exc_info.value)


def test_groq_provider_timeout():
    """Verify network timeout raises LLMTimeoutError."""
    provider = GroqLLMProvider(api_key="gsk-valid")
    err = urllib.error.URLError("timed out")

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(LLMTimeoutError) as exc_info:
            provider.generate_explanation("prompt", "system")
        assert "Groq request timed out" in str(exc_info.value)


def test_groq_provider_malformed_json():
    """Verify non-JSON response raises LLMInvalidOutputError."""
    mock_resp_body = {
        "choices": [{"message": {"content": "Not a valid JSON object"}}]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_body).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    provider = GroqLLMProvider(api_key="gsk-valid")
    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(LLMInvalidOutputError) as exc_info:
            provider.generate_explanation("prompt", "system")
        assert "Groq returned non-JSON output" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Factory Selection & Configuration Switching
# ---------------------------------------------------------------------------


def test_factory_selects_groq_by_default_when_configured(monkeypatch):
    """When GROQ_API_KEY is configured and LLM_PROVIDER=groq, factory builds GroqLLMProvider."""
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-mock-key-abc")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    monkeypatch.delenv("SKIP_LLM_IN_TESTS", raising=False)

    settings = AppSettings()
    assert settings.active_llm_provider == "groq"
    assert settings.llm_live is True

    provider = create_llm_provider(settings)
    assert isinstance(provider, GroqLLMProvider)
    assert provider.provider_id == "groq"
    assert provider.model_id == "openai/gpt-oss-20b"


def test_factory_switches_to_openai_with_env_var(monkeypatch):
    """When LLM_PROVIDER=openai and OPENAI_API_KEY is set, factory builds OpenAILLMProvider."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key-xyz")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-mock-key-abc")
    monkeypatch.delenv("SKIP_LLM_IN_TESTS", raising=False)

    settings = AppSettings()
    assert settings.active_llm_provider == "openai"
    assert settings.llm_live is True

    provider = create_llm_provider(settings)
    assert isinstance(provider, OpenAILLMProvider)
    assert provider.provider_id == "openai"


def test_factory_returns_deterministic_fake_when_offline(monkeypatch):
    """When no keys are configured, factory safely returns DeterministicFakeProvider."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = AppSettings()
    assert settings.llm_live is False

    provider = create_llm_provider(settings)
    assert isinstance(provider, DeterministicFakeProvider)


# ---------------------------------------------------------------------------
# Orchestration Integration with Groq & Claim Verification
# ---------------------------------------------------------------------------


def test_orchestrator_with_groq_verified_explanation():
    """Verify that a valid Groq draft passes ClaimVerifier and produces verified response."""
    engine = get_engine("1529229")
    assert engine is not None

    request = CricketCatchUpRequest(
        match_id="1529229",
        interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
    )

    groq_provider = GroqLLMProvider(api_key="gsk-mock-key", model="openai/gpt-oss-20b")
    # Mock generate_explanation to return a well-grounded draft using DeterministicFakeProvider's logic
    fake_generator = DeterministicFakeProvider()
    with patch.object(
        groq_provider,
        "generate_explanation",
        side_effect=lambda prompt, system_prompt, **kwargs: fake_generator.generate_explanation(prompt, system_prompt),
    ):
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine,
            retrieval_service=None,
            llm_provider=groq_provider,
            verifier=ClaimVerifier(),
            skip_llm=False,
        )

        response = orchestrator.catch_up(request)
        assert response.explanation.generation_mode == GenerationMode.LLM_VERIFIED
        assert response.explanation.verification_status == VerificationStatus.VERIFIED
        assert response.explanation.fallback_reason == FallbackReason.NONE
        assert any("groq" in w.lower() for w in response.warnings)
        assert any("openai/gpt-oss-20b" in w.lower() for w in response.warnings)


def test_orchestrator_with_groq_failure_engages_deterministic_fallback():
    """Verify that a Groq provider error triggers clean deterministic fallback without leaking keys."""
    engine = get_engine("1529229")
    assert engine is not None

    request = CricketCatchUpRequest(
        match_id="1529229",
        interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
    )

    failing_provider = DeterministicFakeProvider(
        simulate_error=LLMProviderError("Groq rate limit exceeded (HTTP 429). Please wait before retrying.")
    )

    orchestrator = CricketCatchUpOrchestrator(
        engine=engine,
        retrieval_service=None,
        llm_provider=failing_provider,
        verifier=ClaimVerifier(),
        skip_llm=False,
    )

    response = orchestrator.catch_up(request)
    assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
    assert response.explanation.fallback_reason == FallbackReason.LLM_ERROR
    assert response.explanation.summary.startswith("The score moved from")
    assert any("Groq rate limit exceeded" in w for w in response.warnings)
