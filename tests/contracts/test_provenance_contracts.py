"""Contract tests for data provenance, attribution, and SHA-256 checksum integrity."""

from datetime import datetime, timezone
import os
import yaml
import pytest
from pydantic import ValidationError

from backend.app.schemas.provenance import (
    PermittedUse,
    SourceProvenance,
)


def test_valid_source_provenance():
    """Verify standard valid SourceProvenance record."""
    prov = SourceProvenance(
        source_id="cricsheet_historical_odi",
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc),
        dataset_revision="1",
        source_format="json",
        source_format_version="1.3.0",
        file_sha256="8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f",
        license_name="Open Data Commons Attribution License (ODC-By v1.0)",
        license_url="http://opendatacommons.org/licenses/by/1.0/",
        attribution_text="Data provided by Cricsheet (https://cricsheet.org/), licensed under ODC-By v1.0.",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        modifications="None",
    )
    assert prov.source_id == "cricsheet_historical_odi"
    assert prov.permitted_use == PermittedUse.OPEN_ATTRIBUTION
    assert len(prov.file_sha256) == 64


def test_provenance_rejects_naive_timestamp():
    """Timestamps without explicit timezone info must be rejected."""
    with pytest.raises(ValidationError) as exc:
        SourceProvenance(
            source_id="cricsheet_test",
            source_name="Cricsheet",
            source_url="https://cricsheet.org/",
            retrieved_at=datetime(2026, 10, 11, 12, 0, 0),  # Naive (no tzinfo)
            dataset_revision="1",
            source_format="json",
            source_format_version="1.3.0",
            file_sha256="8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f",
            license_name="ODC-By-1.0",
            license_url="http://opendatacommons.org/licenses/by/1.0/",
            attribution_text="Data provided by Cricsheet under ODC-By v1.0.",
            permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        )
    assert "timezone-aware UTC datetime" in str(exc.value)


def test_provenance_rejects_invalid_sha256_format():
    """SHA-256 strings not conforming to 64 lowercase hex characters must fail."""
    # Too short
    with pytest.raises(ValidationError):
        SourceProvenance(
            source_id="test",
            source_name="Test",
            source_url="https://example.com",
            retrieved_at=datetime.now(timezone.utc),
            dataset_revision="1",
            source_format="json",
            source_format_version="1.0",
            file_sha256="abcdef1234",  # Invalid length
            license_name="MIT",
            license_url="https://mit.edu",
            attribution_text="Attribution statement.",
            permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        )

    # Invalid non-hex characters
    with pytest.raises(ValidationError):
        SourceProvenance(
            source_id="test",
            source_name="Test",
            source_url="https://example.com",
            retrieved_at=datetime.now(timezone.utc),
            dataset_revision="1",
            source_format="json",
            source_format_version="1.0",
            file_sha256="z" * 64,  # 'z' is not a hex digit
            license_name="MIT",
            license_url="https://mit.edu",
            attribution_text="Attribution statement.",
            permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        )


def test_provenance_requires_meaningful_attribution():
    """Attribution text shorter than 10 characters must be rejected."""
    with pytest.raises(ValidationError):
        SourceProvenance(
            source_id="test",
            source_name="Test",
            source_url="https://example.com",
            retrieved_at=datetime.now(timezone.utc),
            dataset_revision="1",
            source_format="json",
            source_format_version="1.0",
            file_sha256="a" * 64,
            license_name="MIT",
            license_url="https://mit.edu",
            attribution_text="Short",  # < 10 chars
            permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        )


def test_data_sources_yaml_registry_validates():
    """Ensure data/sources.yml exists and matches the provenance contract."""
    sources_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/sources.yml"))
    assert os.path.exists(sources_path), "data/sources.yml must exist"

    with open(sources_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["version"] == "1.0.0"
    assert len(data["sources"]) >= 1

    entry = data["sources"][0]
    prov = SourceProvenance(
        source_id=entry["source_id"],
        source_name=entry["source_name"],
        source_url=entry["canonical_url"],
        retrieved_at=datetime.fromisoformat(entry["retrieved_at"]),
        dataset_revision=str(entry["selected_fixture"]["dataset_revision"]),
        source_format=entry["format"],
        source_format_version=entry["format_version"],
        file_sha256=entry["selected_fixture"]["file_sha256"],
        license_name=entry["license_name"],
        license_url=entry["license_url"],
        attribution_text=entry["attribution_text"],
        permitted_use=PermittedUse(entry["permitted_use"]),
        modifications=entry["modifications"],
    )
    assert prov.source_id == "cricsheet_historical_odi"
    assert prov.file_sha256 == "8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f"
