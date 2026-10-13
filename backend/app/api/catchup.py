"""FastAPI router — cricket catch-up endpoint.

POST /catchup

Validates the request, invokes the real CricketCatchUpOrchestrator, and
returns the canonical CricketCatchUpResponse including the evidence packet
and a deterministic fallback when the LLM is unavailable or verification fails.

No AI output is returned without passing claim verification.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.app.core.config import AppSettings, get_settings
from backend.app.core.fixtures import get_engine
from backend.app.match_engine.errors import (
    InningsIndexOutOfBoundsError,
    OverBoundaryNotFoundError,
)
from backend.app.ai.provider import DeterministicFakeProvider, OpenAILLMProvider
from backend.app.orchestration.cricket_catchup import CricketCatchUpOrchestrator
from backend.app.schemas.cricket import CricketCatchUpRequest
from backend.app.schemas.errors import ErrorCode, ErrorDetail, ErrorResponse
from backend.app.schemas.explanation import CricketCatchUpResponse

router = APIRouter(tags=["catchup"])


import time
from collections import defaultdict

_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_LIMIT_MAX_REQUESTS = 60
_request_history: dict[str, list[float]] = defaultdict(list)


def resolve_client_ip(request: Request, trusted_proxies: list[str]) -> str:
    """Resolve client IP safely against trusted proxies.

    Security Principle:
    Arbitrary client-supplied X-Forwarded-For headers MUST NOT be trusted
    unless the immediate peer connection (request.client.host) is an explicitly
    configured trusted proxy (e.g. reverse proxy, cloud load balancer).

    If the peer is untrusted, the peer IP itself is used for rate limiting.
    If the peer is a trusted proxy, the leftmost client IP from X-Forwarded-For is used.

    Multi-instance Limitation Disclosure:
    This in-memory rate limiting operates per process instance. In horizontally
    scaled multi-instance environments, edge-level rate limiting (e.g. Cloudflare)
    or centralized token buckets (e.g. Redis when justified under AGENTS.md §12)
    must be adopted if uniform cross-instance quotas are required.
    """
    peer_ip = request.client.host if request.client else "127.0.0.1"
    if peer_ip in trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer_ip


def _check_rate_limit(client_ip: str, max_req: int = _RATE_LIMIT_MAX_REQUESTS, window: float = _RATE_LIMIT_WINDOW_SECONDS) -> bool:
    """Return False if client_ip has exceeded rate limit within window."""
    now = time.time()
    cutoff = now - window
    timestamps = [ts for ts in _request_history[client_ip] if ts > cutoff]
    if len(timestamps) >= max_req:
        _request_history[client_ip] = timestamps
        return False
    timestamps.append(now)
    _request_history[client_ip] = timestamps
    return True


def _correlation_id(request: Request) -> str:
    """Return client-provided or generated correlation ID for this request."""
    return request.headers.get("X-Correlation-Id", str(uuid.uuid4()))


def _safe_error(
    status_code: int,
    code: ErrorCode,
    message: str,
    correlation_id: str,
    field: Optional[str] = None,
) -> JSONResponse:
    """Produce a structured, safe error response without any internal details."""
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, field=field),
        correlation_id=correlation_id,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@router.post(
    "/catchup",
    response_model=CricketCatchUpResponse,
    summary="Cricket match interval catch-up",
    description=(
        "Reconstruct what happened during a historical cricket match interval. "
        "Returns a verified explanation grounded in authoritative match data, "
        "or a deterministic fallback when AI is unavailable."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Malformed or invalid request."},
        404: {"model": ErrorResponse, "description": "Match not found."},
        422: {"description": "Validation error (FastAPI built-in)."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
        500: {"model": ErrorResponse, "description": "Internal server error."},
    },
)
async def cricket_catchup(
    body: CricketCatchUpRequest,
    request: Request,
    settings: AppSettings = Depends(get_settings),
) -> CricketCatchUpResponse:
    """Process a cricket catch-up request through the full orchestration pipeline.

    The endpoint:
    1. Validates the request against the canonical CricketCatchUpRequest schema.
    2. Loads the authoritative match engine for the given match_id.
    3. Validates that the requested innings/interval exists in the fixture.
    4. Runs the CricketCatchUpOrchestrator (engine → retrieval → LLM → verification → fallback).
    5. Returns the CricketCatchUpResponse with evidence packet and verified explanation.

    AI output is only returned after passing deterministic claim verification.
    If verification fails or the LLM is unavailable, a deterministic fallback is returned.
    """
    corr_id = _correlation_id(request)

    # 0. In-memory rate limiting safeguard with trusted-proxy-aware IP resolution
    client_ip = resolve_client_ip(request, settings.trusted_proxies)
    if not _check_rate_limit(client_ip):
        return _safe_error(
            429,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            "Rate limit exceeded. Maximum 60 requests per minute allowed.",
            corr_id,
        )

    # 1. Load match engine
    engine = get_engine(body.match_id)
    if engine is None:
        return _safe_error(
            404,
            ErrorCode.MATCH_NOT_FOUND,
            f"Match '{body.match_id}' is not available. "
            "Use GET /matches to list available fixtures.",
            corr_id,
            field="match_id",
        )

    # 2. Validate interval boundaries against real engine data
    try:
        engine.validate_boundary_availability(
            body.interval.innings, body.interval.start_after_over
        )
        engine.validate_boundary_availability(
            body.interval.innings, body.interval.end_after_over
        )
    except InningsIndexOutOfBoundsError as e:
        return _safe_error(
            400,
            ErrorCode.INVALID_INTERVAL,
            f"Innings index out of bounds: {e}",
            corr_id,
            field="interval.innings",
        )
    except OverBoundaryNotFoundError as e:
        return _safe_error(
            400,
            ErrorCode.INVALID_INTERVAL,
            f"Interval boundary not found in fixture data: {e}",
            corr_id,
            field="interval.end_after_over",
        )

    # 3. Build orchestrator (no retrieval service in fallback mode if Qdrant is absent)
    retrieval_service = None
    try:
        from ingestion.knowledge.retrieve import RetrievalService
        from ingestion.knowledge.qdrant_store import QdrantStore

        store = QdrantStore(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        retrieval_service = RetrievalService(
            collection_name=settings.qdrant_active_collection,
            store=store,
        )
    except Exception:
        # Qdrant unavailable — orchestrator proceeds without retrieval
        retrieval_service = None

    # 3. Build LLM provider (key is never logged or forwarded to client)
    if settings.llm_live:
        llm_provider = OpenAILLMProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    else:
        llm_provider = DeterministicFakeProvider()

    orchestrator = CricketCatchUpOrchestrator(
        engine=engine,
        retrieval_service=retrieval_service,
        llm_provider=llm_provider,
        skip_llm=settings.skip_llm,
    )

    # 4. Run the full orchestration lifecycle
    try:
        response = orchestrator.catch_up(body)
        return response
    except (InningsIndexOutOfBoundsError, OverBoundaryNotFoundError) as e:
        return _safe_error(
            400,
            ErrorCode.INVALID_INTERVAL,
            str(e),
            corr_id,
        )
    except Exception:
        # Do NOT expose internal details to the client
        return _safe_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "An unexpected error occurred processing the catch-up request. "
            "Please retry or contact support.",
            corr_id,
        )
