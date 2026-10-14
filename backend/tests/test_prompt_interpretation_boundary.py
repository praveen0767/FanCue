"""Tests that the explanation prompt avoids interpretations the verifier cannot assess."""

from backend.app.ai.prompt_templates import PROMPT_VERSION, SYSTEM_PROMPT


def test_prompt_version_is_bumped_for_interpretation_boundary():
    assert PROMPT_VERSION == "1.1.0"


def test_prompt_forbids_unverifiable_turning_point_and_pressure_language():
    """The LLM must stick to observable evidence instead of implying causal meaning."""
    prompt = SYSTEM_PROMPT.lower()

    assert "turning point" in prompt
    assert "pressure built" in prompt
    assert "momentum shifted" in prompt
    assert "the verifier checks numerical claims, names, and citations" in prompt
    assert "does not determine whether these interpretations are justified" in prompt
    assert "describe observable evidence only" in prompt
    assert "do not infer tactical intent" in prompt
