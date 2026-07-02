"""Tests for the Phase-2 point model (forecasting/src/models/point.py).

Deliberately does NOT assert a dollar win over the baselines here: on a small, fast
synthetic fixture LightGBM has too little data to beat simple rolling means (verified
empirically while writing this test -- the GBM needs the real ~250-day simulated
series to win, which point_floor.py demonstrates on real data: 128,467.93 vs
144,789.25). These tests instead guard the fit/predict CONTRACT and catch a code-level
regression (crash, NaN, schema break) via the backtest harness -- the dollar-gate proof
itself lives in point_floor.py (docs/phase_decisions/P2_review.md BLOCKER-1).
"""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from forecasting.src.config import ItemEconomics, PrepType
from forecasting.src.evaluate.backtest import RollingOriginBacktest
from forecasting.src.models.baselines import Lag7Baseline, RollingMean28Baseline
from forecasting.src.models.point import GlobalLGBMModel


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


def _items():
    eco = ItemEconomics(
        id="item_a", name="Item A", prep_type=PrepType.BATCH,
        co=10.0, cu=15.0, lead_time_days=1,
    )
    return {"item_a": eco, "item_b": eco}


# ------------------------------------------------------------------ fit/predict contract --

def test_predict_before_fit_raises():
    model = GlobalLGBMModel(n_estimators=10)
    with pytest.raises(RuntimeError, match="fit"):
        model.predict([datetime.date(2024, 3, 1)], ["item_a"], ["lunch"])


def test_predict_schema_and_nonnegativity():
    train = _demand_df(n_days=40)
    model = GlobalLGBMModel(n_estimators=10).fit(train)
    test_dates = [datetime.date(2024, 2, 12), datetime.date(2024, 2, 13)]
    preds = model.predict(test_dates, ["item_a", "item_b"], ["lunch", "dinner"])

    assert list(preds.columns) == ["business_date", "item_id", "service_period", "forecast"]
    # Full cross-product: 2 dates x 2 items x 2 service_periods
    assert len(preds) == 8
    assert (preds["forecast"] >= 0).all()
    assert preds["forecast"].notna().all()


def test_predict_inside_training_window_raises_leakage():
    """The pipeline's default check_leakage=True must reject a test date <= train_max_date."""
    train = _demand_df(n_days=40)
    model = GlobalLGBMModel(n_estimators=10).fit(train)
    train_max_date = train["business_date"].max()
    with pytest.raises(ValueError, match="leakage"):
        model.predict([train_max_date], ["item_a"], ["lunch"])


# ------------------------------------------------------------------ diagnostics (rule 03) --

def test_fit_stores_item_bias_and_feature_importances():
    """fit() must store a per-item predicted-vs-actual bias table and feature
    importances (P2_review.md MINOR-6) -- the diagnostic that would surface censored-row
    contamination as a per-item bias."""
    train = _demand_df(n_days=40)
    model = GlobalLGBMModel(n_estimators=10).fit(train)

    assert set(model.item_bias_.index) == {"item_a", "item_b"}
    assert {"pred_mean", "actual_mean", "bias"}.issubset(model.item_bias_.columns)

    assert not model.feature_importances_.empty
    assert set(model.feature_importances_.index) == set(model._pipeline.feature_columns())


# ------------------------------------------------------------------ backtest integration --

def test_backtest_integration_produces_finite_bounded_costs():
    """Regression guard: the model must run cleanly inside RollingOriginBacktest and
    produce finite, non-negative dollar costs in the same ballpark as the baselines --
    NOT a claim that it beats them (see module docstring)."""
    demand_df = _demand_df(n_days=90)
    items = _items()
    models = {
        "lag7": Lag7Baseline(),
        "rolling28": RollingMean28Baseline(),
        "lgbm_point": GlobalLGBMModel(n_estimators=20),
    }
    bt = RollingOriginBacktest(n_folds=4, test_weeks=1, min_train_weeks=6)
    results = bt.run(demand_df, models, items)

    totals = results.groupby("baseline")["dollar_cost"].sum()
    assert np.isfinite(totals["lgbm_point"])
    assert totals["lgbm_point"] >= 0
    # Generous non-regression bound: catches a broken model (crash-free but garbage
    # output) without asserting it must win on a tiny, low-signal synthetic fixture.
    assert totals["lgbm_point"] <= totals.drop("lgbm_point").max() * 2.0
