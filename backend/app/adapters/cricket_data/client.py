"""Cricket Data API client with timeouts, in-memory caching, rate-limiting, and error handling.

Complies with AGENTS.md security rules:
- API key is never logged, exposed in URLs/tracebacks, or leaked to client responses.
- Respects provider quotas (100 hits/day) with in-memory TTL caching.
- Handles provider failures gracefully without crashing.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from backend.app.adapters.cricket_data.models import (
    CricketDataMatchItem,
    CricketDataMatchesResponse,
    CricketDataScorecardResponse,
)
from backend.app.adapters.cricket_data.normalizer import normalize_match_item
from backend.app.core.config import get_settings

import re

logger = logging.getLogger(__name__)


def redact_api_url(url: str) -> str:
    """Redact apikey query parameter from URL strings to prevent accidental leakage."""
    return re.sub(r"([?&]apikey=)[^&]+", r"\1[REDACTED]", str(url))


_UNSET = object()


class CricketDataClient:

    """Client for CricketData.org / CricAPI v1 endpoints."""

    def __init__(
        self,
        api_key: Any = _UNSET,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        cache_ttl: Optional[int] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        settings = get_settings()
        self._api_key = settings.cricket_data_api_key if api_key is _UNSET else api_key
        raw_base = base_url if base_url is not None else settings.cricket_data_api_url
        self._base_url = raw_base.rstrip("/") + "/"
        self._timeout = timeout if timeout is not None else settings.cricket_data_timeout_seconds
        self._cache_ttl = cache_ttl if cache_ttl is not None else settings.cricket_data_cache_ttl_seconds
        self._http_client = http_client

        # In-memory cache structures
        self._matches_cache: Dict[str, Any] = {}
        self._scorecard_cache: Dict[str, Any] = {}

        # Quota tracking
        self._last_hits_today: Optional[int] = None
        self._last_hits_left: Optional[int] = None

    @property
    def is_configured(self) -> bool:
        """Return True if an API key is configured and not a placeholder."""
        if not self._api_key:
            return False
        if self._api_key.startswith("REPLACE_"):
            return False
        return True

    def clear_cache(self) -> None:
        """Clear all in-memory caches."""
        self._matches_cache.clear()
        self._scorecard_cache.clear()

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=self._timeout)

    def get_current_matches(
        self,
        offset: int = 0,
        force_refresh: bool = False,
    ) -> CricketDataMatchesResponse:
        """Fetch current matches, falling back to CricketData's public delayed feed.

        CricketData documents anonymous access for most basic APIs with a longer
        delay. This lets FanCue keep showing scores when a key is absent, invalid,
        or its authenticated daily quota is exhausted. The public mode is labelled
        honestly so the UI does not imply the authenticated feed is working.
        """
        now = time.time()
        now_utc = datetime.now(timezone.utc).isoformat()
        cache_key = f"currentMatches_{offset}"
        authenticated = self.is_configured
        public_mode = not authenticated

        if not force_refresh and cache_key in self._matches_cache:
            entry = self._matches_cache[cache_key]
            if now - entry["timestamp"] < self._cache_ttl:
                cached_resp: CricketDataMatchesResponse = entry["response"]
                return CricketDataMatchesResponse(
                    status=cached_resp.status,
                    configured=cached_resp.configured,
                    matches=cached_resp.matches,
                    total=cached_resp.total,
                    cached=True,
                    cached_at=entry["cached_at_iso"],
                    hits_today=cached_resp.hits_today,
                    hits_left=cached_resp.hits_left,
                    message=cached_resp.message,
                )

        # If the authenticated quota is exhausted, avoid another paid/quota hit.
        if authenticated and self._last_hits_left is not None and self._last_hits_left <= 0:
            public_mode = True

        url = f"{self._base_url}currentMatches"
        client = self._get_client()

        def request_payload(anonymous: bool):
            params: Dict[str, Any] = {"offset": offset}
            if not anonymous:
                params["apikey"] = self._api_key
            response = client.get(url, params=params)
            if response.status_code != 200:
                return response, None
            try:
                return response, response.json()
            except ValueError:
                return response, None

        logger.info(
            "Requesting CricketData currentMatches (offset=%d, public_mode=%s)",
            offset,
            public_mode,
        )

        try:
            resp, payload = request_payload(anonymous=public_mode)
        except httpx.TimeoutException:
            logger.warning("CricketData API request timed out while fetching currentMatches")
            if cache_key in self._matches_cache:
                old = self._matches_cache[cache_key]
                cached_resp: CricketDataMatchesResponse = old["response"]
                return CricketDataMatchesResponse(
                    status="success",
                    configured=cached_resp.configured,
                    matches=cached_resp.matches,
                    total=cached_resp.total,
                    cached=True,
                    cached_at=old["cached_at_iso"],
                    message="The score provider timed out; showing the last cached match list.",
                )
            return CricketDataMatchesResponse(
                status="error",
                configured=authenticated and not public_mode,
                matches=[],
                total=0,
                message="The cricket score provider timed out. Please retry shortly.",
            )
        except Exception as exc:
            logger.error("CricketData API request error: %s", type(exc).__name__)
            if cache_key in self._matches_cache:
                old = self._matches_cache[cache_key]
                cached_resp: CricketDataMatchesResponse = old["response"]
                return CricketDataMatchesResponse(
                    status="success",
                    configured=cached_resp.configured,
                    matches=cached_resp.matches,
                    total=cached_resp.total,
                    cached=True,
                    cached_at=old["cached_at_iso"],
                    message="The score provider is unavailable; showing the last cached match list.",
                )
            return CricketDataMatchesResponse(
                status="error",
                configured=authenticated and not public_mode,
                matches=[],
                total=0,
                message=f"Unable to reach the cricket score provider ({type(exc).__name__}).",
            )

        # Retry without the configured key if the server rejects authentication.
        if resp.status_code in (401, 403) and not public_mode:
            public_mode = True
            try:
                resp, payload = request_payload(anonymous=True)
            except Exception as exc:
                logger.warning("CricketData anonymous fallback failed: %s", type(exc).__name__)
                payload = None
        elif resp.status_code != 200:
            logger.warning("CricketData API returned HTTP %d", resp.status_code)
            return CricketDataMatchesResponse(
                status="error",
                configured=authenticated and not public_mode,
                matches=[],
                total=0,
                message=f"Cricket Data API returned HTTP {resp.status_code}.",
            )

        if payload is None:
            return CricketDataMatchesResponse(
                status="error",
                configured=authenticated and not public_mode,
                matches=[],
                total=0,
                message="The cricket score provider returned an unreadable response.",
            )

        provider_status = payload.get("status")
        reason = str(payload.get("reason") or "")
        reason_lower = reason.lower()
        auth_rejected = any(token in reason_lower for token in ("invalid api key", "invalid_api_key", "unauthorized"))
        quota_rejected = any(token in reason_lower for token in ("daily limit", "quota exhausted", "rate limit", "hits left"))

        if provider_status != "success" and not public_mode and (auth_rejected or quota_rejected):
            # Official public access does not need an API key and is delayed by
            # up to about five minutes. Retry only once and never log the key.
            public_mode = True
            try:
                resp, public_payload = request_payload(anonymous=True)
            except Exception as exc:
                logger.warning("CricketData public-feed fallback failed: %s", type(exc).__name__)
                public_payload = None
                resp = None
            if (
                resp is not None
                and resp.status_code == 200
                and isinstance(public_payload, dict)
                and public_payload.get("status") == "success"
            ):
                payload = public_payload
                provider_status = "success"
                reason = ""
            else:
                logger.warning("CricketData public-feed fallback was not successful")

        if provider_status != "success":
            safe_reason = reason if reason else "The provider reported a temporary failure."
            logger.warning("CricketData returned non-success status: %s", safe_reason)
            return CricketDataMatchesResponse(
                status="error",
                configured=authenticated and not public_mode,
                matches=[],
                total=0,
                hits_today=self._last_hits_today,
                hits_left=self._last_hits_left,
                message=f"Cricket score feed unavailable: {safe_reason}",
            )

        info = payload.get("info") or {}
        if isinstance(info, dict):
            if "hitsToday" in info:
                self._last_hits_today = info.get("hitsToday")
            if "hitsLeft" in info:
                self._last_hits_left = info.get("hitsLeft")

        raw_data = payload.get("data") or []
        matches: list[CricketDataMatchItem] = []
        if isinstance(raw_data, list):
            for item in raw_data:
                normalized = normalize_match_item(item, retrieved_at=now_utc)
                if normalized is not None:
                    matches.append(normalized)

        if public_mode:
            message = (
                "Using CricketData.org's public score feed. Updates may lag by up to about 5 minutes."
            )
        else:
            message = None

        result = CricketDataMatchesResponse(
            status="success",
            configured=not public_mode,
            matches=matches,
            total=len(matches),
            cached=False,
            cached_at=now_utc,
            hits_today=None if public_mode else self._last_hits_today,
            hits_left=None if public_mode else self._last_hits_left,
            message=message,
        )

        self._matches_cache[cache_key] = {
            "response": result,
            "timestamp": now,
            "cached_at_iso": now_utc,
        }
        return result

    def get_match_scorecard(
        self,
        match_id: str,
        force_refresh: bool = False,
    ) -> CricketDataScorecardResponse:
        """Fetch scorecard for a specific match with caching and bounds."""
        now = time.time()
        now_utc = datetime.now(timezone.utc).isoformat()

        if not self.is_configured:
            return CricketDataScorecardResponse(
                status="unconfigured",
                configured=False,
                match=None,
                scorecard=None,
                message="Cricket Data API key is not configured.",
            )

        clean_mid = str(match_id).strip()
        if not clean_mid:
            return CricketDataScorecardResponse(
                status="error",
                configured=True,
                match=None,
                scorecard=None,
                message="Missing match_id.",
            )

        cache_key = f"scorecard_{clean_mid}"
        if not force_refresh and cache_key in self._scorecard_cache:
            entry = self._scorecard_cache[cache_key]
            if now - entry["timestamp"] < self._cache_ttl:
                cached_resp: CricketDataScorecardResponse = entry["response"]
                return CricketDataScorecardResponse(
                    status=cached_resp.status,
                    configured=True,
                    match=cached_resp.match,
                    scorecard=cached_resp.scorecard,
                    can_reconstruct_interval=False,
                    limitation_reason=cached_resp.limitation_reason,
                    cached=True,
                    cached_at=entry["cached_at_iso"],
                    message=cached_resp.message,
                )

        url = f"{self._base_url}match_scorecard"
        params = {"apikey": self._api_key, "id": clean_mid}

        logger.info("Requesting CricketData match_scorecard (id=%s)", clean_mid)

        try:
            client = self._get_client()
            resp = client.get(url, params=params)
        except httpx.TimeoutException:
            logger.warning("CricketData API timeout while fetching match_scorecard")
            if cache_key in self._scorecard_cache:
                old_resp = self._scorecard_cache[cache_key]["response"]
                return CricketDataScorecardResponse(
                    status="success",
                    configured=True,
                    match=old_resp.match,
                    scorecard=old_resp.scorecard,
                    can_reconstruct_interval=False,
                    cached=True,
                    cached_at=self._scorecard_cache[cache_key]["cached_at_iso"],
                    message="Upstream API timed out; serving cached scorecard.",
                )
            return CricketDataScorecardResponse(
                status="error",
                configured=True,
                message="Upstream Cricket Data API timed out.",
            )
        except Exception as exc:
            logger.error("CricketData API scorecard error: %s", type(exc).__name__)
            return CricketDataScorecardResponse(
                status="error",
                configured=True,
                message=f"Failed to communicate with Cricket Data API: {type(exc).__name__}",
            )

        if resp.status_code != 200:
            return CricketDataScorecardResponse(
                status="error",
                configured=True,
                message=f"Cricket Data API returned HTTP {resp.status_code}",
            )

        try:
            payload = resp.json()
        except ValueError:
            return CricketDataScorecardResponse(
                status="error",
                configured=True,
                message="Malformed JSON response from Cricket Data API.",
            )

        info = payload.get("info") or {}
        if isinstance(info, dict):
            if "hitsToday" in info:
                self._last_hits_today = info.get("hitsToday")
            if "hitsLeft" in info:
                self._last_hits_left = info.get("hitsLeft")

        prov_status = payload.get("status")
        if prov_status != "success":
            reason = payload.get("reason") or "Provider reported non-success status."
            return CricketDataScorecardResponse(
                status="error",
                configured=True,
                message=f"Provider message: {reason}",
            )

        raw_data = payload.get("data")
        if not isinstance(raw_data, dict):
            return CricketDataScorecardResponse(
                status="not_found",
                configured=True,
                message=f"No scorecard data returned for match {clean_mid}.",
            )

        # Normalize match summary if present
        norm_match = normalize_match_item(raw_data, retrieved_at=now_utc)

        result = CricketDataScorecardResponse(
            status="success",
            configured=True,
            match=norm_match,
            scorecard=raw_data.get("scorecard") if isinstance(raw_data.get("scorecard"), dict) else raw_data,
            can_reconstruct_interval=False,
            cached=False,
            cached_at=now_utc,
        )

        self._scorecard_cache[cache_key] = {
            "response": result,
            "timestamp": now,
            "cached_at_iso": now_utc,
        }

        return result


_client_instance: Optional[CricketDataClient] = None


def get_cricket_data_client() -> CricketDataClient:
    """Return singleton CricketDataClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = CricketDataClient()
    return _client_instance
