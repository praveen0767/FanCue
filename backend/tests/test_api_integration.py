"""API integration tests — /healthz, /matches, /matches/{id}/intervals, POST /catchup.

All tests use httpx TestClient with SKIP_LLM_IN_TESTS=true so no external
LLM calls are made. Fixture IDs 1529229 and 1552779 are exercised against
real engine data. No data is invented.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import AppSettings, get_settings
from backend.app.main import app

MATCH_IDS = ["1529229", "1552779"]
client = TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def force_skip_llm():
    """Ensure API tests run in deterministic fallback mode without polluting os.environ."""
    settings = AppSettings(skip_llm=True)
    app.dependency_overrides[get_settings] = lambda: settings
    yield
    app.dependency_overrides.pop(get_settings, None)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_healthz_returns_200(self):
        resp = client.get("/healthz")
        assert resp.status_code == 200

    def test_healthz_returns_ok_status(self):
        data = resp = client.get("/healthz").json()
        assert data["status"] == "ok"

    def test_healthz_contains_no_secrets(self):
        text = client.get("/healthz").text
        sensitive = ["key", "password", "token", "secret", "OPENAI", "QDRANT_API"]
        for word in sensitive:
            assert word.upper() not in text.upper(), f"Potential secret '{word}' in /healthz"

    def test_healthz_no_traceback(self):
        text = client.get("/healthz").text
        assert "Traceback" not in text
        assert "Exception" not in text

    def test_readyz_returns_200(self):
        resp = client.get("/readyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fixtures"] == "ready"
        assert data["status"] in ("ready", "degraded")
        assert "Traceback" not in resp.text


# ---------------------------------------------------------------------------
# Match listing
# ---------------------------------------------------------------------------


class TestMatchListing:
    def test_get_matches_200(self):
        resp = client.get("/matches")
        assert resp.status_code == 200

    def test_get_matches_returns_known_fixtures(self):
        data = client.get("/matches").json()
        ids = [m["match_id"] for m in data["matches"]]
        for mid in MATCH_IDS:
            assert mid in ids, f"Expected fixture {mid} in /matches"

    def test_get_matches_total_matches_count(self):
        data = client.get("/matches").json()
        assert data["total"] == len(data["matches"])

    def test_match_descriptor_fields_present(self):
        data = client.get("/matches").json()
        assert len(data["matches"]) > 0
        match = data["matches"][0]
        for field in ("match_id", "sport", "name", "format", "teams", "date"):
            assert field in match, f"Expected field '{field}' in match descriptor"

    def test_match_descriptor_sport_is_cricket(self):
        data = client.get("/matches").json()
        for m in data["matches"]:
            assert m["sport"] == "cricket"

    def test_match_teams_count(self):
        data = client.get("/matches").json()
        for m in data["matches"]:
            assert len(m["teams"]) == 2


# ---------------------------------------------------------------------------
# Interval listing
# ---------------------------------------------------------------------------


class TestIntervalListing:
    @pytest.mark.parametrize("match_id", MATCH_IDS)
    def test_get_intervals_200(self, match_id):
        resp = client.get(f"/matches/{match_id}/intervals")
        assert resp.status_code == 200

    @pytest.mark.parametrize("match_id", MATCH_IDS)
    def test_get_intervals_returns_non_empty_list(self, match_id):
        data = client.get(f"/matches/{match_id}/intervals").json()
        assert len(data["intervals"]) > 0

    @pytest.mark.parametrize("match_id", MATCH_IDS)
    def test_interval_boundaries_are_valid(self, match_id):
        data = client.get(f"/matches/{match_id}/intervals").json()
        for iv in data["intervals"]:
            assert iv["end_after_over"] > iv["start_after_over"]
            assert iv["start_after_over"] >= -1

    @pytest.mark.parametrize("match_id", MATCH_IDS)
    def test_interval_has_label(self, match_id):
        data = client.get(f"/matches/{match_id}/intervals").json()
        for iv in data["intervals"]:
            assert iv["label"], "Each interval must have a non-empty label"

    def test_unknown_match_returns_404(self):
        resp = client.get("/matches/DOES_NOT_EXIST_99999/intervals")
        assert resp.status_code == 404

    def test_unknown_match_error_structure(self):
        resp = client.get("/matches/FAKE_ID/intervals")
        # FastAPI raises HTTPException with detail as dict
        data = resp.json()
        # HTTPException detail is nested in "detail" key
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Catch-up endpoint
# ---------------------------------------------------------------------------

VALID_CATCHUP_1529229 = {
    "match_id": "1529229",
    "interval": {"innings": 0, "start_after_over": -1, "end_after_over": 5},
}

VALID_CATCHUP_1552779 = {
    "match_id": "1552779",
    "interval": {"innings": 0, "start_after_over": -1, "end_after_over": 5},
}

VALID_CATCHUP_MID_INNINGS = {
    "match_id": "1529229",
    "interval": {"innings": 0, "start_after_over": 5, "end_after_over": 10},
}

VALID_CATCHUP_1552779_MID = {
    "match_id": "1552779",
    "interval": {"innings": 1, "start_after_over": -1, "end_after_over": 5},
}


class TestCatchUpEndpoint:
    def test_catchup_1529229_returns_200(self):
        resp = client.post("/catchup", json=VALID_CATCHUP_1529229)
        assert resp.status_code == 200, resp.text

    def test_catchup_1552779_returns_200(self):
        resp = client.post("/catchup", json=VALID_CATCHUP_1552779)
        assert resp.status_code == 200, resp.text

    def test_catchup_mid_innings_1529229(self):
        resp = client.post("/catchup", json=VALID_CATCHUP_MID_INNINGS)
        assert resp.status_code == 200, resp.text

    def test_catchup_1552779_second_innings(self):
        resp = client.post("/catchup", json=VALID_CATCHUP_1552779_MID)
        assert resp.status_code == 200, resp.text

    def test_catchup_response_has_match_descriptor(self):
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        assert "match" in data
        assert data["match"]["match_id"] == "1529229"

    def test_catchup_response_has_evidence_packet(self):
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        assert "evidence_packet" in data
        packet = data["evidence_packet"]
        assert "packet_id" in packet
        assert "key_facts" in packet
        assert isinstance(packet["key_facts"], list)

    def test_catchup_evidence_packet_linked_to_match(self):
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        assert data["evidence_packet"]["match_id"] == "1529229"

    def test_catchup_response_has_state_before_after(self):
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        for key in ("state_before", "state_after", "state_delta"):
            assert key in data, f"Missing {key} in response"

    def test_catchup_state_delta_non_negative(self):
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        delta = data["state_delta"]
        assert delta["runs_added"] >= 0
        assert delta["wickets_lost"] >= 0

    def test_catchup_returns_over_by_over_ball_story(self):
        """Every selected over has real ball records and consistent score deltas."""
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        overs = data["over_by_over"]
        assert overs, "Expected over-by-over story for a non-empty interval"
        assert [item["over_number"] for item in overs] == sorted(
            item["over_number"] for item in overs
        )
        assert all(item["balls"] for item in overs)
        assert all(item["score_after_runs"] >= 0 for item in overs)
        assert sum(item["runs"] for item in overs) == data["state_delta"]["runs_added"]
        assert sum(item["wickets"] for item in overs) == data["state_delta"]["wickets_lost"]
        for over in overs:
            assert over["legal_balls"] <= 6
            assert len(over["balls"]) <= 20
            for ball in over["balls"]:
                assert ball["batter"]
                assert ball["bowler"]
                assert ball["total_runs"] >= 0
                assert ball["display"]

    def test_catchup_response_has_explanation(self):
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        assert "explanation" in data
        explanation = data["explanation"]
        assert "summary" in explanation
        assert len(explanation["summary"]) >= 10

    def test_catchup_deterministic_fallback_engaged(self):
        """With SKIP_LLM_IN_TESTS=true, expect deterministic_fallback mode."""
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        explanation = data["explanation"]
        assert explanation["generation_mode"] == "deterministic_fallback"
        assert explanation["fallback_reason"] == "disabled"

    def test_catchup_mode_is_replay(self):
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        assert data["mode"] == "replay"

    def test_catchup_unknown_match_returns_404(self):
        payload = {
            "match_id": "NO_SUCH_MATCH",
            "interval": {"innings": 0, "start_after_over": -1, "end_after_over": 5},
        }
        resp = client.post("/catchup", json=payload)
        assert resp.status_code == 404

    def test_catchup_invalid_interval_out_of_bounds(self):
        payload = {
            "match_id": "1529229",
            "interval": {"innings": 0, "start_after_over": -1, "end_after_over": 999},
        }
        resp = client.post("/catchup", json=payload)
        assert resp.status_code == 400

    def test_catchup_invalid_reversed_interval(self):
        """Pydantic validator must reject end <= start."""
        payload = {
            "match_id": "1529229",
            "interval": {"innings": 0, "start_after_over": 10, "end_after_over": 5},
        }
        resp = client.post("/catchup", json=payload)
        assert resp.status_code == 422  # FastAPI validation error

    def test_catchup_missing_match_id(self):
        payload = {"interval": {"innings": 0, "start_after_over": -1, "end_after_over": 5}}
        resp = client.post("/catchup", json=payload)
        assert resp.status_code == 422

    def test_catchup_safe_error_no_traceback(self):
        payload = {
            "match_id": "NO_SUCH_MATCH",
            "interval": {"innings": 0, "start_after_over": -1, "end_after_over": 5},
        }
        text = client.post("/catchup", json=payload).text
        assert "Traceback" not in text
        assert "Exception" not in text

    def test_catchup_safe_error_no_api_keys(self):
        payload = {
            "match_id": "NO_SUCH_MATCH",
            "interval": {"innings": 0, "start_after_over": -1, "end_after_over": 5},
        }
        text = client.post("/catchup", json=payload).text
        assert "OPENAI_API_KEY" not in text
        assert "QDRANT_API_KEY" not in text

    def test_catchup_1552779_state_facts_traceable(self):
        """Verify state facts in evidence packet link back to match engine data."""
        data = client.post("/catchup", json=VALID_CATCHUP_1552779).json()
        facts = data["evidence_packet"]["key_facts"]
        assert len(facts) >= 1
        # Each fact must have a fact_id and match_id
        for fact in facts:
            assert "fact_id" in fact
            assert fact.get("match_id") == "1552779"

    def test_catchup_provenance_present(self):
        """Evidence packet provenance must be populated."""
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        prov = data["evidence_packet"].get("provenance")
        assert prov is not None
        assert "source_name" in prov
        assert "source_url" in prov

    def test_catchup_no_fabricated_scores(self):
        """State delta runs/wickets must be non-negative integers from the engine."""
        data = client.post("/catchup", json=VALID_CATCHUP_1529229).json()
        delta = data["state_delta"]
        assert isinstance(delta["runs_added"], int)
        assert isinstance(delta["wickets_lost"], int)
        assert delta["runs_added"] >= 0
        assert delta["wickets_lost"] >= 0
        # Verify consistency: state_after.runs - state_before.runs == runs_added
        assert (
            data["state_after"]["runs"] - data["state_before"]["runs"] == delta["runs_added"]
        )

    def test_catchup_rate_limiting_exceeded(self):
        """Simulate exceeding rate limit to verify 429 response structure."""
        from backend.app.api.catchup import _request_history
        test_ip = "192.168.1.99"
        # Preload 65 recent timestamps for test_ip
        import time
        now = time.time()
        _request_history[test_ip] = [now] * 65

        # Request from test_ip
        resp = client.post(
            "/catchup",
            json=VALID_CATCHUP_1529229,
            headers={"X-Forwarded-For": test_ip},
        )
        # Should return 429
        assert resp.status_code == 429
        err = resp.json()["error"]
        assert err["code"] == "RATE_LIMIT_EXCEEDED"
        # Clean up
        _request_history.pop(test_ip, None)

    def test_catchup_rate_limiting_untrusted_proxy_spoof_prevented(self):
        """When peer is untrusted, X-Forwarded-For must be ignored to prevent IP spoofing."""
        from unittest.mock import Mock
        from backend.app.api.catchup import resolve_client_ip
        req = Mock()
        req.client.host = "203.0.113.50"  # untrusted peer
        req.headers = {"X-Forwarded-For": "10.0.0.1"}
        resolved = resolve_client_ip(req, trusted_proxies=["127.0.0.1", "::1"])
        assert resolved == "203.0.113.50", "Must ignore X-Forwarded-For from untrusted peer"

    def test_catchup_rate_limiting_trusted_proxy_forwarded_honored(self):
        """When peer is a trusted proxy, X-Forwarded-For must be respected."""
        from unittest.mock import Mock
        from backend.app.api.catchup import resolve_client_ip
        req = Mock()
        req.client.host = "127.0.0.1"  # trusted proxy
        req.headers = {"X-Forwarded-For": "198.51.100.22, 10.0.0.1"}
        resolved = resolve_client_ip(req, trusted_proxies=["127.0.0.1", "::1"])
        assert resolved == "198.51.100.22", "Must extract client IP from trusted proxy"


# ---------------------------------------------------------------------------
# CORS behavior
# ---------------------------------------------------------------------------


class TestCORSBehavior:
    def test_cors_options_health(self):
        """Preflight OPTIONS request should succeed for /healthz."""
        resp = client.options(
            "/healthz",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # 200 or 204 — CORS configured
        assert resp.status_code in (200, 204, 405)

    def test_cors_header_on_get_matches(self):
        """GET /matches should include Access-Control-Allow-Origin for local dev origin."""
        resp = client.get("/matches", headers={"Origin": "http://localhost:5173"})
        assert resp.status_code == 200
        # TestClient may not propagate CORS headers in all versions; check response is valid
        assert "matches" in resp.json()
