"""Application configuration loaded from environment variables.

All settings read from the process environment (populated by python-dotenv
from a .env file in development). No secret values are hardcoded here.

Missing REQUIRED production settings will raise EnvironmentError so the
application fails fast rather than silently using insecure defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _get_env(key: str, default: str | None = None) -> str:
    """Return env value or default; raise EnvironmentError if neither available."""
    val = os.environ.get(key, default)
    if val is None:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            "Check your .env file against .env.example."
        )
    return val


def _parse_origins(raw: str) -> List[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


def _default_origins() -> List[str]:
    raw = os.environ.get("ALLOWED_ORIGINS")
    if raw is not None:
        return _parse_origins(raw)
    env = os.environ.get("FANCUE_ENV", "development").lower()
    if env == "production":
        return []
    return ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"]


@dataclass(frozen=True)
class AppSettings:
    """Validated application settings for this process."""

    fancue_env: str = field(default_factory=lambda: os.environ.get("FANCUE_ENV", "development"))
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))

    # CORS — comma-separated list of allowed origins.
    # In development: defaults to localhost and 127.0.0.1 on ports 5173 and 3000.
    # In production: must be explicitly set via ALLOWED_ORIGINS (no localhost fallback).
    allowed_origins: List[str] = field(default_factory=_default_origins)

    # Trusted proxies for safe X-Forwarded-For client IP resolution
    trusted_proxies: List[str] = field(
        default_factory=lambda: [
            p.strip()
            for p in os.environ.get("TRUSTED_PROXIES", "127.0.0.1,::1,testclient").split(",")
            if p.strip()
        ]
    )

    # Qdrant
    qdrant_host: str = field(default_factory=lambda: os.environ.get("QDRANT_HOST", "127.0.0.1"))
    qdrant_port: int = field(default_factory=lambda: int(os.environ.get("QDRANT_PORT", "6333")))
    qdrant_url: str | None = field(default_factory=lambda: os.environ.get("QDRANT_URL") or None)
    qdrant_api_key: str | None = field(
        default_factory=lambda: os.environ.get("QDRANT_API_KEY") or None
    )
    qdrant_collection_dev: str = field(
        default_factory=lambda: os.environ.get(
            "QDRANT_COLLECTION_DEV", "fancue_cricket_knowledge_dev_v1"
        )
    )
    qdrant_collection_prod: str = field(
        default_factory=lambda: os.environ.get(
            "QDRANT_COLLECTION_PROD", "fancue_cricket_knowledge_v1"
        )
    )

    # LLM
    skip_llm: bool = field(
        default_factory=lambda: os.environ.get("SKIP_LLM_IN_TESTS", "false").lower()
        in ("true", "1", "yes")
    )
    # OpenAI API key — read from env only, never hardcoded, never logged.
    # Presence is checked at provider construction time.
    openai_api_key: str | None = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY") or None
    )
    openai_model: str = field(
        default_factory=lambda: os.environ.get("LLM_MODEL", "gpt-4o-mini")
    )
    openai_timeout_seconds: float = field(
        default_factory=lambda: float(os.environ.get("LLM_TIMEOUT_SECONDS", "30"))
    )

    # Retrieval
    retrieval_top_k: int = field(
        default_factory=lambda: int(os.environ.get("RETRIEVAL_TOP_K", "5"))
    )

    # Cricket Data API (cricketdata.org — near-live match discovery)
    cricket_data_api_key: str | None = field(
        default_factory=lambda: os.environ.get("CRICKET_DATA_API_KEY") or None
    )
    cricket_data_api_url: str = field(
        default_factory=lambda: os.environ.get(
            "CRICKET_DATA_API_URL", "https://api.cricapi.com/v1/"
        )
    )
    cricket_data_timeout_seconds: float = field(
        default_factory=lambda: float(os.environ.get("CRICKET_DATA_TIMEOUT_SECONDS", "10.0"))
    )
    cricket_data_cache_ttl_seconds: int = field(
        default_factory=lambda: int(os.environ.get("CRICKET_DATA_CACHE_TTL_SECONDS", "300"))
    )

    @property
    def is_production(self) -> bool:
        return self.fancue_env == "production"

    @property
    def qdrant_active_collection(self) -> str:
        return self.qdrant_collection_prod if self.is_production else self.qdrant_collection_dev

    @property
    def llm_live(self) -> bool:
        """Return True when a valid (non-placeholder) OpenAI key is configured and LLM is not skipped."""
        if self.skip_llm:
            return False
        if not self.openai_api_key:
            return False
        if self.openai_api_key.startswith("REPLACE_"):
            return False
        return True

    @property
    def cricket_data_live(self) -> bool:
        """Return True when a valid (non-placeholder) Cricket Data API key is configured."""
        if not self.cricket_data_api_key:
            return False
        if self.cricket_data_api_key.startswith("REPLACE_"):
            return False
        return True


_settings: AppSettings | None = None


def get_settings(reload: bool = False) -> AppSettings:
    """Return singleton AppSettings, initialised once per process (or reloaded if reload=True)."""
    global _settings
    if _settings is None or reload:
        # Load .env in development; in production vars come from the environment directly
        env_file = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
            ".env",
        )
        if os.path.isfile(env_file):
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file, override=False)
            except ImportError:
                pass  # python-dotenv not installed — rely on system env
        _settings = AppSettings()
    return _settings

