"""Tests for the Phase-2 feature pipeline (forecasting/src/features/pipeline.py)."""
from __future__ import annotations

import datetime
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from forecasting.src.features.pipeline import (
    FEATURE_COLS,
    FeaturePipeline,
    _era_for_date,
)


# ------------------------------------------------------------------ helpers --

def _demand_df(
    start: str = "2022-02-01",
    n_days: int = 30,
    items: list[str] | None = None,
    periods: list[str] | None = None,
    base_demand: int = 10,
) -> pd.DataFrame:
    """Minimal demand DataFrame for pipeline tests."""
    items = items or ["item_a"]
    periods = periods or ["dinner"]
    rng = pd.date_range(start, periods=n_days, freq="D")
    rows = []
    for d in rng:
        for it in items:
            for sp in periods:
                rows.append({
                    "business_date": d.date(),
                    "item_id": it,
                    "service_period": sp,
                    "demand": base_demand,
                })
    return pd.DataFrame(rows)


def _synthetic_era_boundaries() -> list[tuple[date, int]]:
    """Two eras: era 0 from 2022-01-01, era 1 from 2022-03-01."""
    return [(date(2022, 1, 1), 0), (date(2022, 3, 1), 1)]


# ------------------------------------------------------------------ era logic --

def test_era_id_before_first_boundary():
    """A date before (or equal to) the first boundary gets era 0."""
    bounds = _synthetic_era_boundaries()
    era_id, elapsed = _era_for_date(date(2022, 1, 15), bounds)
    assert era_id == 0
    assert elapsed == 14  # 15 - 1 = 14 days elapsed


def test_era_id_after_second_boundary():
    """A date after the second boundary gets era 1."""
    bounds = _synthetic_era_boundaries()
    era_id, elapsed = _era_for_date(date(2022, 4, 1), bounds)
    assert era_id == 1
    assert elapsed == (date(2022, 4, 1) - date(2022, 3, 1)).days


def test_era_days_elapsed_nonneg():
    """era_days_elapsed is always >= 0, even for dates at era boundary."""
    bounds = _synthetic_era_boundaries()
    _, elapsed = _era_for_date(date(2022, 3, 1), bounds)
    assert elapsed == 0


# ------------------------------------------------------------------ fit/transform schema --

def test_all_feature_columns_present_after_transform():
    """transform() must add every column listed in FEATURE_COLS."""
    train = _demand_df(n_days=30)
    test = _demand_df(start="2022-03-03", n_days=5)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)
    result = pipeline.transform(test)
    missing = set(FEATURE_COLS) - set(result.columns)
    assert not missing, f"Missing feature columns: {missing}"


def test_transform_preserves_input_rows():
    """Output row count equals input row count."""
    train = _demand_df(n_days=30)
    test = _demand_df(start="2022-03-03", n_days=7)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)
    result = pipeline.transform(test)
    assert len(result) == len(test)


def test_transform_requires_fit_first():
    """transform() without prior fit() raises RuntimeError."""
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries())
    test = _demand_df(n_days=3)
    with pytest.raises(RuntimeError, match="fit"):
        pipeline.transform(test)


# ------------------------------------------------------------------ lag correctness --

def test_lag_1_equals_prior_day_demand():
    """lag_1 at day d must equal training demand at d-1 (core correctness check).

    This is the most important single test: if lag_1 equals same-day demand,
    the model is training on its own target — the canonical leakage mistake.
    """
    # Training: demand=10 every day for 30 days
    train = _demand_df(n_days=30, base_demand=10)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)

    # Transform on day 31 (first day after training)
    last_train_date = date(2022, 2, 1) + timedelta(days=29)  # 2022-03-02
    test_date = last_train_date + timedelta(days=1)
    test = pd.DataFrame([{
        "business_date": test_date,
        "item_id": "item_a",
        "service_period": "dinner",
        "demand": 99,  # should NOT appear as lag_1
    }])
    result = pipeline.transform(test)
    assert result["lag_1"].iloc[0] == pytest.approx(10.0), (
        f"lag_1 should be yesterday's training demand (10), not today's demand (99). "
        f"Got: {result['lag_1'].iloc[0]}"
    )


def test_lag_1_never_equals_same_day_demand():
    """Structural leakage guard: lag_1 must not equal today's demand value.

    Uses deliberately different demand levels so an accidental same-day
    read would be caught even if the magnitudes happened to be close.
    """
    # Training: alternating 5 and 20 every two days
    rows = []
    for i in range(30):
        rows.append({
            "business_date": date(2022, 2, 1) + timedelta(days=i),
            "item_id": "item_a",
            "service_period": "dinner",
            "demand": 5 if i % 2 == 0 else 20,
        })
    train = pd.DataFrame(rows)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)

    # Self-transform on training data
    result = pipeline.transform(train)
    # For any row where demand != lag_1 (day 0 has NaN, others alternate), check no match
    # The key invariant: lag_1 at row i should equal demand at row i-1, not row i
    has_same_day_leak = False
    for i in range(1, len(result)):
        d = result.iloc[i]["demand"]
        l1 = result.iloc[i]["lag_1"]
        d_prev = result.iloc[i - 1]["demand"]
        if not np.isnan(l1) and abs(l1 - d) < 1e-6 and abs(d - d_prev) > 1:
            # lag_1 matches today's demand, but today ≠ yesterday → leak
            has_same_day_leak = True
            break
    assert not has_same_day_leak, (
        "lag_1 matched today's demand on a row where demand != yesterday's demand. "
        "shift(1) discipline violated."
    )


def test_lag_7_equals_same_weekday_last_week():
    """lag_7 at day d must equal training demand at d-7."""
    rows = []
    for i in range(20):
        rows.append({
            "business_date": date(2022, 2, 1) + timedelta(days=i),
            "item_id": "item_a",
            "service_period": "dinner",
            "demand": i,  # distinct values so we can verify the right one is selected
        })
    train = pd.DataFrame(rows)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)

    # Transform on day 8 (index 7 in 0-based), lag_7 should be day 1 (demand=1)
    test_date = date(2022, 2, 1) + timedelta(days=7)
    test = pd.DataFrame([{
        "business_date": test_date,
        "item_id": "item_a",
        "service_period": "dinner",
        "demand": 0,
    }])
    result = pipeline.transform(test)
    # demand at date(2022, 2, 1) (i=0) was 0; lag_7 at day 8 should be demand at day 1 = 1
    assert result["lag_7"].iloc[0] == pytest.approx(1.0)


# ------------------------------------------------------------------ rolling stats --

def test_rolling_mean_7_uses_prior_7_days():
    """rolling_mean_7 at day d must be the mean of days [d-7 … d-1]."""
    # Demand pattern: 1 for days 0–6, then 100 for day 7 (today)
    rows = []
    for i in range(8):
        rows.append({
            "business_date": date(2022, 2, 1) + timedelta(days=i),
            "item_id": "item_a",
            "service_period": "dinner",
            "demand": 1 if i < 7 else 100,
        })
    train = pd.DataFrame(rows)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)

    test_date = date(2022, 2, 1) + timedelta(days=7)  # day 7 (100 demand)
    test = pd.DataFrame([{
        "business_date": test_date,
        "item_id": "item_a",
        "service_period": "dinner",
        "demand": 100,
    }])
    result = pipeline.transform(test)
    # Window should cover days 0-6 (all demand=1), mean=1.0
    assert result["rolling_mean_7"].iloc[0] == pytest.approx(1.0), (
        "rolling_mean_7 should be 1.0 (mean of 7 prior days at demand=1), "
        f"not {result['rolling_mean_7'].iloc[0]} — current-day demand (100) leaked in."
    )


def test_rolling_std_nan_with_single_observation():
    """rolling_std_7 is NaN when the window has only 1 observation (min_periods=2)."""
    train = _demand_df(n_days=2, base_demand=10)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)
    # Transform on day 3: only 2 training days, window [d-7…d-1] has at most 2 obs
    test = _demand_df(start="2022-02-03", n_days=1)
    result = pipeline.transform(test)
    # With only 2 prior obs in the 7-day window, std may be defined (n=2 → float);
    # with only 1 prior obs (first possible test day), std must be NaN
    train_1day = _demand_df(n_days=1, base_demand=10)
    pipeline_1 = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train_1day)
    test_1 = _demand_df(start="2022-02-02", n_days=1)
    result_1 = pipeline_1.transform(test_1)
    assert np.isnan(result_1["rolling_std_7"].iloc[0]), (
        "rolling_std_7 must be NaN when only 1 prior obs exists (min_periods=2)"
    )


# ------------------------------------------------------------------ leakage guard --

def test_check_leakage_raises_on_overlap():
    """check_leakage=True must raise when transform dates overlap training dates."""
    train = _demand_df(n_days=14)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)
    # Overlap: transform date is within the training window
    overlap_test = _demand_df(start="2022-02-07", n_days=3)
    with pytest.raises(ValueError, match="[Ll]eakage"):
        pipeline.transform(overlap_test, check_leakage=True)


def test_check_leakage_passes_for_future_dates():
    """check_leakage=True must NOT raise when all transform dates are after training."""
    train = _demand_df(n_days=14)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)
    # First test date is day after last training date
    future_test = _demand_df(start="2022-02-15", n_days=5)
    result = pipeline.transform(future_test, check_leakage=True)
    assert len(result) == len(future_test)


# ------------------------------------------------------------------ edge cases --

def test_unknown_item_gives_nan_lags():
    """A (item, period) pair not seen during fit returns NaN lags — no crash."""
    train = _demand_df(n_days=14, items=["item_a"])
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)
    test = _demand_df(start="2022-02-15", n_days=3, items=["item_b"])
    result = pipeline.transform(test)
    assert result["lag_1"].isna().all(), (
        "Unseen item must produce NaN lags, not crash or inherit another item's history"
    )


def test_is_weekend_correct():
    """is_weekend must be 1 on Saturday (5) and Sunday (6), 0 otherwise."""
    train = _demand_df(n_days=7)
    pipeline = FeaturePipeline(era_boundaries=_synthetic_era_boundaries()).fit(train)
    result = pipeline.transform(train)
    for _, row in result.iterrows():
        d = row["business_date"]
        expected = 1 if d.weekday() >= 5 else 0
        assert row["is_weekend"] == expected, (
            f"is_weekend={row['is_weekend']} on {d} (weekday={d.weekday()}, expected {expected})"
        )
