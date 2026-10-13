"""Tests for deterministic idempotency of cricket match engine."""

from datetime import datetime, timezone
import os
import pytest

from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.schemas.cricket import (
    CricketCatchUpRequest,
    CricketInterval,
)
from backend.app.schemas.provenance import (
    PermittedUse,
    SourceProvenance,
)

FIXTURE_1529229 = os.path.abspath("data/raw/1529229.json")
SHA256_1529229 = "8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f"


@pytest.fixture
def sample_provenance():
    return SourceProvenance(
        source_id="cricsheet_historical_odi",
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=datetime.now(timezone.utc),
        dataset_revision="1",
        source_format="json",
        source_format_version="1.3.0",
        file_sha256=SHA256_1529229,
        license_name="ODC-By-1.0",
        license_url="http://opendatacommons.org/licenses/by/1.0/",
        attribution_text="Data provided by Cricsheet under ODC-By v1.0.",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
    )


def test_idempotent_event_normalization(sample_provenance):
    """Multiple normalization runs of the same match produce byte-for-byte identical events."""
    engine1 = CricketMatchEngine.from_fixture(FIXTURE_1529229, "1529229", sample_provenance)
    engine2 = CricketMatchEngine.from_fixture(FIXTURE_1529229, "1529229", sample_provenance)

    events1 = engine1.get_innings_events(0)
    events2 = engine2.get_innings_events(0)

    assert len(events1) == len(events2)
    for e1, e2 in zip(events1, events2):
        assert e1.event_id == e2.event_id
        assert e1.model_dump() == e2.model_dump()


def test_idempotent_interval_reconstruction(sample_provenance):
    """Multiple interval reconstructions produce identical states, deltas, and evidence packets."""
    engine = CricketMatchEngine.from_fixture(FIXTURE_1529229, "1529229", sample_provenance)
    request = CricketCatchUpRequest(
        match_id="1529229",
        interval=CricketInterval(innings=0, start_after_over=10, end_after_over=20),
    )

    run1 = engine.reconstruct_interval(request)
    run2 = engine.reconstruct_interval(request)

    # Compare state_before, state_after, delta, packet
    assert run1[0].model_dump() == run2[0].model_dump()
    assert run1[1].model_dump() == run2[1].model_dump()
    assert run1[2].model_dump() == run2[2].model_dump()
    assert run1[4].model_dump() == run2[4].model_dump()
