"""Cricsheet JSON format parsing and structural integrity validation."""

import hashlib
import json
import os
from typing import Any, Dict, Optional

from backend.app.adapters.cricket.errors import (
    ChecksumMismatchError,
    CricsheetFormatError,
    FixtureNotFoundError,
    MissingCriticalFieldError,
)


def load_cricsheet_json(
    file_path: str,
    expected_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Load and validate a raw Cricsheet JSON match file.
    
    Args:
        file_path: Absolute or workspace-relative path to the JSON file.
        expected_sha256: Optional 64-character hex hash to verify against recorded provenance.
        
    Returns:
        Parsed and validated raw JSON data dictionary.
        
    Raises:
        FixtureNotFoundError: If the file does not exist.
        ChecksumMismatchError: If the computed SHA-256 differs from expected_sha256.
        CricsheetFormatError: If required top-level structures are missing.
        MissingCriticalFieldError: If essential metadata fields are absent.
    """
    if not os.path.exists(file_path):
        raise FixtureNotFoundError(
            f"Cricsheet fixture file not found at path: {file_path}",
            context={"file_path": file_path},
        )

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    if expected_sha256:
        actual_sha256 = hashlib.sha256(file_bytes).hexdigest()
        if actual_sha256.lower() != expected_sha256.lower():
            raise ChecksumMismatchError(
                f"Checksum mismatch for fixture '{file_path}'. "
                f"Expected {expected_sha256}, got {actual_sha256}.",
                context={
                    "file_path": file_path,
                    "expected_sha256": expected_sha256,
                    "actual_sha256": actual_sha256,
                },
            )

    try:
        data = json.loads(file_bytes.decode("utf-8"))
    except json.JSONDecodeError as err:
        raise CricsheetFormatError(
            f"Corrupt or non-JSON data in file '{file_path}': {err}",
            context={"file_path": file_path, "json_error": str(err)},
        )

    if not isinstance(data, dict):
        raise CricsheetFormatError(
            "Cricsheet root document must be a JSON object.",
            context={"file_path": file_path},
        )

    # Validate mandatory root keys
    for key in ("meta", "info", "innings"):
        if key not in data:
            raise MissingCriticalFieldError(
                f"Required Cricsheet root key '{key}' is missing.",
                context={"file_path": file_path, "missing_key": key},
            )

    meta = data["meta"]
    if not isinstance(meta, dict) or "data_version" not in meta:
        raise CricsheetFormatError(
            "Cricsheet 'meta' section must contain 'data_version'.",
            context={"file_path": file_path},
        )

    info = data["info"]
    if not isinstance(info, dict) or "teams" not in info:
        raise MissingCriticalFieldError(
            "Cricsheet 'info' section must specify participating 'teams'.",
            context={"file_path": file_path},
        )

    innings = data["innings"]
    if not isinstance(innings, list) or len(innings) == 0:
        raise CricsheetFormatError(
            "Cricsheet 'innings' section must be a non-empty list.",
            context={"file_path": file_path},
        )

    return data
