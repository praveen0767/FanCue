import os
import pytest
from backend.app.core.config import AppSettings

@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    # Ensure SKIP_LL... is false and no other env interferes
    monkeypatch.delenv("SKIP_LLM_IN_TESTS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield

def test_llm_live_without_key(monkeypatch):
    # No OPENAI_API_KEY set, llm_live should be False
    settings = AppSettings()
    assert settings.llm_live is False

def test_llm_live_with_key(monkeypatch):
    # Set a dummy API key, llm_live should be True
    dummy_key = "sk-testdummy123"
    monkeypatch.setenv("OPENAI_API_KEY", dummy_key)
    settings = AppSettings()
    # skip_llm defaults to False when env var not set
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
