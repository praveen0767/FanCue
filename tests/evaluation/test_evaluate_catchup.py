"""Tests for the live evaluation harness and its local adversarial verifier sample."""

import warnings

from scripts.evaluate_catchup import (
    choose_interval,
    make_local_adversarial_report,
    nearest_rank_percentile,
)


def test_nearest_rank_percentiles_are_deterministic():
    values = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert nearest_rank_percentile(values, 0.50) == 0.3
    assert nearest_rank_percentile(values, 0.95) == 0.5
    assert nearest_rank_percentile([], 0.50) is None


def test_choose_interval_uses_valid_short_interval_without_inventing_boundaries():
    intervals = [
        {"innings": 0, "start_after_over": -1, "end_after_over": 5},
        {"innings": 0, "start_after_over": 0, "end_after_over": 5},
        {"innings": 1, "start_after_over": 5, "end_after_over": 10},
    ]
    chosen = choose_interval(intervals)
    assert chosen == intervals[1]


def test_local_adversarial_verifier_set_records_observed_outcomes():
    """Measure the verifier output without asserting a pre-decided rejection rate."""
    result = make_local_adversarial_report()

    assert result["adversarial_cases"] == 3
    assert {item["case"] for item in result["results"]} == {
        "wrong_score",
        "wrong_player",
        "invented_wicket",
    }
    assert all(isinstance(item["rejected"], bool) for item in result["results"])
    measured = (
        f"Observed local adversarial verifier result: {result['rejected_cases']}/"
        f"{result['adversarial_cases']} rejected; "
        f"rate={result['rejection_rate_percent']:.2f}%; "
        + "; ".join(
            f"{item['case']}={'rejected' if item['rejected'] else 'not rejected'}"
            f"[{','.join(item['rejection_reasons']) or 'no reason'}]"
            for item in result["results"]
        )
    )
    warnings.warn(measured, UserWarning, stacklevel=1)
