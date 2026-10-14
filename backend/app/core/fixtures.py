"""Fixture registry — loads and caches known Cricsheet match engines.

Match facts derive from the tracked, authoritative JSON files in data/raw/.
Known fixture hashes are verified on every first load by the JSON parser.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Optional

from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.schemas.common import MatchDescriptor
from backend.app.schemas.provenance import PermittedUse, SourceProvenance

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _data_root() -> str:
    """Return absolute path to data/raw/, supporting dev and container layouts."""
    candidate = os.path.join(_REPO_ROOT, "data", "raw")
    if os.path.isdir(candidate):
        return candidate
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "raw")
    )


# Frozen provenance for each fixture recorded in data/sources.yml.
# Hashes are raw file SHA-256 values and must be updated with the registry when data changes.
_FIXTURE_METADATA: Dict[str, Dict[str, object]] = {
    "1529229": {
        "source_id": "cricsheet_historical_odi",
        "retrieved_at": datetime(2026, 10, 6, 12, 45, 0, tzinfo=timezone.utc),
        "dataset_revision": "1",
        "sha256": "8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f",
    },
    "1552779": {
        "source_id": "cricsheet_historical_t20",
        "retrieved_at": datetime(2026, 10, 6, 12, 45, 0, tzinfo=timezone.utc),
        "dataset_revision": "1",
        "sha256": "99b2df4d4ebcaa328834ec101776a201c679b5d89b1a604241c504b0d9bb3e2b",
    },
}


def _make_provenance(match_id: str) -> SourceProvenance:
    """Return fixture-specific provenance; unknown fixtures are rejected."""
    try:
        metadata = _FIXTURE_METADATA[match_id]
    except KeyError as exc:
        raise ValueError(f"No verified provenance record exists for fixture {match_id!r}.") from exc

    return SourceProvenance(
        source_id=str(metadata["source_id"]),
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=metadata["retrieved_at"],
        dataset_revision=str(metadata["dataset_revision"]),
        source_format="json",
        source_format_version="1.3.0",
        file_sha256=str(metadata["sha256"]),
        license_name="Open Data Commons Attribution License (ODC-By v1.0)",
        license_url="https://opendatacommons.org/licenses/by/1.0/",
        attribution_text=(
            "Data provided by Cricsheet (https://cricsheet.org/), licensed under "
            "the Open Data Commons Attribution License (ODC-By v1.0)."
        ),
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        modifications="Normalized to FanCue CricketDeliveryEvent schema.",
    )


# Registry cache — built lazily for process lifetime.
_engine_cache: Dict[str, CricketMatchEngine] = {}


def _build_engine(match_id: str) -> CricketMatchEngine:
    """Load a known fixture and verify its raw bytes against the registered hash."""
    raw_dir = _data_root()
    file_path = os.path.join(raw_dir, f"{match_id}.json")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            f"Fixture file for match {match_id!r} not found at {file_path!r}. "
            "Check that the expected Cricsheet JSON exists in data/raw/."
        )

    metadata = _FIXTURE_METADATA.get(match_id)
    if metadata is None:
        raise ValueError(f"No verified provenance record exists for fixture {match_id!r}.")

    provenance = _make_provenance(match_id)
    return CricketMatchEngine.from_fixture(
        file_path=file_path,
        match_id=match_id,
        provenance=provenance,
        expected_sha256=str(metadata["sha256"]),
    )


def get_engine(match_id: str) -> Optional[CricketMatchEngine]:
    """Return a cached engine, or None if the fixture file is absent."""
    if match_id not in _engine_cache:
        try:
            _engine_cache[match_id] = _build_engine(match_id)
        except FileNotFoundError:
            return None
    return _engine_cache[match_id]


def list_available_match_ids() -> list[str]:
    """List only verified, supported fixture IDs actually present on disk."""
    raw_dir = _data_root()
    if not os.path.isdir(raw_dir):
        return []
    return sorted(
        match_id
        for match_id in _FIXTURE_METADATA
        if os.path.isfile(os.path.join(raw_dir, f"{match_id}.json"))
    )


def get_match_descriptor(match_id: str) -> Optional[MatchDescriptor]:
    """Return MatchDescriptor for match_id, or None if the fixture is unavailable."""
    engine = get_engine(match_id)
    if engine is None:
        return None
    return engine.match_descriptor
