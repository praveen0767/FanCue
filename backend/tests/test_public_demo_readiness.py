"""Regression tests for public-demo readiness, fixture integrity and production CORS."""

import hashlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.cors import configure_cors
from backend.app.core import fixtures
from backend.app.core.config import AppSettings
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
    import backend.app.core.config as config
    import backend.app.core.fixtures as fixture_registry

    settings = AppSettings(
        fancue_env="production",
        retrieval_enabled=False,
        skip_llm=True,
    )
    # /readyz imports these functions locally inside the route. Patch their
    # defining modules, not backend.app.api.health (where they are not globals).
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(
        fixture_registry,
        "list_available_match_ids",
        lambda: ["1529229", "1552779"],
    )

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixtures"] == "ready"
    assert payload["qdrant"] == "bypassed"
    assert payload["llm_mode"] == "deterministic_fallback"
    assert payload["status"] == "ready"


@pytest.mark.parametrize(
    ("match_id", "expected_sha256"),
    [
        ("1529229", "8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f"),
        ("1552779", "99b2df4d4ebcaa328834ec101776a201c679b5d89b1a604241c504b0d9bb3e2b"),
    ],
)
def test_fixture_registry_hashes_match_tracked_files(match_id, expected_sha256):
    """The provenance registry and parser must verify the actual checked-in fixture bytes."""
    fixture_path = Path("data/raw") / f"{match_id}.json"
    actual = hashlib.sha256(fixture_path.read_bytes()).hexdigest()

    assert actual == expected_sha256
    provenance = fixtures._make_provenance(match_id)
    assert provenance.file_sha256 == expected_sha256

    engine = fixtures._build_engine(match_id)
    assert engine.match_id == match_id
    assert engine.provenance.file_sha256 == expected_sha256


def test_fixture_registry_rejects_unknown_fixture_id():
    """An unregistered file must not be advertised with a fake all-zero checksum."""
    with pytest.raises(ValueError, match="No verified provenance"):
        fixtures._make_provenance("9999999")


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
