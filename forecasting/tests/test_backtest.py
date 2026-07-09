"""Tests for the rolling-origin backtest harness (Phase 1)."""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from forecasting.src.evaluate.backtest import (
    RollingOriginBacktest,
    leakage_canary,
    min_train_weeks_reaching_tail,
    splits_with_full_tail_coverage,
)
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


# ------------------------------------------------------------- end-anchored folds --

def test_min_train_weeks_reaching_tail_reserves_the_requested_test_span():
    """400 days, 4 folds x 2 weeks (14 days) = 56-day test span reserved -> the
    returned min_train_weeks should occupy (roughly) the remaining ~344 days."""
    dates = pd.date_range("2023-01-01", periods=400, freq="D")
    min_train_weeks = min_train_weeks_reaching_tail(dates, n_folds=4, test_weeks=2)
    assert min_train_weeks == (400 - 4 * 2 * 7) // 7


def test_min_train_weeks_reaching_tail_never_below_one():
    dates = pd.date_range("2023-01-01", periods=10, freq="D")
    assert min_train_weeks_reaching_tail(dates, n_folds=4, test_weeks=8) == 1


def test_end_anchored_folds_reach_the_series_final_date(demand_df):
    """The whole point of the fix: with min_train_weeks computed to reach the
    tail, the LAST fold's test window must end at (or be extended to) the
    series' true final date -- unlike the plain start-anchored default, which
    leaves the folds clustered near the series start on a long series."""
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in demand_df["business_date"].unique()])
    dates = pd.DatetimeIndex(sorted(dates))
    min_train_weeks = min_train_weeks_reaching_tail(dates, n_folds=4, test_weeks=2)
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=min_train_weeks)
    folds = list(splits_with_full_tail_coverage(bt, dates))
    assert len(folds) == 4
    _, last_test = folds[-1]
    assert last_test.max() == dates.max()


def test_end_anchored_folds_do_not_touch_earlier_fold_boundaries(demand_df):
    """splits_with_full_tail_coverage only ever extends the LAST fold; folds
    0..n-2 must be byte-identical to the plain (unwrapped) splits() output."""
    dates = pd.DatetimeIndex(sorted(
        pd.Timestamp(d) for d in demand_df["business_date"].unique()
    ))
    min_train_weeks = min_train_weeks_reaching_tail(dates, n_folds=4, test_weeks=2)
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=min_train_weeks)
    plain_folds = list(bt.splits(dates))
    covered_folds = list(splits_with_full_tail_coverage(bt, dates))
    for (plain_train, plain_test), (cov_train, cov_test) in zip(plain_folds[:-1], covered_folds[:-1]):
        assert plain_train.equals(cov_train)
        assert plain_test.equals(cov_test)
    # last fold: train untouched, test only ever grows
    assert plain_folds[-1][0].equals(covered_folds[-1][0])
    assert set(plain_folds[-1][1]).issubset(set(covered_folds[-1][1]))


def test_end_anchored_folds_still_expand_training_window(demand_df):
    dates = pd.DatetimeIndex(sorted(
        pd.Timestamp(d) for d in demand_df["business_date"].unique()
    ))
    min_train_weeks = min_train_weeks_reaching_tail(dates, n_folds=4, test_weeks=2)
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=min_train_weeks)
    sizes = [len(tr) for tr, _ in splits_with_full_tail_coverage(bt, dates)]
    for i in range(1, len(sizes)):
        assert sizes[i] > sizes[i - 1]


def test_end_anchored_folds_still_pass_leakage_check(demand_df):
    dates = pd.DatetimeIndex(sorted(
        pd.Timestamp(d) for d in demand_df["business_date"].unique()
    ))
    min_train_weeks = min_train_weeks_reaching_tail(dates, n_folds=4, test_weeks=2)
    bt = RollingOriginBacktest(n_folds=4, test_weeks=2, min_train_weeks=min_train_weeks)
    for train_dates, test_dates in splits_with_full_tail_coverage(bt, dates):
        assert test_dates.min() > train_dates.max()


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
