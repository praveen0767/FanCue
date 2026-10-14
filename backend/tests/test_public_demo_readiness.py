"""Regression tests for the public-demo readiness contract."""

from fastapi.testclient import TestClient

from backend.app.core.config import AppSettings, get_settings
from backend.app.main import app


def test_healthz_is_process_liveness_only():
    """The liveness endpoint must stay cheap and avoid dependency claims."""
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "fancue-api"


def test_readyz_reports_fixtures_and_disabled_retrieval_without_external_calls(monkeypatch):
    """Readiness should make the no-Qdrant deployment mode explicit."""
    from backend.app.core import fixtures

    monkeypatch.setattr(fixtures, "list_available_match_ids", lambda: ["match-a", "match-b"])
    monkeypatch.setenv("FANCUE_ENV", "production")
    monkeypatch.setenv("FANCUE_RETRIEVAL_ENABLED", "false")
    settings = AppSettings(
        fancue_env="production",
        retrieval_enabled=False,
        skip_llm=True,
    )

    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.get("/readyz")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixtures"] == "ready"
    assert payload["qdrant"] == "bypassed"
    assert payload["llm_mode"] == "deterministic_fallback"
    assert payload["status"] == "ready"


def test_production_cors_allows_only_configured_frontend_origin(monkeypatch):
    """Check exact origin matching and ensure arbitrary web origins are not allowed."""
    from backend.app.api.cors import configure_cors
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    settings = AppSettings(
        fancue_env="production",
        allowed_origins=["https://fan-cue.vercel.app"],
    )
    cors_app = FastAPI()
    configure_cors(cors_app, settings)

    @cors_app.post("/catchup")
    def catchup():
        return {"ok": True}

    with TestClient(cors_app) as client:
        accepted = client.options(
            "/catchup",
            headers={
                "Origin": "https://fan-cue.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        rejected = client.options(
            "/catchup",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert accepted.status_code == 200
    assert accepted.headers.get("access-control-allow-origin") == "https://fan-cue.vercel.app"
    assert rejected.headers.get("access-control-allow-origin") is None
