"""Cricket Data API adapter package (cricketdata.org / cricapi.com).

Provides bounded, cached, rate-limited near-live cricket match discovery
and scorecard retrieval. Completely separated from authoritative historical Cricsheet fixtures.
"""

from backend.app.adapters.cricket_data.models import (
    CricketDataMatchItem,
    CricketDataMatchesResponse,
    CricketDataScorecardResponse,
    CricketDataInningsScore,
)
from backend.app.adapters.cricket_data.client import CricketDataClient, get_cricket_data_client

__all__ = [
    "CricketDataMatchItem",
    "CricketDataMatchesResponse",
    "CricketDataScorecardResponse",
    "CricketDataInningsScore",
    "CricketDataClient",
    "get_cricket_data_client",
]
