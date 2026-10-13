"""Match engine package exporting CricketMatchEngine, state calculations, and interval tools."""

from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.match_engine.errors import (
    InningsIndexOutOfBoundsError,
    InvalidIntervalError,
    MatchEngineError,
    OverBoundaryNotFoundError,
    ReconciliationError,
)
from backend.app.match_engine.intervals import (
    extract_key_facts,
    filter_interval_deliveries,
    NON_BOWLER_CREDITED_DISMISSALS,
)
from backend.app.match_engine.state import (
    calculate_state_delta,
    calculate_state_snapshot,
    calculate_final_innings_snapshot,
)

__all__ = [
    "CricketMatchEngine",
    "calculate_state_snapshot",
    "calculate_state_delta",
    "calculate_final_innings_snapshot",
    "filter_interval_deliveries",
    "extract_key_facts",
    "NON_BOWLER_CREDITED_DISMISSALS",
    "MatchEngineError",
    "InvalidIntervalError",
    "InningsIndexOutOfBoundsError",
    "OverBoundaryNotFoundError",
    "ReconciliationError",
]
