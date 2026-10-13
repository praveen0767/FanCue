"""FanCue FastAPI application entry point.

This module creates, configures, and exports the FastAPI application instance.
It is the sole authoritative entry point for the HTTP API layer.

Startup sequence:
1. Load settings from environment.
2. Configure CORS middleware.
3. Register API routers.
4. Expose /healthz, /matches, /matches/{match_id}/intervals, POST /catchup.

Run with:
    uvicorn backend.app.main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.app.api.cors import configure_cors
from backend.app.api.health import router as health_router
from backend.app.api.matches import router as matches_router
from backend.app.api.catchup import router as catchup_router
from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    Separated into a factory function to support clean test construction.
    """
    settings = get_settings()

    app = FastAPI(
        title="FanCue API",
        description=(
            "AI-powered, evidence-grounded cricket match catch-up. "
            "Catch the moment. Understand the game."
        ),
        version="0.8.0",
        docs_url="/docs",
        redoc_url="/redoc",
        # Do NOT expose the OpenAPI schema in production without auth
        openapi_url="/openapi.json",
    )

    # Configure CORS from environment settings
    configure_cors(app, settings)

    # Register routers
    app.include_router(health_router)
    app.include_router(matches_router)
    app.include_router(catchup_router)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc):
        """Ensure unhandled exceptions never leak internal details to the client."""
        logger.exception("Unhandled exception in request %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again.",
                },
            },
        )

    logger.info(
        "FanCue API v0.8.0 started (env=%s, skip_llm=%s, origins=%s)",
        settings.fancue_env,
        settings.skip_llm,
        settings.allowed_origins,
    )

    return app


# Application singleton — exported for uvicorn and tests
app = create_app()
