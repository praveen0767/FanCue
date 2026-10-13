"""Data provenance, source attribution, and licensing metadata contracts."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PermittedUse(str, Enum):
    """Permitted usage tier for dataset."""
    OPEN_ATTRIBUTION = "open_attribution"
    NON_COMMERCIAL = "non_commercial"
    EVALUATION_ONLY = "evaluation_only"
    COMMERCIAL = "commercial"


class SourceProvenance(BaseModel):
    """Auditable provenance record for an authoritative data source or fixture."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of data source in registry.",
    )
    source_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Human-readable provider name (e.g. 'Cricsheet').",
    )
    source_url: str = Field(
        ...,
        description="Canonical URL of dataset provider.",
    )
    retrieved_at: datetime = Field(
        ...,
        description="Timezone-aware UTC timestamp when dataset was retrieved.",
    )
    dataset_revision: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Version, revision number, or git commit hash of dataset.",
    )
    source_format: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Source serialization format (e.g. 'json', 'yaml').",
    )
    source_format_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Format specification version (e.g. '1.3.0').",
    )
    file_sha256: str = Field(
        ...,
        pattern=r"^[a-f0-9]{64}$",
        description="Cryptographic SHA-256 hash (64 hex characters) of source file.",
    )
    license_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Full license name or SPDX identifier (e.g. 'ODC-By-1.0').",
    )
    license_url: str = Field(
        ...,
        description="Canonical URL to full legal license text.",
    )
    attribution_text: str = Field(
        ...,
        min_length=10,
        max_length=512,
        description="Mandatory legal attribution notice as required by license.",
    )
    permitted_use: PermittedUse = Field(
        ...,
        description="Authorized usage category.",
    )
    modifications: str = Field(
        default="None",
        max_length=256,
        description="Summary of any transformations applied to raw data.",
    )

    @field_validator("retrieved_at")
    @classmethod
    def validate_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure timestamp has explicit timezone information."""
        if v.tzinfo is None:
            raise ValueError("retrieved_at must be a timezone-aware UTC datetime.")
        return v
