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
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._base_url = base_url

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
            raise LLMProviderError(f"OpenAI HTTP error: {e.code} {e.reason}") from e
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
            raise LLMUnavailableError(f"OpenAI connection failed: {e}") from e
        except json.JSONDecodeError as e:
            raise LLMInvalidOutputError(f"OpenAI returned non-JSON output: {e}") from e
        except Exception as e:
            raise LLMProviderError(f"Unexpected OpenAI error: {e}") from e
