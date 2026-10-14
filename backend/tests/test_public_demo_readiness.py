"""Regression tests for public-demo readiness and deployment CORS contract."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.cors import configure_cors
from backend.app.core.config import AppSettings, get_settings
from backend.app.main import app


def test_healthz_is_process_liveness_only():
    """The liveness endpoint is cheap and does not claim dependency readiness."""
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "fancue-api"


def test_readyz_reports_fixture_and_retrieval_mode_without_external_calls(monkeypatch):
    """Readiness should make the no-Qdrant deployment mode explicit."""
    from backend.app.core import fixtures

    monkeypatch.setattr(fixtures, "list_available_match_ids", lambda: ["match-a", "match-b"])
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


def test_production_cors_allows_configured_origin_only():
    """Exact Vercel origin gets preflight headers; an arbitrary origin does not."""
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
    assert "POST" in accepted.headers.get("access-control-allow-methods", "")
    assert rejected.headers.get("access-control-allow-origin") is None
