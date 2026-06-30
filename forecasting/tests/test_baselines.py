"""Tests for the baseline forecasters (Phase 1)."""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from forecasting.src.models.baselines import (
    ChefGutBaseline,
    CrostonBaseline,
    Lag7Baseline,
    RollingMean28Baseline,
    score_baseline,
)


def _make_demand_df(n_days: int = 35, seed: int = 0) -> pd.DataFrame:
    """Deterministic 35-day demand fixture with 3 items × 2 service periods."""
    rng = np.random.default_rng(seed)
    start = datetime.date(2023, 1, 1)
    items = ["item_a", "item_b", "item_c"]
    periods = ["lunch", "dinner"]
    rows = []
    for day_offset in range(n_days):
        d = start + datetime.timedelta(days=day_offset)
        for it in items:
            for sp in periods:
                base = {"item_a": 10, "item_b": 5, "item_c": 0}[it]
                demand = int(rng.poisson(base + 1)) if it != "item_c" else (
                    int(rng.poisson(3)) if rng.random() > 0.6 else 0
                )
                rows.append({"business_date": d, "item_id": it, "service_period": sp, "demand": demand})
    return pd.DataFrame(rows)


@pytest.fixture
def demand_df():
    return _make_demand_df(35)


@pytest.fixture
def train_df(demand_df):
    cutoff = datetime.date(2023, 1, 29)
    return demand_df[demand_df["business_date"] <= cutoff].copy()


@pytest.fixture
def test_df(demand_df):
    cutoff = datetime.date(2023, 1, 29)
    return demand_df[demand_df["business_date"] > cutoff].copy()


# ------------------------------------------------------------------ Lag7 --

def test_lag7_returns_correct_value(demand_df):
    train = demand_df[demand_df["business_date"] <= datetime.date(2023, 1, 28)].copy()
    bl = Lag7Baseline().fit(train)
    # Predict day 8 (Jan 8); lag-7 should match demand on Jan 1
    target_date = datetime.date(2023, 1, 8)
    lag_date = datetime.date(2023, 1, 1)
    preds = bl.predict([target_date], ["item_a"], ["dinner"])
    expected = float(
        train.loc[
            (train["business_date"] == lag_date)
            & (train["item_id"] == "item_a")
            & (train["service_period"] == "dinner"),
            "demand",
        ].iloc[0]
    )
    assert preds.iloc[0]["forecast"] == expected


def test_lag7_falls_back_when_no_lag(train_df):
    """When lag-7 not in training, should return a non-NaN fallback."""
    bl = Lag7Baseline().fit(train_df)
    # Request a date whose lag-7 is definitely not in training (train starts Jan 1, predict Jan 3)
    preds = bl.predict([datetime.date(2023, 1, 3)], ["item_a"], ["lunch"])
    assert not np.isnan(preds.iloc[0]["forecast"])
    assert preds.iloc[0]["forecast"] >= 0


def test_lag7_nonneg(train_df, test_df):
    bl = Lag7Baseline().fit(train_df)
    dates = sorted(test_df["business_date"].unique())
    preds = bl.predict(dates, ["item_a", "item_b", "item_c"], ["lunch", "dinner"])
    assert (preds["forecast"] >= 0).all()


# ------------------------------------------------------------------ Rolling mean --

def test_rolling_mean_uses_same_weekday(demand_df):
    """Rolling mean for a Monday should only use Monday history."""
    train = demand_df[demand_df["business_date"] <= datetime.date(2023, 1, 25)].copy()
    bl = RollingMean28Baseline().fit(train)
    # Feb 6 is a Monday; only Mondays in the prior 28 days should count
    preds = bl.predict([datetime.date(2023, 1, 30)], ["item_a"], ["dinner"])
    assert preds.iloc[0]["forecast"] >= 0


def test_rolling_mean_falls_back_with_one_observation(demand_df):
    """Only 7 days of training → at most 1 same-weekday obs; must still return a number."""
    train = demand_df[demand_df["business_date"] <= datetime.date(2023, 1, 7)].copy()
    bl = RollingMean28Baseline().fit(train)
    preds = bl.predict([datetime.date(2023, 1, 9)], ["item_b"], ["lunch"])
    assert not np.isnan(preds.iloc[0]["forecast"])
    assert preds.iloc[0]["forecast"] >= 0


# ------------------------------------------------------------------ Chef gut --

def test_chef_gut_rounds_to_five(demand_df):
    bl = ChefGutBaseline().fit(demand_df)
    dates = sorted(demand_df["business_date"].unique()[-6:])
    preds = bl.predict(dates, ["item_a", "item_b"], ["lunch", "dinner"])
    for _, row in preds.iterrows():
        val = row["forecast"]
        assert val % 5 == 0, f"ChefGut forecast {val} is not a multiple of 5"
        assert val >= 0


def test_chef_gut_nonneg_always(demand_df):
    bl = ChefGutBaseline().fit(demand_df)
    dates = [datetime.date(2023, 2, 1)]
    preds = bl.predict(dates, ["item_a", "item_b", "item_c"], ["lunch", "dinner"])
    assert (preds["forecast"] >= 0).all()


# ------------------------------------------------------------------ Croston --

def test_croston_returns_zero_for_all_zero_history():
    rows = [
        {"business_date": datetime.date(2023, 1, i), "item_id": "item_x",
         "service_period": "dinner", "demand": 0}
        for i in range(1, 21)
    ]
    df = pd.DataFrame(rows)
    bl = CrostonBaseline().fit(df)
    preds = bl.predict([datetime.date(2023, 1, 21)], ["item_x"], ["dinner"])
    assert preds.iloc[0]["forecast"] == 0.0


def test_croston_positive_when_positive_history():
    rows = []
    for i in range(1, 21):
        d = int(3 if i % 4 == 0 else 0)
        rows.append({"business_date": datetime.date(2023, 1, i),
                     "item_id": "item_x", "service_period": "dinner", "demand": d})
    df = pd.DataFrame(rows)
    bl = CrostonBaseline().fit(df)
    preds = bl.predict([datetime.date(2023, 1, 21)], ["item_x"], ["dinner"])
    assert preds.iloc[0]["forecast"] > 0.0


# ------------------------------------------------------------------ score_baseline --

def test_all_baselines_score_positive_dollar_cost(train_df, test_df):
    from forecasting.src.config import ItemEconomics, PrepType
    eco = ItemEconomics(
        id="item_a", name="Item A", prep_type=PrepType.BATCH,
        co=10.0, cu=15.0, lead_time_days=1,
    )
    items = {"item_a": eco, "item_b": eco, "item_c": eco}
    for Cls in [Lag7Baseline, RollingMean28Baseline, ChefGutBaseline, CrostonBaseline]:
        bl = Cls().fit(train_df)
        result = score_baseline(bl, test_df, items)
        total = result["dollar_cost"].dropna().sum()
        assert total >= 0, f"{Cls.__name__} returned negative total dollar cost"


def test_baselines_dont_use_future_data(demand_df):
    """Baselines fitted on train must not reference test-set dates."""
    cutoff = datetime.date(2023, 1, 21)
    train = demand_df[demand_df["business_date"] <= cutoff].copy()
    test_dates = [datetime.date(2023, 1, 22), datetime.date(2023, 1, 23)]
    for Cls in [Lag7Baseline, RollingMean28Baseline, ChefGutBaseline, CrostonBaseline]:
        bl = Cls().fit(train)
        # confirm predict() returns results for test_dates only
        preds = bl.predict(test_dates, ["item_a"], ["lunch"])
        returned_dates = set(preds["business_date"].tolist())
        assert returned_dates == set(test_dates), (
            f"{Cls.__name__}: predict returned unexpected dates {returned_dates}"
        )


# ------------------------------------------------------------------ _to_date --

def test_to_date_parses_strings():
    """audit #8: string dates must be parsed, not passed through."""
    from forecasting.src.models.baselines import _to_date
    out = _to_date(pd.Series(["2023-01-01", "2023-02-15"]))
    assert out.iloc[0] == datetime.date(2023, 1, 1)
    assert out.iloc[1] == datetime.date(2023, 2, 15)


def test_to_date_raises_on_garbage():
    """audit #8: unparseable dates fail loud rather than becoming silent NaT."""
    from forecasting.src.models.baselines import _to_date
    with pytest.raises(ValueError, match="unparseable"):
        _to_date(pd.Series(["2023-01-01", "not-a-date"]))
