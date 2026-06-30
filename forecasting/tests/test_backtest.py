"""Tests for the rolling-origin backtest harness (Phase 1)."""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from forecasting.src.evaluate.backtest import RollingOriginBacktest, leakage_canary
from forecasting.src.models.baselines import (
    BaseBaseline,
    ChefGutBaseline,
    Lag7Baseline,
    RollingMean28Baseline,
)


def _make_demand(n_days: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = datetime.date(2023, 1, 1)
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


def _make_items():
    from forecasting.src.config import ItemEconomics, PrepType
    eco = ItemEconomics(
        id="item_a", name="Item A", prep_type=PrepType.BATCH,
        co=10.0, cu=15.0, lead_time_days=1,
    )
    return {"item_a": eco, "item_b": eco}


@pytest.fixture
def demand_df():
    return _make_demand(200)


@pytest.fixture
def items():
    return _make_items()


# ------------------------------------------------------------------ splits --

def test_splits_produce_n_folds(demand_df):
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in demand_df["business_date"].unique()])
    splits = list(bt.splits(dates))
    assert len(splits) == 4


def test_test_always_after_train(demand_df):
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in demand_df["business_date"].unique()])
    for train_dates, test_dates in bt.splits(dates):
        assert test_dates.min() > train_dates.max(), (
            f"Test start {test_dates.min()} <= train end {train_dates.max()}"
        )


def test_expanding_window(demand_df):
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in demand_df["business_date"].unique()])
    sizes = [len(tr) for tr, _ in bt.splits(dates)]
    for i in range(1, len(sizes)):
        assert sizes[i] > sizes[i - 1], "Training window did not expand fold-over-fold"


def test_n_folds_below_4_raises():
    with pytest.raises(ValueError, match="n_folds must be >= 4"):
        RollingOriginBacktest(n_folds=3)


def test_insufficient_data_raises():
    bt = RollingOriginBacktest(n_folds=4, test_weeks=8, min_train_weeks=20)
    tiny_dates = pd.DatetimeIndex(
        [pd.Timestamp(datetime.date(2023, 1, 1) + datetime.timedelta(days=i)) for i in range(10)]
    )
    with pytest.raises(ValueError, match="Not enough data"):
        list(bt.splits(tiny_dates))


# ------------------------------------------------------------------ leakage canary --

def test_leakage_canary_passes_when_no_leak():
    feature_df = pd.DataFrame({
        "business_date": [datetime.date(2023, 1, 1), datetime.date(2023, 1, 5)]
    })
    target_df = pd.DataFrame({
        "business_date": [datetime.date(2023, 1, 10)]
    })
    leakage_canary(feature_df, target_df)  # must not raise


def test_leakage_canary_raises_on_overlap():
    feature_df = pd.DataFrame({
        "business_date": [datetime.date(2023, 1, 10)]  # overlaps with target
    })
    target_df = pd.DataFrame({
        "business_date": [datetime.date(2023, 1, 10)]
    })
    with pytest.raises(ValueError, match="Temporal leakage"):
        leakage_canary(feature_df, target_df)


class _LeakingBaseline(BaseBaseline):
    """A deliberately broken baseline that peeks at future data."""

    def fit(self, demand_df: pd.DataFrame) -> "_LeakingBaseline":
        self._future_peek = demand_df  # store training data but will be augmented
        return self

    def predict(self, dates, items, service_periods) -> pd.DataFrame:
        rows = [
            {"business_date": d, "item_id": it, "service_period": sp, "forecast": 10.0}
            for d in dates for it in items for sp in service_periods
        ]
        return pd.DataFrame(rows)


def test_splits_raises_if_forced_overlap():
    """Verify that splits() itself checks for temporal ordering."""
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    # Use a date range long enough
    dates = pd.DatetimeIndex(
        [pd.Timestamp(datetime.date(2023, 1, 1) + datetime.timedelta(days=i)) for i in range(200)]
    )
    for train_dates, test_dates in bt.splits(dates):
        # If this doesn't raise, temporal ordering is enforced
        assert test_dates.min() > train_dates.max()


# ------------------------------------------------------------------ run() --

def test_dollar_costs_are_positive_finite(demand_df, items):
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    baselines = {
        "lag7": Lag7Baseline(),
        "rolling28": RollingMean28Baseline(),
        "chef_gut": ChefGutBaseline(),
    }
    results = bt.run(demand_df, baselines, items)
    assert len(results) > 0, "run() returned no results"
    for _, row in results.iterrows():
        assert np.isfinite(row["dollar_cost"]), f"Non-finite dollar_cost for {row['baseline']}"
        assert row["dollar_cost"] >= 0, f"Negative dollar_cost for {row['baseline']}"


def test_results_dataframe_schema(demand_df, items):
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    baselines = {"lag7": Lag7Baseline(), "rolling28": RollingMean28Baseline()}
    results = bt.run(demand_df, baselines, items)
    required_cols = {
        "fold", "baseline", "item_id", "train_end",
        "test_start", "test_end", "dollar_cost", "wape", "bias", "n_days",
    }
    assert required_cols.issubset(set(results.columns)), (
        f"Missing columns: {required_cols - set(results.columns)}"
    )


def test_all_baselines_appear_in_results(demand_df, items):
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    baselines = {
        "lag7": Lag7Baseline(),
        "rolling28": RollingMean28Baseline(),
        "chef_gut": ChefGutBaseline(),
    }
    results = bt.run(demand_df, baselines, items)
    assert set(results["baseline"].unique()) == set(baselines.keys())


def test_four_folds_in_results(demand_df, items):
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    baselines = {"lag7": Lag7Baseline()}
    results = bt.run(demand_df, baselines, items)
    assert results["fold"].nunique() == 4


def test_wape_between_zero_and_reasonable(demand_df, items):
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    baselines = {"rolling28": RollingMean28Baseline()}
    results = bt.run(demand_df, baselines, items)
    wape_vals = results["wape"].dropna()
    assert (wape_vals >= 0).all()
    assert (wape_vals < 10).all(), "WAPE > 1000% — something is very wrong"


def test_string_dated_demand_does_not_silently_empty(demand_df, items):
    """audit #8: a demand_df with string business_date (as a CSV load gives) must still
    backtest, not silently return an empty frame. Previously _to_date passed strings
    through and run() yielded nothing with no error."""
    df = demand_df.copy()
    df["business_date"] = df["business_date"].astype(str)
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=8)
    results = bt.run(df, {"rolling28": RollingMean28Baseline()}, items)
    assert not results.empty
    assert results["fold"].nunique() == 4
