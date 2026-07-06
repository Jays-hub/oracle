"""Tests for src/pricing/trends.py — price-trend detection over the seam's price-history shape.

Covers: correctness against hand-computed pct_change, the same-day tie-break rule (mirrors
src/pricing/compute.py::latest_prices), the "not enough history yet" edge case (no fabricated
0%/None), reproducibility (same input twice -> identical output), and the significance filter.
"""
import pandas as pd
import pytest

from src.pricing import trends


def _obs_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_latest_price_per_ingredient_picks_max_date():
    df = _obs_df([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.0, "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.5, "observed_date": "2026-06-08"},
    ])
    latest = trends.latest_price_per_ingredient(df)
    assert len(latest) == 1
    assert latest["unit_price"].iloc[0] == pytest.approx(3.5)


def test_latest_price_per_ingredient_same_day_tie_break_is_last_input_row():
    """Mirrors compute.py::latest_prices' documented tie-break: on equal observed_date, the LAST
    row in input order wins, not the first."""
    df = _obs_df([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.0, "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.9, "observed_date": "2026-06-01"},
    ])
    latest = trends.latest_price_per_ingredient(df)
    assert latest["unit_price"].iloc[0] == pytest.approx(3.9)


def test_latest_price_per_ingredient_empty_input():
    df = _obs_df([])
    latest = trends.latest_price_per_ingredient(df)
    assert latest.empty


def test_price_trend_correctness_hand_computed():
    """beef: $3.00 -> $3.48 over exactly one week is a hand-computed +16% move."""
    df = _obs_df([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00, "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.48, "observed_date": "2026-06-08"},
    ])
    trend = trends.price_trend(df, lookback_days=7)
    assert len(trend) == 1
    row = trend.iloc[0]
    assert row["current_price"] == pytest.approx(3.48)
    assert row["prior_price"] == pytest.approx(3.00)
    assert row["pct_change"] == pytest.approx(0.16, abs=1e-6)
    assert row["direction"] == "up"


def test_price_trend_flags_down_and_flat_directions():
    df = _obs_df([
        {"ingredient_id": "a", "ingredient_name": "a", "unit_price": 2.00, "observed_date": "2026-06-01"},
        {"ingredient_id": "a", "ingredient_name": "a", "unit_price": 1.80, "observed_date": "2026-06-10"},
        {"ingredient_id": "b", "ingredient_name": "b", "unit_price": 2.00, "observed_date": "2026-06-01"},
        {"ingredient_id": "b", "ingredient_name": "b", "unit_price": 2.00, "observed_date": "2026-06-10"},
    ])
    trend = trends.price_trend(df, lookback_days=7)
    directions = dict(zip(trend["ingredient_id"], trend["direction"]))
    assert directions["a"] == "down"
    assert directions["b"] == "flat"


def test_price_trend_skips_ingredient_with_not_enough_history():
    """A single observation (no prior >= lookback_days earlier) must not fabricate a 0% trend —
    it's simply excluded from the result."""
    df = _obs_df([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00, "observed_date": "2026-06-01"},
    ])
    trend = trends.price_trend(df, lookback_days=7)
    assert trend.empty


def test_price_trend_respects_as_of_date():
    """A future observation (after as_of) must not leak into "current"."""
    df = _obs_df([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00, "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.48, "observed_date": "2026-06-08"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 9.99, "observed_date": "2026-07-01"},
    ])
    trend = trends.price_trend(df, as_of="2026-06-08", lookback_days=7)
    assert trend.iloc[0]["current_price"] == pytest.approx(3.48)


def test_price_trend_empty_input():
    trend = trends.price_trend(_obs_df([]))
    assert trend.empty


def test_price_trend_is_reproducible():
    df = _obs_df([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00, "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.48, "observed_date": "2026-06-08"},
    ])
    first = trends.price_trend(df, lookback_days=7)
    second = trends.price_trend(df, lookback_days=7)
    pd.testing.assert_frame_equal(first, second)


def test_significant_moves_filters_by_threshold_and_ranks_by_magnitude():
    trend = pd.DataFrame([
        {"ingredient_id": "a", "ingredient_name": "a", "current_price": 1.0, "prior_price": 1.0,
         "pct_change": 0.05, "direction": "up"},
        {"ingredient_id": "b", "ingredient_name": "b", "current_price": 1.0, "prior_price": 1.0,
         "pct_change": -0.30, "direction": "down"},
        {"ingredient_id": "c", "ingredient_name": "c", "current_price": 1.0, "prior_price": 1.0,
         "pct_change": 0.16, "direction": "up"},
    ])
    moves = trends.significant_moves(trend, threshold=0.10)
    assert list(moves["ingredient_id"]) == ["b", "c"]  # 30% then 16%, 5% excluded


def test_significant_moves_empty_input():
    empty_trend = trends.price_trend(_obs_df([]))
    moves = trends.significant_moves(empty_trend)
    assert moves.empty
