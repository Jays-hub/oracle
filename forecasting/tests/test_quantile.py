"""Tests for the Phase-4 quantile model (forecasting/src/models/quantile.py).

Mirrors test_point.py's approach: guards the fit/predict CONTRACT and non-crossing
guarantee on a small, fast synthetic fixture rather than asserting a dollar/pinball
win (that proof belongs to evaluate/newsvendor_floor.py and evaluate/calibration.py
on real data, same division of labor as point_floor.py vs. test_point.py).
"""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from forecasting.src.models.quantile import DEFAULT_QUANTILE_LEVELS, QuantileGBMModel


def _demand_df(n_days: int = 60, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = datetime.date(2024, 1, 1)
    rows = []
    for offset in range(n_days):
        d = start + datetime.timedelta(days=offset)
        for it in ["item_a", "item_b"]:
            for sp in ["lunch", "dinner"]:
                rows.append({
                    "business_date": d,
                    "item_id": it,
                    "service_period": sp,
                    "demand": int(rng.poisson(10)),
                })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ construction --

def test_rejects_quantile_levels_outside_open_unit_interval():
    with pytest.raises(ValueError):
        QuantileGBMModel(quantile_levels=(0.0, 0.5))
    with pytest.raises(ValueError):
        QuantileGBMModel(quantile_levels=(0.5, 1.0))


def test_deduplicates_and_sorts_quantile_levels():
    model = QuantileGBMModel(quantile_levels=(0.9, 0.1, 0.5, 0.5))
    assert model.quantile_levels == [0.1, 0.5, 0.9]


# ------------------------------------------------------------------ fit/predict contract --

def test_predict_before_fit_raises():
    model = QuantileGBMModel(quantile_levels=(0.1, 0.5, 0.9), n_estimators=10)
    with pytest.raises(RuntimeError, match="fit"):
        model.predict_quantiles([datetime.date(2024, 3, 1)], ["item_a"], ["lunch"])


def test_predict_quantiles_schema_and_nonnegativity():
    train = _demand_df(n_days=40)
    model = QuantileGBMModel(quantile_levels=(0.1, 0.5, 0.9), n_estimators=10).fit(train)
    test_dates = [datetime.date(2024, 2, 12), datetime.date(2024, 2, 13)]
    preds = model.predict_quantiles(test_dates, ["item_a", "item_b"], ["lunch", "dinner"])

    assert list(preds.columns) == [
        "business_date", "item_id", "service_period", "quantile", "forecast",
    ]
    # Full cross-product: 2 dates x 2 items x 2 service_periods x 3 quantile levels
    assert len(preds) == 2 * 2 * 2 * 3
    assert (preds["forecast"] >= 0).all()
    assert preds["forecast"].notna().all()
    assert set(preds["quantile"].unique()) == {0.1, 0.5, 0.9}


def test_predict_inside_training_window_raises_leakage():
    train = _demand_df(n_days=40)
    model = QuantileGBMModel(quantile_levels=(0.1, 0.5, 0.9), n_estimators=10).fit(train)
    train_max_date = train["business_date"].max()
    with pytest.raises(ValueError, match="leakage"):
        model.predict_quantiles([train_max_date], ["item_a"], ["lunch"])


def test_fit_trains_one_estimator_per_quantile_level():
    train = _demand_df(n_days=40)
    model = QuantileGBMModel(quantile_levels=(0.1, 0.5, 0.9), n_estimators=10).fit(train)
    assert set(model.estimators_.keys()) == {0.1, 0.5, 0.9}


# ------------------------------------------------------------------ non-crossing (rule 03) --

def test_predict_quantiles_are_never_crossing():
    """Independently re-derived (not a tautology): fit a WIDE, densely-spaced
    quantile grid where independently-trained models are likely to cross without
    the post-hoc rearrangement, then assert every item-day's forecasts are
    non-decreasing in quantile level.
    """
    train = _demand_df(n_days=90, seed=7)
    levels = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)
    model = QuantileGBMModel(quantile_levels=levels, n_estimators=15).fit(train)
    test_dates = [datetime.date(2024, 4, 1), datetime.date(2024, 4, 2), datetime.date(2024, 4, 3)]
    preds = model.predict_quantiles(test_dates, ["item_a", "item_b"], ["lunch", "dinner"])

    for _, grp in preds.groupby(["business_date", "item_id", "service_period"]):
        ordered = grp.sort_values("quantile")["forecast"].to_numpy()
        assert np.all(np.diff(ordered) >= -1e-9), f"crossing quantiles found: {ordered}"


# ------------------------------------------------------------------ reproducibility --

def test_same_seed_twice_gives_identical_predictions():
    train = _demand_df(n_days=40)
    test_dates = [datetime.date(2024, 2, 12), datetime.date(2024, 2, 13)]

    model_a = QuantileGBMModel(quantile_levels=(0.1, 0.5, 0.9), n_estimators=10, random_state=42).fit(train)
    preds_a = model_a.predict_quantiles(test_dates, ["item_a", "item_b"], ["lunch", "dinner"])

    model_b = QuantileGBMModel(quantile_levels=(0.1, 0.5, 0.9), n_estimators=10, random_state=42).fit(train)
    preds_b = model_b.predict_quantiles(test_dates, ["item_a", "item_b"], ["lunch", "dinner"])

    pd.testing.assert_frame_equal(preds_a, preds_b)


# ------------------------------------------------------------------ edge cases --

def test_default_quantile_levels_are_within_open_unit_interval():
    assert all(0.0 < q < 1.0 for q in DEFAULT_QUANTILE_LEVELS)
    assert list(DEFAULT_QUANTILE_LEVELS) == sorted(DEFAULT_QUANTILE_LEVELS)


def test_single_quantile_level_still_produces_a_valid_curve():
    train = _demand_df(n_days=40)
    model = QuantileGBMModel(quantile_levels=(0.5,), n_estimators=10).fit(train)
    preds = model.predict_quantiles(
        [datetime.date(2024, 2, 12)], ["item_a"], ["lunch"]
    )
    assert len(preds) == 1
    assert preds["quantile"].iloc[0] == 0.5
