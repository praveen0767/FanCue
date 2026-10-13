"""Tests for cricket delivery and match descriptor normalizer."""

import os
import pytest

from backend.app.adapters.cricket.errors import (
    CricsheetDeliveryArithmeticError,
    CricsheetFormatError,
    MissingCriticalFieldError,
)
from backend.app.adapters.cricket.normalizer import (
    normalize_innings_deliveries,
    normalize_match_descriptor,
)
from backend.app.adapters.cricket.parser import load_cricsheet_json
from backend.app.schemas.common import MatchMode, SportType

FIXTURE_1529229 = os.path.abspath("data/raw/1529229.json")


@pytest.fixture
def raw_match_data():
    return load_cricsheet_json(FIXTURE_1529229)


def test_normalize_match_descriptor_valid(raw_match_data):
    """Verify descriptor extraction from real fixture."""
    desc = normalize_match_descriptor(
        raw_data=raw_match_data,
        match_id="1529229",
        source_id="cricsheet_historical_odi",
        source_revision="1",
    )
    assert desc.match_id == "1529229"
    assert desc.sport == SportType.CRICKET
    assert desc.format == "ODI"
    assert desc.teams == ["India", "West Indies"]
    assert desc.mode == MatchMode.REPLAY
    assert desc.supported_innings == [0, 1]


def test_normalize_match_descriptor_missing_teams():
    """Missing or insufficient teams raises MissingCriticalFieldError."""
    with pytest.raises(MissingCriticalFieldError):
        normalize_match_descriptor(
            raw_data={"info": {"teams": ["India"]}},
            match_id="1529229",
            source_id="cricsheet",
            source_revision="1",
        )


def test_normalize_innings_deliveries_real_fixture(raw_match_data):
    """Verify delivery event normalization for real fixture innings 0."""
    events = normalize_innings_deliveries(raw_match_data, "1529229", 0)
    assert len(events) > 0

    first_ball = events[0]
    assert first_ball.event_id == "1529229_inn0_ov0_d1"
    assert first_ball.over == 0
    assert first_ball.delivery_in_over == 1
    assert first_ball.legal_ball_number == 1
    assert first_ball.batter == "RG Sharma"
    assert first_ball.bowler == "JNT Seales"


def test_normalize_innings_deliveries_out_of_bounds_innings(raw_match_data):
    """Requesting non-existent innings raises CricsheetFormatError."""
    with pytest.raises(CricsheetFormatError):
        normalize_innings_deliveries(raw_match_data, "1529229", 5)


def test_normalize_innings_missing_over_index():
    """Missing 'over' key raises MissingCriticalFieldError."""
    bad_data = {
        "innings": [{"overs": [{"deliveries": []}]}]
    }
    with pytest.raises(MissingCriticalFieldError):
        normalize_innings_deliveries(bad_data, "test", 0)


def test_normalize_innings_missing_runs():
    """Missing delivery runs raises MissingCriticalFieldError."""
    bad_data = {
        "innings": [
            {
                "overs": [
                    {
                        "over": 0,
                        "deliveries": [{"batter": "A", "bowler": "B"}],
                    }
                ]
            }
        ]
    }
    with pytest.raises(MissingCriticalFieldError):
        normalize_innings_deliveries(bad_data, "test", 0)


def test_normalize_innings_delivery_arithmetic_mismatch():
    """Mismatch between batter + extras != total raises CricsheetDeliveryArithmeticError."""
    bad_data = {
        "innings": [
            {
                "overs": [
                    {
                        "over": 0,
                        "deliveries": [
                            {
                                "batter": "A",
                                "bowler": "B",
                                "runs": {"batter": 2, "extras": 1, "total": 4},  # 2 + 1 != 4
                            }
                        ],
                    }
                ]
            }
        ]
    }
    with pytest.raises(CricsheetDeliveryArithmeticError):
        normalize_innings_deliveries(bad_data, "test", 0)


def test_normalize_innings_legal_vs_illegal_deliveries():
    """Wides and no-balls must have legal_ball_number = 0, legal balls 1-6."""
    mock_data = {
        "innings": [
            {
                "overs": [
                    {
                        "over": 0,
                        "deliveries": [
                            # Legal ball 1
                            {"batter": "A", "bowler": "B", "runs": {"batter": 0, "extras": 0, "total": 0}},
                            # Wide (illegal)
                            {
                                "batter": "A",
                                "bowler": "B",
                                "runs": {"batter": 0, "extras": 1, "total": 1},
                                "extras": {"wides": 1},
                            },
                            # Legal ball 2
                            {"batter": "A", "bowler": "B", "runs": {"batter": 4, "extras": 0, "total": 4}},
                        ],
                    }
                ]
            }
        ]
    }
    events = normalize_innings_deliveries(mock_data, "test_match", 0)
    assert len(events) == 3
    assert events[0].legal_ball_number == 1
    assert events[1].legal_ball_number == 0  # Wide
    assert events[2].legal_ball_number == 2  # Advances legal count to 2


def test_normalize_innings_string_fielder():
    """Dismissal with string fielder instead of dict must be normalized correctly."""
    mock_data = {
        "innings": [
            {
                "overs": [
                    {
                        "over": 0,
                        "deliveries": [
                            {
                                "batter": "A",
                                "bowler": "B",
                                "runs": {"batter": 0, "extras": 0, "total": 0},
                                "wickets": [
                                    {
                                        "player_out": "A",
                                        "kind": "caught",
                                        "fielders": ["Fielder Name"],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ]
    }
    events = normalize_innings_deliveries(mock_data, "test_match", 0)
    assert events[0].wickets[0].fielders == ["Fielder Name"]
