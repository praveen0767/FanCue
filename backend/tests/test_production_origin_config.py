"""Regression tests for exact production CORS origin configuration."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.cors import configure_cors
from backend.app.core.config import AppSettings, _parse_origins


def test_production_allowed_origin_trims_surrounding_whitespace(monkeypatch):
    monkeypatch.setenv("FANCUE_ENV", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", " https://fan-cue.vercel.app ")

    settings = AppSettings()

    assert settings.allowed_origins == ["https://fan-cue.vercel.app"]
    assert not settings.allowed_origins[0].endswith("/")


def test_origin_parser_does_not_silently_remove_trailing_slash():
    assert _parse_origins("https://fan-cue.vercel.app") == [
        "https://fan-cue.vercel.app"
    ]
    assert _parse_origins("https://fan-cue.vercel.app/") == [
        "https://fan-cue.vercel.app/"
    ]


def test_production_preflight_allows_exact_origin_only():
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
        trailing_slash_mismatch = client.options(
            "/catchup",
            headers={
                "Origin": "https://fan-cue.vercel.app/",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert accepted.headers.get("access-control-allow-origin") == "https://fan-cue.vercel.app"
    assert trailing_slash_mismatch.headers.get("access-control-allow-origin") is None
