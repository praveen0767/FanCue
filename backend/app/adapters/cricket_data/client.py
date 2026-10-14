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
        """Fetch current matches through the authenticated CricketData API.

        CricketData's basic API examples use an API key. Do not pretend an
        anonymous request is a supported fallback: reject missing keys early
        and return an actionable diagnostic when the provider rejects a key.
        """
        now = time.time()
        now_utc = datetime.now(timezone.utc).isoformat()
        cache_key = f"currentMatches_{offset}"

        def cached_response(message: str, status: str = "success") -> Optional[CricketDataMatchesResponse]:
            entry = self._matches_cache.get(cache_key)
            if not entry:
                return None
            previous: CricketDataMatchesResponse = entry["response"]
            return CricketDataMatchesResponse(
                status=status,
                configured=previous.configured,
                matches=previous.matches,
                total=previous.total,
                cached=True,
                cached_at=entry["cached_at_iso"],
                hits_today=previous.hits_today,
                hits_left=previous.hits_left,
                message=message,
            )

        if not self.is_configured:
            return CricketDataMatchesResponse(
                status="unconfigured",
                configured=False,
                matches=[],
                total=0,
                message=(
                    "Near-live scores require a valid CricketData.org API key. "
                    "Set CRICKET_DATA_API_KEY in the Render service environment."
                ),
            )

        if not force_refresh and cache_key in self._matches_cache:
            entry = self._matches_cache[cache_key]
            if now - entry["timestamp"] < self._cache_ttl:
                previous: CricketDataMatchesResponse = entry["response"]
                return CricketDataMatchesResponse(
                    status=previous.status,
                    configured=previous.configured,
                    matches=previous.matches,
                    total=previous.total,
                    cached=True,
                    cached_at=entry["cached_at_iso"],
                    hits_today=previous.hits_today,
                    hits_left=previous.hits_left,
                    message=previous.message,
                )

        # Never make an upstream call when the authenticated daily quota is known exhausted.
        if self._last_hits_left is not None and self._last_hits_left <= 0 and not force_refresh:
            cached = cached_response(
                "CricketData.org's daily API allowance is exhausted. Showing the last cached match list.",
                status="rate_limited",
            )
            if cached is not None:
                return cached
            return CricketDataMatchesResponse(
                status="rate_limited",
                configured=True,
                matches=[],
                total=0,
                hits_today=self._last_hits_today,
                hits_left=0,
                message="CricketData.org's daily API allowance is exhausted. Try again after it resets.",
            )

        url = f"{self._base_url}currentMatches"
        params = {"apikey": self._api_key, "offset": offset}
        logger.info("Requesting CricketData currentMatches (offset=%d)", offset)

        try:
            client = self._get_client()
            resp = client.get(url, params=params)
        except httpx.TimeoutException:
            logger.warning("CricketData API timed out while fetching currentMatches")
            cached = cached_response(
                "The score provider timed out. Showing the last cached match list."
            )
            if cached is not None:
                return cached
            return CricketDataMatchesResponse(
                status="error",
                configured=True,
                matches=[],
                total=0,
                message="The cricket score provider timed out. Please retry shortly.",
            )
        except Exception as exc:
            logger.error("CricketData API request error: %s", type(exc).__name__)
            cached = cached_response(
                "The score provider is unavailable. Showing the last cached match list."
            )
            if cached is not None:
                return cached
            return CricketDataMatchesResponse(
                status="error",
                configured=True,
                matches=[],
                total=0,
                message=f"Unable to reach the cricket score provider ({type(exc).__name__}).",
            )

        if resp.status_code in (401, 403):
            return CricketDataMatchesResponse(
                status="error",
                configured=False,
                matches=[],
                total=0,
                message=(
                    "CricketData.org rejected the configured API key. In Render, open "
                    "the fancue-api service → Environment and replace CRICKET_DATA_API_KEY "
                    "with a valid key from your CricketData.org account, then redeploy."
                ),
            )
        if resp.status_code != 200:
            logger.warning("CricketData API returned HTTP %d", resp.status_code)
            cached = cached_response(
                f"CricketData.org returned HTTP {resp.status_code}. Showing the last cached match list."
            )
            if cached is not None:
                return cached
            return CricketDataMatchesResponse(
                status="error",
                configured=True,
                matches=[],
                total=0,
                message=f"CricketData.org returned HTTP {resp.status_code}.",
            )

        try:
            payload = resp.json()
        except ValueError:
            return CricketDataMatchesResponse(
                status="error",
                configured=True,
                matches=[],
                total=0,
                message="CricketData.org returned an unreadable response.",
            )

        info = payload.get("info") or {}
        if isinstance(info, dict):
            if "hitsToday" in info:
                self._last_hits_today = info.get("hitsToday")
            if "hitsLeft" in info:
                self._last_hits_left = info.get("hitsLeft")

        provider_status = payload.get("status")
        if provider_status != "success":
            reason = str(payload.get("reason") or "The provider reported a temporary failure.")
            reason_lower = reason.lower()
            if any(token in reason_lower for token in ("invalid api key", "invalid_api_key", "unauthorized", "invalid key")):
                return CricketDataMatchesResponse(
                    status="error",
                    configured=False,
                    matches=[],
                    total=0,
                    hits_today=self._last_hits_today,
                    hits_left=self._last_hits_left,
                    message=(
                        "CricketData.org rejected the configured API key. In Render, open "
                        "the fancue-api service → Environment and replace CRICKET_DATA_API_KEY "
                        "with a valid key from your CricketData.org account, then redeploy."
                    ),
                )
            if any(token in reason_lower for token in ("daily limit", "quota exhausted", "rate limit", "hits left")):
                cached = cached_response(
                    "CricketData.org's request allowance is exhausted. Showing the last cached match list.",
                    status="rate_limited",
                )
                if cached is not None:
                    return cached
                return CricketDataMatchesResponse(
                    status="rate_limited",
                    configured=True,
                    matches=[],
                    total=0,
                    hits_today=self._last_hits_today,
                    hits_left=self._last_hits_left,
                    message="CricketData.org's request allowance is exhausted. Try again after it resets.",
                )
            logger.warning("CricketData returned non-success status: %s", reason)
            cached = cached_response(
                "The score provider is temporarily unavailable. Showing the last cached match list."
            )
            if cached is not None:
                return cached
            return CricketDataMatchesResponse(
                status="error",
                configured=True,
                matches=[],
                total=0,
                hits_today=self._last_hits_today,
                hits_left=self._last_hits_left,
                message="CricketData.org could not return match data. Please retry later.",
            )

        raw_data = payload.get("data") or []
        matches: list[CricketDataMatchItem] = []
        if isinstance(raw_data, list):
            for item in raw_data:
                normalized = normalize_match_item(item, retrieved_at=now_utc)
                if normalized is not None:
                    matches.append(normalized)

        result = CricketDataMatchesResponse(
            status="success",
            configured=True,
            matches=matches,
            total=len(matches),
            cached=False,
            cached_at=now_utc,
            hits_today=self._last_hits_today,
            hits_left=self._last_hits_left,
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
