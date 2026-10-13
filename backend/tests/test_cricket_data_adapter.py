"""Tests for Cricket Data API adapter, normalization, caching, and rate limiting.

No external network calls are made during tests. All HTTP responses are mocked.
API keys and secrets are never logged or leaked.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.adapters.cricket_data.client import CricketDataClient
from backend.app.adapters.cricket_data.models import (
    CricketDataMatchItem,
    CricketDataMatchesResponse,
)
from backend.app.adapters.cricket_data.normalizer import (
    normalize_match_item,
    parse_innings_score,
)
from backend.app.main import app

client = TestClient(app)

# Sanitized mock response for currentMatches
MOCK_CURRENT_MATCHES_RAW = {
    "apikey": "REPLACE_MOCK_KEY",
    "data": [
        {
            "id": "match-uuid-ind-aus-001",
            "name": "India vs Australia, 1st ODI",
            "matchType": "odi",
            "status": "India won by 5 wickets",
            "venue": "Wankhede Stadium, Mumbai",
            "date": "2026-10-13",
            "dateTimeGMT": "2026-10-13T08:30:00",
            "teams": ["India", "Australia"],
            "teamInfo": [
                {"name": "India", "shortname": "IND", "img": "https://example.com/ind.png"},
                {"name": "Australia", "shortname": "AUS", "img": "https://example.com/aus.png"},
            ],
            "score": [
                {"r": 276, "w": 10, "o": 49.2, "inning": "Australia Inning 1"},
                {"r": 280, "w": 5, "o": 48.4, "inning": "India Inning 1"},
            ],
            "series_id": "series-uuid-001",
            "matchStarted": True,
            "matchEnded": True,
        },
        {
            "id": "match-uuid-eng-pak-002",
            "name": "England vs Pakistan, 2nd T20I",
            "matchType": "t20",
            "status": "Innings Break",
            "venue": "Old Trafford, Manchester",
            "date": "2026-10-13",
            "dateTimeGMT": "2026-10-13T17:00:00",
            "teams": ["England", "Pakistan"],
            "teamInfo": [
                {"name": "England", "shortname": "ENG"},
                {"name": "Pakistan", "shortname": "PAK"},
            ],
            "score": [
                {"r": 185, "w": 6, "o": 20.0, "inning": "Pakistan Inning 1"},
            ],
            "series_id": "series-uuid-002",
            "matchStarted": True,
            "matchEnded": False,
        },
    ],
    "info": {
        "hitsToday": 12,
        "hitsLeft": 88,
        "serverTime": 1.2,
    },
    "status": "success",
}

# Sanitized mock response for match_scorecard
MOCK_SCORECARD_RAW = {
    "apikey": "REPLACE_MOCK_KEY",
    "data": {
        "id": "match-uuid-ind-aus-001",
        "name": "India vs Australia, 1st ODI",
        "matchType": "odi",
        "status": "India won by 5 wickets",
        "venue": "Wankhede Stadium, Mumbai",
        "date": "2026-10-13",
        "dateTimeGMT": "2026-10-13T08:30:00",
        "teams": ["India", "Australia"],
        "score": [
            {"r": 276, "w": 10, "o": 49.2, "inning": "Australia Inning 1"},
            {"r": 280, "w": 5, "o": 48.4, "inning": "India Inning 1"},
        ],
        "matchStarted": True,
        "matchEnded": True,
        "scorecard": {
            "innings": [
                {"name": "Australia Inning 1", "runs": 276, "wickets": 10},
                {"name": "India Inning 1", "runs": 280, "wickets": 5},
            ]
        },
    },
    "info": {
        "hitsToday": 13,
        "hitsLeft": 87,
    },
    "status": "success",
}


class MockTransport(httpx.BaseTransport):
    """Mock HTTP transport returning controlled responses."""

    def __init__(self, handler):
        self.handler = handler

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self.handler(request)


# ---------------------------------------------------------------------------
# Test Normalization
# ---------------------------------------------------------------------------


def test_parse_innings_score_valid():
    raw = {"r": 165, "w": 4, "o": 18.2, "inning": "India Inning 1"}
    score = parse_innings_score(raw)
    assert score is not None
    assert score.r == 165
    assert score.w == 4
    assert score.o == 18.2
    assert score.inning == "India Inning 1"


def test_parse_innings_score_corrupt_types():
    raw = {"r": "not-a-number", "w": None, "o": "12.4", "inning": ""}
    score = parse_innings_score(raw)
    assert score is not None
    assert score.r == 0
    assert score.w == 0
    assert score.o == 12.4
    assert score.inning == ""


def test_normalize_match_item_full():
    raw = MOCK_CURRENT_MATCHES_RAW["data"][0]
    match = normalize_match_item(raw, retrieved_at="2026-10-13T10:00:00Z")
    assert match is not None
    assert match.id == "match-uuid-ind-aus-001"
    assert match.name == "India vs Australia, 1st ODI"
    assert match.match_type == "odi"
    assert match.status == "India won by 5 wickets"
    assert match.venue == "Wankhede Stadium, Mumbai"
    assert len(match.teams) == 2
    assert len(match.score) == 2
    assert match.score[0].r == 276
    assert match.score[1].r == 280
    assert match.match_started is True
    assert match.match_ended is True
    assert match.source == "CricketData.org"
    assert "Near-live" in match.freshness


def test_normalize_match_item_missing_id():
    raw = {"name": "No ID Match", "teams": ["Team A", "Team B"]}
    match = normalize_match_item(raw, retrieved_at="2026-10-13T10:00:00Z")
    assert match is None


def test_normalize_match_item_missing_name_fallback_to_teams():
    raw = {"id": "123", "teams": ["Team Alpha", "Team Beta"], "matchType": "t20"}
    match = normalize_match_item(raw, retrieved_at="2026-10-13T10:00:00Z")
    assert match is not None
    assert match.name == "Team Alpha vs Team Beta"


# ---------------------------------------------------------------------------
# Test Client Lifecycle, Caching & Rate Limiting
# ---------------------------------------------------------------------------


def test_unconfigured_client():
    client = CricketDataClient(api_key=None)
    assert client.is_configured is False
    resp = client.get_current_matches()
    assert resp.status == "unconfigured"
    assert resp.configured is False
    assert resp.total == 0
    assert "not configured" in (resp.message or "")


def test_placeholder_key_is_unconfigured():
    client = CricketDataClient(api_key="REPLACE_WITH_YOUR_KEY")
    assert client.is_configured is False
    resp = client.get_current_matches()
    assert resp.status == "unconfigured"


def test_caching_and_quota_tracking():
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=MOCK_CURRENT_MATCHES_RAW)

    mock_client = httpx.Client(transport=MockTransport(mock_handler))
    adapter = CricketDataClient(
        api_key="valid-test-key-12345",
        http_client=mock_client,
        cache_ttl=60,
    )

    # First call: makes network request
    resp1 = adapter.get_current_matches()
    assert resp1.status == "success"
    assert resp1.cached is False
    assert resp1.total == 2
    assert resp1.hits_today == 12
    assert resp1.hits_left == 88
    assert call_count == 1

    # Second call within TTL: served from cache without HTTP request
    resp2 = adapter.get_current_matches()
    assert resp2.status == "success"
    assert resp2.cached is True
    assert resp2.total == 2
    assert call_count == 1

    # Force refresh: bypasses cache and makes second HTTP request
    resp3 = adapter.get_current_matches(force_refresh=True)
    assert resp3.status == "success"
    assert resp3.cached is False
    assert call_count == 2


def test_rate_limit_handling():
    rate_limit_payload = {
        "status": "failure",
        "reason": "You have exhausted your daily limit of 100 requests.",
        "info": {"hitsToday": 100, "hitsLeft": 0},
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=rate_limit_payload)

    mock_client = httpx.Client(transport=MockTransport(mock_handler))
    adapter = CricketDataClient(
        api_key="valid-test-key-12345",
        http_client=mock_client,
    )

    resp = adapter.get_current_matches()
    assert resp.status == "error"
    assert "limit" in (resp.message or "").lower()
    assert resp.hits_left == 0


def test_timeout_handling_graceful():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out")

    mock_client = httpx.Client(transport=MockTransport(mock_handler))
    adapter = CricketDataClient(
        api_key="valid-test-key-12345",
        http_client=mock_client,
    )

    resp = adapter.get_current_matches()
    assert resp.status == "error"
    assert "timed out" in (resp.message or "").lower()


def test_scorecard_retrieval_and_disclaimer():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=MOCK_SCORECARD_RAW)

    mock_client = httpx.Client(transport=MockTransport(mock_handler))
    adapter = CricketDataClient(
        api_key="valid-test-key-12345",
        http_client=mock_client,
    )

    resp = adapter.get_match_scorecard("match-uuid-ind-aus-001")
    assert resp.status == "success"
    assert resp.match is not None
    assert resp.match.id == "match-uuid-ind-aus-001"
    assert resp.can_reconstruct_interval is False
    assert "ball-by-ball delivery ledger" in resp.limitation_reason.lower()


# ---------------------------------------------------------------------------
# Test API Router & Source Separation
# ---------------------------------------------------------------------------


def test_get_near_live_matches_endpoint(monkeypatch):
    mock_client = CricketDataClient(
        api_key="valid-mock-key",
        http_client=httpx.Client(transport=MockTransport(lambda req: httpx.Response(200, json=MOCK_CURRENT_MATCHES_RAW))),
    )
    monkeypatch.setattr("backend.app.api.matches.get_cricket_data_client", lambda: mock_client)
    resp = client.get("/matches/near-live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["configured"] is True
    assert len(data["matches"]) == 2


def test_get_near_live_scorecard_endpoint(monkeypatch):
    mock_client = CricketDataClient(
        api_key="valid-mock-key",
        http_client=httpx.Client(transport=MockTransport(lambda req: httpx.Response(200, json=MOCK_SCORECARD_RAW))),
    )
    monkeypatch.setattr("backend.app.api.matches.get_cricket_data_client", lambda: mock_client)
    resp = client.get("/matches/near-live/match-uuid-ind-aus-001/scorecard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["can_reconstruct_interval"] is False
    assert "ball-by-ball delivery ledger" in data["limitation_reason"].lower()


def test_get_near_live_matches_unconfigured(monkeypatch):
    mock_client = CricketDataClient(api_key=None)
    monkeypatch.setattr("backend.app.api.matches.get_cricket_data_client", lambda: mock_client)
    resp = client.get("/matches/near-live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unconfigured"
    assert data["configured"] is False


def test_source_separation_historical_matches():
    """Verify that /matches returns only historical Cricsheet fixtures."""
    resp = client.get("/matches")
    assert resp.status_code == 200
    data = resp.json()
    # IDs should only be Cricsheet fixtures (e.g. 1529229, 1552779)
    for m in data["matches"]:
        assert m["source_id"].startswith("cricsheet_")
        assert m["mode"] == "replay"


def test_redact_api_url_redacts_keys():
    from backend.app.adapters.cricket_data.client import redact_api_url

    secret_key = "cd1b1f4b-ea51-45f1-becb-f9663996a844"
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={secret_key}&offset=0"
    redacted = redact_api_url(url)
    assert secret_key not in redacted
    assert "apikey=[REDACTED]" in redacted

    url2 = f"https://api.cricapi.com/v1/match_info?id=123&apikey={secret_key}"
    redacted2 = redact_api_url(url2)
    assert secret_key not in redacted2
    assert "apikey=[REDACTED]" in redacted2

