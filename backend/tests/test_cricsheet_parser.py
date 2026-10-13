"""Tests for Cricsheet JSON parser and structural validator."""

import json
import os
import pytest

from backend.app.adapters.cricket.errors import (
    ChecksumMismatchError,
    CricsheetFormatError,
    FixtureNotFoundError,
    MissingCriticalFieldError,
)
from backend.app.adapters.cricket.parser import load_cricsheet_json

FIXTURE_1529229 = os.path.abspath("data/raw/1529229.json")
SHA256_1529229 = "8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f"


def test_load_cricsheet_json_valid():
    """Verify loading and validating real Cricsheet fixture 1529229."""
    data = load_cricsheet_json(FIXTURE_1529229, expected_sha256=SHA256_1529229)
    assert data["meta"]["data_version"] == "1.3.0"
    assert data["info"]["match_type"] == "ODI"
    assert len(data["innings"]) == 2


def test_load_cricsheet_json_file_not_found():
    """Missing file raises FixtureNotFoundError."""
    with pytest.raises(FixtureNotFoundError):
        load_cricsheet_json("data/raw/non_existent_fixture.json")


def test_load_cricsheet_json_checksum_mismatch():
    """Tampered or mismatched expected checksum raises ChecksumMismatchError."""
    with pytest.raises(ChecksumMismatchError):
        load_cricsheet_json(FIXTURE_1529229, expected_sha256="0" * 64)


def test_load_cricsheet_json_corrupt_json(tmp_path):
    """Corrupt non-JSON file raises CricsheetFormatError."""
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("NOT A JSON {", encoding="utf-8")
    with pytest.raises(CricsheetFormatError):
        load_cricsheet_json(str(corrupt_file))


def test_load_cricsheet_json_non_dict_root(tmp_path):
    """JSON with list root raises CricsheetFormatError."""
    list_file = tmp_path / "list_root.json"
    list_file.write_text("[]", encoding="utf-8")
    with pytest.raises(CricsheetFormatError):
        load_cricsheet_json(str(list_file))


def test_load_cricsheet_json_missing_root_keys(tmp_path):
    """Missing required keys ('meta', 'info', 'innings') raises MissingCriticalFieldError."""
    bad_file = tmp_path / "missing_meta.json"
    bad_file.write_text(json.dumps({"info": {}, "innings": []}), encoding="utf-8")
    with pytest.raises(MissingCriticalFieldError) as exc:
        load_cricsheet_json(str(bad_file))
    assert "missing_meta" in str(exc.value) or "meta" in str(exc.value)


def test_load_cricsheet_json_missing_data_version(tmp_path):
    """Missing data_version in meta section raises CricsheetFormatError."""
    bad_file = tmp_path / "missing_version.json"
    bad_file.write_text(json.dumps({"meta": {}, "info": {"teams": ["A", "B"]}, "innings": [{}]}), encoding="utf-8")
    with pytest.raises(CricsheetFormatError):
        load_cricsheet_json(str(bad_file))


def test_load_cricsheet_json_missing_teams(tmp_path):
    """Missing info.teams raises MissingCriticalFieldError."""
    bad_file = tmp_path / "missing_teams.json"
    bad_file.write_text(json.dumps({"meta": {"data_version": "1.3.0"}, "info": {}, "innings": [{}]}), encoding="utf-8")
    with pytest.raises(MissingCriticalFieldError):
        load_cricsheet_json(str(bad_file))


def test_load_cricsheet_json_empty_innings(tmp_path):
    """Empty innings array raises CricsheetFormatError."""
    bad_file = tmp_path / "empty_innings.json"
    bad_file.write_text(json.dumps({"meta": {"data_version": "1.3.0"}, "info": {"teams": ["A", "B"]}, "innings": []}), encoding="utf-8")
    with pytest.raises(CricsheetFormatError):
        load_cricsheet_json(str(bad_file))
