"""Provider-neutral LLM adapter interface, deterministic mock provider, and live client wrapper."""

from abc import ABC, abstractmethod
import json
import os
from typing import Any, Callable, Dict, Optional

from backend.app.ai.models import AICandidateClaim, AIExplanationDraft
from backend.app.schemas.explanation import ClaimType


class LLMProviderError(Exception):
    """Base error for LLM provider failures."""
    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when LLM call exceeds configured timeout."""
    pass


class LLMUnavailableError(LLMProviderError):
    """Raised when LLM service is offline or unreachable."""
    pass


class LLMInvalidOutputError(LLMProviderError):
    """Raised when LLM returns output that cannot be parsed into AIExplanationDraft."""
    pass


class LLMProvider(ABC):
    """Abstract interface for LLM explanation generation."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Provider name identifier."""
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Model name identifier."""
        pass

    @abstractmethod
    def generate_explanation(
        self,
        prompt: str,
        system_prompt: str,
        timeout_seconds: float = 30.0,
    ) -> AIExplanationDraft:
        """Generate structured explanation draft adhering to AIExplanationDraft schema."""
        pass


class DeterministicFakeProvider(LLMProvider):
    """Deterministic, offline fake provider for reproducible testing and verification.
    
    Can be configured to return valid grounded drafts, simulate hallucinations (fabricated
    scores, altered players, fake fact IDs), return malformed JSON, or simulate timeouts.
    """

    def __init__(
        self,
        preset_draft: Optional[AIExplanationDraft] = None,
        simulate_error: Optional[Exception] = None,
        generator_func: Optional[Callable[[str], AIExplanationDraft]] = None,
    ) -> None:
        self._preset_draft = preset_draft
        self._simulate_error = simulate_error
        self._generator_func = generator_func
        self._call_count = 0

    @property
    def provider_id(self) -> str:
        return "deterministic_fake"

    @property
    def model_id(self) -> str:
        return "fake-cricket-explainer-v1"

    @property
    def call_count(self) -> int:
        return self._call_count

    def generate_explanation(
        self,
        prompt: str,
        system_prompt: str,
        timeout_seconds: float = 30.0,
    ) -> AIExplanationDraft:
        self._call_count += 1

        if self._simulate_error is not None:
            raise self._simulate_error

        if self._preset_draft is not None:
            return self._preset_draft

        if self._generator_func is not None:
            return self._generator_func(prompt)

        # Default: parse the packet from prompt JSON to produce a grounded valid draft
        try:
            # Extract JSON block from prompt
            start_idx = prompt.find("EVIDENCE PACKET:\n")
            if start_idx != -1:
                json_str = prompt[start_idx + len("EVIDENCE PACKET:\n"): prompt.rfind("\n\nRespond with")]
                packet_data = json.loads(json_str)
                delta = packet_data["authoritative_state_delta"]
                facts = packet_data["authoritative_facts"]
                passages = packet_data.get("untrusted_context_passages", [])

                delta_fact_id = facts[0]["fact_id"] if facts else "fact_delta"
                knowledge_id = passages[0]["doc_id"] if passages else ""

                claims = [
                    AICandidateClaim(
                        claim_id="claim_1",
                        claim_type=ClaimType.SCORE_DELTA,
                        text=f"During the interval, {delta['runs_added']} runs were added for the loss of {delta['wickets_lost']} wickets in {delta['completed_overs_delta']} overs.",
                        cited_fact_ids=[delta_fact_id],
                        claimed_runs=delta["runs_added"],
                        claimed_wickets=delta["wickets_lost"],
                        claimed_overs=delta["completed_overs_delta"],
                    )
                ]

                # If there are key event facts (e.g. wickets, sixes), cite them
                for f in facts[1:3]:
                    f_id = f["fact_id"]
                    f_desc = f["description"]
                    f_data = f.get("data", {})
                    player = f_data.get("player_out") or f_data.get("bowler")
                    claims.append(
                        AICandidateClaim(
                            claim_id=f"claim_{len(claims) + 1}",
                            claim_type=ClaimType.EVENT_CHRONOLOGY,
                            text=f_desc,
                            cited_fact_ids=[f_id],
                            claimed_player=player,
                        )
                    )

                # Contextual fact if passage available
                if knowledge_id:
                    claims.append(
                        AICandidateClaim(
                            claim_id=f"claim_{len(claims) + 1}",
                            claim_type=ClaimType.TACTICAL_CONTEXT,
                            text="The interval progression altered the scoring momentum under standard match conditions.",
                            cited_knowledge_ids=[knowledge_id],
                        )
                    )

                summary = (
                    f"In this interval, {delta['runs_added']} runs were scored and {delta['wickets_lost']} wickets fell "
                    f"over {delta['completed_overs_delta']} overs at a run rate of {delta['interval_run_rate']:.2f} rpo."
                )

                return AIExplanationDraft(
                    summary=summary,
                    claims=claims,
                )
        except Exception as e:
            raise LLMInvalidOutputError(f"Failed to generate fake explanation draft: {e}") from e

        # Fallback basic draft
        return AIExplanationDraft(
            summary="Standard interval explanation summary.",
            claims=[
                AICandidateClaim(
                    claim_id="claim_1",
                    claim_type=ClaimType.META,
                    text="Interval completed with recorded state change.",
                    cited_fact_ids=[],
                )
            ],
        )


class OpenAILLMProvider(LLMProvider):
    """Live OpenAI API provider adapter with structured output schema enforcement.
    
    Uses python requests/urllib without heavy third-party SDK dependencies.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout_seconds = timeout_seconds

    @property
    def provider_id(self) -> str:
        return "openai"

    @property
    def model_id(self) -> str:
        return self._model

    def generate_explanation(
        self,
        prompt: str,
        system_prompt: str,
        timeout_seconds: float = 30.0,
    ) -> AIExplanationDraft:
        if not self._api_key or self._api_key.startswith("REPLACE_"):
            raise LLMUnavailableError("OpenAI API key not configured or contains placeholder.")

        import urllib.request
        import urllib.error

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        # Request structured JSON
        body = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                content = resp_data["choices"][0]["message"]["content"]
                draft_dict = json.loads(content)
                return AIExplanationDraft.model_validate(draft_dict)
        except urllib.error.HTTPError as e:
            status = e.code
            # Safely read a sanitized error category from the provider body.
            # We only extract the 'type' field (not the full message or any key material).
            safe_body_type = ""
            try:
                body_bytes = e.read()
                body_json = json.loads(body_bytes.decode("utf-8", errors="replace"))
                safe_body_type = body_json.get("error", {}).get("type", "") or ""
            except Exception:
                pass

            if status == 401:
                raise LLMProviderError(
                    f"OpenAI authentication failed (HTTP 401). "
                    f"Check that OPENAI_API_KEY is valid and not revoked."
                ) from e
            elif status == 403:
                raise LLMProviderError(
                    f"OpenAI access denied (HTTP 403). "
                    f"The API key may lack permission for this model."
                ) from e
            elif status == 404:
                raise LLMProviderError(
                    f"OpenAI endpoint or model not found (HTTP 404). "
                    f"Model '{self._model}' may not be accessible on this account."
                ) from e
            elif status == 429:
                quota_or_rate = (
                    "quota exhausted (insufficient_quota)"
                    if "insufficient_quota" in safe_body_type
                    else "rate limit exceeded"
                )
                raise LLMProviderError(
                    f"OpenAI {quota_or_rate} (HTTP 429). "
                    f"Add credits or reduce request frequency."
                ) from e
            elif 500 <= status < 600:
                raise LLMUnavailableError(
                    f"OpenAI upstream service error (HTTP {status}). Retry later."
                ) from e
            else:
                raise LLMProviderError(f"OpenAI HTTP error: {status}") from e
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
            raise LLMUnavailableError(f"OpenAI connection failed: {e}") from e
        except json.JSONDecodeError as e:
            raise LLMInvalidOutputError(f"OpenAI returned non-JSON output: {e}") from e
        except Exception as e:
            if isinstance(e, LLMProviderError):
                raise
            raise LLMProviderError(f"Unexpected OpenAI error: {e}") from e


class GroqLLMProvider(LLMProvider):
    """Live Groq API provider adapter with structured JSON schema enforcement.

    Uses Groq's OpenAI-compatible endpoint (https://api.groq.com/openai/v1)
    via standard urllib without heavy external SDK dependencies.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-oss-20b",
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY", "")
        self._model = model
        self._base_url = (base_url or "https://api.groq.com/openai/v1").rstrip("/")
        self._timeout_seconds = timeout_seconds

    @property
    def provider_id(self) -> str:
        return "groq"

    @property
    def model_id(self) -> str:
        return self._model

    def generate_explanation(
        self,
        prompt: str,
        system_prompt: str,
        timeout_seconds: Optional[float] = None,
    ) -> AIExplanationDraft:
        if not self._api_key or self._api_key.startswith("REPLACE_"):
            raise LLMUnavailableError("Groq API key not configured or contains placeholder.")

        import urllib.request
        import urllib.error

        effective_timeout = timeout_seconds if timeout_seconds is not None else self._timeout_seconds

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "FanCue/0.9.0",
        }

        # Request structured JSON
        body = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                content = resp_data["choices"][0]["message"]["content"]
                draft_dict = json.loads(content)
                return AIExplanationDraft.model_validate(draft_dict)
        except urllib.error.HTTPError as e:
            status = e.code
            safe_body_type = ""
            safe_error_code = ""
            try:
                body_bytes = e.read()
                body_json = json.loads(body_bytes.decode("utf-8", errors="replace"))
                err_obj = body_json.get("error", {})
                safe_body_type = err_obj.get("type", "") or ""
                safe_error_code = err_obj.get("code", "") or ""
            except Exception:
                pass

            if status == 401:
                raise LLMProviderError(
                    f"Groq authentication failed (HTTP 401). "
                    f"Check that GROQ_API_KEY is valid and not revoked."
                ) from e
            elif status == 403:
                raise LLMProviderError(
                    f"Groq access denied (HTTP 403). "
                    f"The API key may lack permission for model '{self._model}'."
                ) from e
            elif status == 404:
                raise LLMProviderError(
                    f"Groq endpoint or model not found (HTTP 404). "
                    f"Model '{self._model}' may not be supported on Groq."
                ) from e
            elif status == 429:
                quota_or_rate = (
                    "quota exhausted (insufficient_quota)"
                    if "insufficient_quota" in safe_body_type or "insufficient_quota" in safe_error_code
                    else "rate limit exceeded"
                )
                raise LLMProviderError(
                    f"Groq {quota_or_rate} (HTTP 429). "
                    f"Please wait before retrying or check account rate limits."
                ) from e
            elif 500 <= status < 600:
                raise LLMUnavailableError(
                    f"Groq upstream service error (HTTP {status}). Retry later."
                ) from e
            else:
                raise LLMProviderError(f"Groq HTTP error: {status}") from e
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                raise LLMTimeoutError(f"Groq request timed out: {e}") from e
            raise LLMUnavailableError(f"Groq connection failed: {e}") from e
        except json.JSONDecodeError as e:
            raise LLMInvalidOutputError(f"Groq returned non-JSON output: {e}") from e
        except Exception as e:
            if isinstance(e, LLMProviderError):
                raise
            raise LLMProviderError(f"Unexpected Groq error: {e}") from e


def create_llm_provider(settings: Optional[Any] = None) -> LLMProvider:
    """Factory creating the configured LLMProvider based on application settings.

    Returns GroqLLMProvider when LLM_PROVIDER=groq and configured,
    OpenAILLMProvider when LLM_PROVIDER=openai and configured,
    or DeterministicFakeProvider when offline, keys are missing, or in test mode.
    """
    if settings is None:
        from backend.app.core.config import get_settings
        settings = get_settings()

    if not settings.llm_live:
        return DeterministicFakeProvider()

    provider_name = settings.active_llm_provider
    if provider_name == "groq":
        return GroqLLMProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            base_url=settings.groq_base_url,
            timeout_seconds=settings.groq_timeout_seconds,
        )
    elif provider_name == "openai":
        return OpenAILLMProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    return DeterministicFakeProvider()

