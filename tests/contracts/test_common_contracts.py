"""Tests for common domain contracts: MatchDescriptor, RequestCorrelation, and core enums."""

import pytest
from pydantic import ValidationError

from backend.app.schemas.common import (
    ExplanationDepth,
    LanguageCode,
    MatchDescriptor,
    MatchMode,
    PerspectiveLens,
    RequestCorrelation,
    SportType,
)


def test_valid_match_descriptor():
    """Verify standard valid MatchDescriptor instantiation."""
    desc = MatchDescriptor(
        match_id="1529229",
        sport=SportType.CRICKET,
        name="India vs West Indies",
        format="ODI",
        teams=["India", "West Indies"],
        date="2026-10-03",
        venue="Sabina Park, Kingston",
        mode=MatchMode.REPLAY,
        source_id="cricsheet_historical_odi",
        source_revision="1",
        supported_innings=[0, 1],
    )
    assert desc.match_id == "1529229"
    assert desc.sport == SportType.CRICKET
    assert desc.mode == MatchMode.REPLAY
    assert len(desc.teams) == 2


def test_match_descriptor_invalid_sport():
    """Unsupported sport enum value must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        MatchDescriptor(
            match_id="1529229",
            sport="basketball",  # Invalid
            name="India vs West Indies",
            format="ODI",
            teams=["India", "West Indies"],
            date="2026-10-03",
            source_id="cricsheet_historical_odi",
            source_revision="1",
        )
    assert "Input should be 'cricket' or 'football'" in str(exc_info.value)


def test_match_descriptor_invalid_date_format():
    """Invalid date format must be rejected."""
    with pytest.raises(ValidationError):
        MatchDescriptor(
            match_id="1529229",
            sport=SportType.CRICKET,
            name="India vs West Indies",
            format="ODI",
            teams=["India", "West Indies"],
            date="03-10-2026",  # Not YYYY-MM-DD
            source_id="cricsheet_historical_odi",
            source_revision="1",
        )


def test_match_descriptor_forbids_extra_fields():
    """Unknown fields must be strictly rejected."""
    with pytest.raises(ValidationError) as exc_info:
        MatchDescriptor(
            match_id="1529229",
            sport=SportType.CRICKET,
            name="India vs West Indies",
            format="ODI",
            teams=["India", "West Indies"],
            date="2026-10-03",
            source_id="cricsheet_historical_odi",
            source_revision="1",
            broadcaster="Sky Sports",  # Extra field
        )
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_valid_request_correlation():
    """Verify request correlation object with UTC timestamp."""
    corr = RequestCorrelation(correlation_id="corr_test_12345678")
    assert corr.correlation_id == "corr_test_12345678"
    assert corr.created_at.tzinfo is not None


def test_request_correlation_too_short():
    """Correlation IDs shorter than 8 chars must be rejected."""
    with pytest.raises(ValidationError):
        RequestCorrelation(correlation_id="short")
