"""Production retrieval feature-flag and per-worker cache tests."""

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import AppSettings, get_settings
from backend.app.main import app
import backend.app.api.catchup as catchup_api


def test_retrieval_defaults_enabled_in_development(monkeypatch):
    monkeypatch.setenv("FANCUE_ENV", "development")
    monkeypatch.delenv("FANCUE_RETRIEVAL_ENABLED", raising=False)
    assert AppSettings().retrieval_enabled is True


def test_retrieval_defaults_disabled_in_production(monkeypatch):
    monkeypatch.setenv("FANCUE_ENV", "production")
    monkeypatch.delenv("FANCUE_RETRIEVAL_ENABLED", raising=False)
    assert AppSettings().retrieval_enabled is False


@pytest.mark.parametrize(("value", "expected"), [
    ("true", True),
    ("1", True),
    ("yes", True),
    ("false", False),
    ("0", False),
    ("no", False),
])
def test_retrieval_flag_explicit_value(monkeypatch, value, expected):
    monkeypatch.setenv("FANCUE_ENV", "production")
    monkeypatch.setenv("FANCUE_RETRIEVAL_ENABLED", value)
    assert AppSettings().retrieval_enabled is expected


def test_catchup_skips_retrieval_when_disabled(monkeypatch):
    """A production catch-up still returns factual fallback without initializing FastEmbed."""
    settings = AppSettings(
        fancue_env="production",
        retrieval_enabled=False,
        skip_llm=True,
    )

    def must_not_initialize_retrieval(*args, **kwargs):
        pytest.fail("Retrieval service must not be created when retrieval is disabled")

    monkeypatch.setattr(catchup_api, "_cached_retrieval_service", must_not_initialize_retrieval)
    monkeypatch.setattr(catchup_api, "_check_rate_limit", lambda *args, **kwargs: True)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.post(
                "/catchup",
                json={
                    "match_id": "1529229",
                    "interval": {
                        "innings": 0,
                        "start_after_over": 14,
                        "end_after_over": 21,
                    },
                    "language": "en",
                },
            )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["explanation"]["generation_mode"] == "deterministic_fallback"
        assert payload["explanation"]["verification_status"] in (
            "verified",
            "unverified_fallback",
        )
        assert payload["evidence_packet"]["retrieved_knowledge_ids"] == []
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_retrieval_service_is_cached_per_worker_config(monkeypatch):
    """Repeated requests reuse the same retrieval service and embedding-provider object."""
    import ingestion.knowledge.qdrant_store as qdrant_module
    import ingestion.knowledge.retrieve as retrieval_module

    class FakeStore:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRetrievalService:
        def __init__(self, collection_name, store):
            self.collection_name = collection_name
            self.store = store

    monkeypatch.setattr(qdrant_module, "QdrantStore", FakeStore)
    monkeypatch.setattr(retrieval_module, "RetrievalService", FakeRetrievalService)
    catchup_api._cached_retrieval_service.cache_clear()
    try:
        first = catchup_api._cached_retrieval_service(
            "fancue_cricket_knowledge_v1", "localhost", 6333,
            "https://qdrant.example", "test-only-key", True,
        )
        second = catchup_api._cached_retrieval_service(
            "fancue_cricket_knowledge_v1", "localhost", 6333,
            "https://qdrant.example", "test-only-key", True,
        )
        assert first is second
        assert isinstance(first.store, FakeStore)
        assert first.store.kwargs["allow_local_fallback"] is False
    finally:
        catchup_api._cached_retrieval_service.cache_clear()
