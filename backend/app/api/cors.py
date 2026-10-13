"""CORS middleware configuration helper.

Reads allowed origins from AppSettings (which reads from ALLOWED_ORIGINS env var).
Do NOT add credentials=True unless the frontend explicitly requires cookies,
which FanCue does not.

Usage:
    from backend.app.api.cors import configure_cors
    configure_cors(app, settings)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import AppSettings


def configure_cors(app: FastAPI, settings: AppSettings) -> None:
    """Add CORS middleware to the FastAPI app using settings-derived origin list.

    - Allows origins listed in ALLOWED_ORIGINS (comma-separated env var).
    - In production, wildcards (*) are explicitly rejected for security.
    - Does NOT enable credentials (no cookies used).
    - Allows standard HTTP methods and headers used by the FanCue frontend.
    """
    origins = [o for o in settings.allowed_origins if not (settings.is_production and o == "*")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-Correlation-Id"],
    )
