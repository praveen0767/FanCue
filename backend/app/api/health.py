"""FastAPI router — health check endpoint.

GET /healthz

Returns basic process health. Does NOT assert that Qdrant is reachable
(that would require a live network call on every health probe, violating
the principle of least surprise for container orchestrators).
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Minimal health-check response suitable for container liveness probes."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(..., description="'ok' when process is running.")
    service: str = Field(default="fancue-api")
    version: str = Field(default="0.9.0")
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of this check.",
    )


class ReadinessResponse(BaseModel):
    """Dependency readiness response distinguishing process liveness from dependencies."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(..., description="'ready' or 'degraded' or 'unready'")
    service: str = Field(default="fancue-api")
    fixtures: str = Field(..., description="'ready' when authoritative fixtures are loaded.")
    qdrant: str = Field(..., description="'ready', 'unreachable', or 'bypassed'.")
    llm_mode: str = Field(..., description="'deterministic_fallback' or 'live'.")
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of this check.",
    )


@router.get("/healthz", response_model=HealthResponse, summary="Process liveness probe")
def healthz() -> HealthResponse:
    """Return process-level health status.

    Confirms the API process is running and accepting HTTP requests.
    Does NOT assert external dependency readiness.
    """
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadinessResponse, summary="Dependency readiness probe")
def readyz() -> ReadinessResponse:
    """Return comprehensive dependency readiness status.

    Checks authoritative fixture availability, Qdrant connectivity,
    and LLM operating mode without exposing credentials or internal tracebacks.
    """
    from backend.app.core.config import get_settings
    from backend.app.core.fixtures import list_available_match_ids

    settings = get_settings()

    # 1. Authoritative fixtures check
    available_fixtures = list_available_match_ids()
    fixtures_status = "ready" if len(available_fixtures) >= 2 else "missing_fixtures"

    # 2. Qdrant connectivity check
    qdrant_status = "bypassed"
    if settings.retrieval_enabled and not settings.skip_llm:
        try:
            from ingestion.knowledge.qdrant_store import QdrantStore

            store = QdrantStore(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                allow_local_fallback=not settings.is_production,
            )
            client = store.get_client()
            client.get_collections()
            qdrant_status = "ready"
        except Exception:
            qdrant_status = "unreachable"

    llm_mode = "deterministic_fallback" if settings.skip_llm else "live"

    overall_status = "ready"
    if fixtures_status != "ready":
        overall_status = "unready"
    elif qdrant_status == "unreachable" and settings.is_production:
        overall_status = "degraded"

    return ReadinessResponse(
        status=overall_status,
        fixtures=fixtures_status,
        qdrant=qdrant_status,
        llm_mode=llm_mode,
    )
