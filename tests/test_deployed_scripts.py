"""Unit tests for public smoke/evaluation helpers; no network requests are made."""

import pytest

from scripts.evaluate_catchups import is_verifier_rejection, percentile, verifier_was_reached
from scripts.smoke_test import SmokeTestError, choose_interval


def test_choose_interval_picks_an_interval_returned_by_api():
    response = {
        "match_id": "1529229",
        "intervals": [
            {"innings": 0, "start_after_over": -1, "end_after_over": 2, "label": "start to 3"},
            {"innings": 0, "start_after_over": 3, "end_after_over": 8, "label": "4 to 8"},
            {"innings": 1, "start_after_over": 4, "end_after_over": 9, "label": "5 to 9"},
        ],
    }
    assert choose_interval(response) == response["intervals"][1]


def test_choose_interval_rejects_empty_api_result():
    with pytest.raises(SmokeTestError, match="No valid intervals"):
        choose_interval({"match_id": "1552779", "intervals": []})


def test_percentile_uses_linear_interpolation():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(values, 0.50) == 3.0
    assert percentile(values, 0.95) == 4.8
    assert percentile([], 0.95) is None


def test_verifier_rate_excludes_provider_failures_and_fallback_disabled():
    assert is_verifier_rejection("deterministic_fallback", "unsupported_claims")
    assert is_verifier_rejection("deterministic_fallback", "fact_mismatch")
    assert not is_verifier_rejection("deterministic_fallback", "llm_error")
    assert not is_verifier_rejection("deterministic_fallback", "disabled")
    assert verifier_was_reached("llm_verified", "none")
    assert verifier_was_reached("deterministic_fallback", "unsupported_claims")
    assert not verifier_was_reached("deterministic_fallback", "llm_error")
