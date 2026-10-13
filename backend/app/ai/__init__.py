"""AI provider interfaces, prompt templates, and models."""

from backend.app.ai.models import AICandidateClaim, AIExplanationDraft
from backend.app.ai.prompt_templates import SYSTEM_PROMPT, build_explanation_prompt
from backend.app.ai.provider import (
    DeterministicFakeProvider,
    LLMInvalidOutputError,
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMUnavailableError,
    OpenAILLMProvider,
)

__all__ = [
    "AICandidateClaim",
    "AIExplanationDraft",
    "SYSTEM_PROMPT",
    "build_explanation_prompt",
    "LLMProvider",
    "DeterministicFakeProvider",
    "OpenAILLMProvider",
    "LLMProviderError",
    "LLMTimeoutError",
    "LLMUnavailableError",
    "LLMInvalidOutputError",
]
