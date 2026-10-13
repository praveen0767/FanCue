"""Standardized structured error contracts."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ErrorCode(str, Enum):
    """Machine-readable application error codes."""
    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    INVALID_INTERVAL = "INVALID_INTERVAL"
    MATCH_NOT_FOUND = "MATCH_NOT_FOUND"
    UNSUPPORTED_DATA_FORMAT = "UNSUPPORTED_DATA_FORMAT"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"
    REVISION_MISMATCH = "REVISION_MISMATCH"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    """Detailed error diagnostics for clients and logs."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ErrorCode = Field(..., description="Canonical error code.")
    message: str = Field(..., min_length=1, description="Human-readable explanation of failure.")
    field: Optional[str] = Field(
        default=None,
        description="Path of invalid request field if applicable (e.g. 'interval.start_after_over').",
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional contextual diagnostic parameters.",
    )


class ErrorResponse(BaseModel):
    """Structured error payload returned on API failures."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    error: ErrorDetail = Field(...)
    correlation_id: str = Field(
        ...,
        min_length=8,
        description="Correlation ID for tracing error in logs.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timezone-aware UTC timestamp of failure.",
    )

    @field_validator("timestamp")
    @classmethod
    def validate_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be a timezone-aware UTC datetime.")
        return v
