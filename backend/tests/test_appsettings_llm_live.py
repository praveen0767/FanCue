import os
import pytest
from backend.app.core.config import AppSettings

@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    # Ensure SKIP_LLM_IN_TESTS is false and no other env interferes
    monkeypatch.delenv("SKIP_LLM_IN_TESTS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    yield

def test_llm_live_without_key(monkeypatch):
    # Neither key set, llm_live should be False
    settings = AppSettings()
    assert settings.llm_live is False

def test_llm_live_with_openai_key(monkeypatch):
    # Set a dummy OpenAI API key, llm_live should be True
    dummy_key = "sk-testdummy123"
    monkeypatch.setenv("OPENAI_API_KEY", dummy_key)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    settings = AppSettings()
    assert settings.skip_llm is False
    assert settings.llm_live is True
    assert settings.active_llm_provider == "openai"

def test_llm_live_with_groq_key(monkeypatch):
    # Set a dummy Groq API key, llm_live should be True
    dummy_key = "gsk-testdummy456"
    monkeypatch.setenv("GROQ_API_KEY", dummy_key)
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    settings = AppSettings()
    assert settings.skip_llm is False
    assert settings.llm_live is True
    assert settings.active_llm_provider == "groq"
    assert settings.active_llm_model == "openai/gpt-oss-20b"

def test_llm_live_with_key(monkeypatch):
    # Backward compatibility test: OpenAI key auto-detected when provider not set
    dummy_key = "sk-testdummy123"
    monkeypatch.setenv("OPENAI_API_KEY", dummy_key)
    settings = AppSettings()
    assert settings.skip_llm is False
    assert settings.llm_live is True



def test_cricket_data_live_property(monkeypatch):
    monkeypatch.delenv("CRICKET_DATA_API_KEY", raising=False)
    s_none = AppSettings()
    assert s_none.cricket_data_live is False

    monkeypatch.setenv("CRICKET_DATA_API_KEY", "REPLACE_WITH_YOUR_KEY")
    s_placeholder = AppSettings()
    assert s_placeholder.cricket_data_live is False

    monkeypatch.setenv("CRICKET_DATA_API_KEY", "valid-test-key-36chars")
    s_valid = AppSettings()
    assert s_valid.cricket_data_live is True
