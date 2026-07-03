"""Tests for the Phase-3 demand unconstrainer (forecasting/src/models/unconstrain.py)."""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from forecasting.src.models.unconstrain import unconstrain_demand


def _row(d: datetime.date, demand: int, censored: bool = False,
         item_id: str = "item_a", service_period: str = "dinner") -> dict:
    return {
        "business_date": d,
        "item_id": item_id,
        "service_period": service_period,
        "demand": demand,
        "censored": censored,
    }


def _expected_tail_mean(values: list[float], cap: float) -> float:
    """Independent (non-module) re-derivation of E[D | D > cap] via method-of-
    moments NegBin/Poisson -- mirrors unconstrain.py's documented formula but
    calls scipy directly, so it is a real correctness check, not a tautology."""
    arr = np.array(values, dtype=float)
    mean, var = arr.mean(), arr.var(ddof=1)
    if var > mean:
        r = mean**2 / (var - mean)
        p = r / (r + mean)
        dist = stats.nbinom(r, p)
    else:
        dist = stats.poisson(mean)
    return float(dist.expect(lambda k: k, lb=cap + 1, conditional=True))


# ------------------------------------------------------------------ correctness --

def test_fine_grain_hand_computed_correction():
    """8 uncensored Mondays meet min_history=8 at the fine (item, service_period,
    weekday) grain, so the estimate must be E[D | D > cap] of a NegBin/Poisson
    fit to exactly those 8 values -- independently re-derived via scipy, not by
    calling the module's own helper."""
    values = [10, 12, 8, 14, 11, 9, 13, 15]
    mondays = [datetime.date(2024, 1, 1) + datetime.timedelta(weeks=i) for i in range(9)]
    rows = [_row(mondays[i], v) for i, v in enumerate(values)]
    cap = 7
    rows.append(_row(mondays[8], cap, censored=True))

    out = unconstrain_demand(pd.DataFrame(rows), min_history=8)
    corrected = out[out["business_date"] == mondays[8]]["demand"].iloc[0]

    expected = _expected_tail_mean(values, cap)
    assert corrected == pytest.approx(expected)
    assert corrected > cap  # the whole point: recovery must exceed the observed cap


def test_coarse_fallback_hand_computed_correction():
    """Only 2 prior same-weekday (Monday) uncensored observations exist (below
    min_history=8), so the estimate must fall back to the coarser (item,
    service_period) grain -- fit against all 8 prior uncensored rows regardless
    of weekday."""
    coarse_values = [10, 20, 30, 40, 5, 15, 25, 14]  # 8 values, various weekdays
    dates = [
        datetime.date(2024, 1, 1),   # Mon
        datetime.date(2024, 1, 2),   # Tue
        datetime.date(2024, 1, 3),   # Wed
        datetime.date(2024, 1, 4),   # Thu
        datetime.date(2024, 1, 5),   # Fri
        datetime.date(2024, 1, 6),   # Sat
        datetime.date(2024, 1, 7),   # Sun
        datetime.date(2024, 1, 8),   # Mon (2nd Monday)
    ]
    rows = [_row(d, v) for d, v in zip(dates, coarse_values)]
    cap = 5
    censored_date = datetime.date(2024, 1, 15)  # 3rd Monday, censored
    rows.append(_row(censored_date, cap, censored=True))

    out = unconstrain_demand(pd.DataFrame(rows), min_history=8)
    corrected = out[out["business_date"] == censored_date]["demand"].iloc[0]

    expected = _expected_tail_mean(coarse_values, cap)
    assert corrected == pytest.approx(expected)


def test_poisson_fallback_when_not_overdispersed():
    """When prior history is NOT overdispersed (var <= mean), the fit must use
    Poisson, not Negative Binomial -- a near-constant history triggers this."""
    values = [10, 10, 11, 9, 10, 10, 11, 9]  # low variance, var <= mean
    assert np.var(values, ddof=1) <= np.mean(values)  # sanity-check the premise
    mondays = [datetime.date(2024, 1, 1) + datetime.timedelta(weeks=i) for i in range(9)]
    rows = [_row(mondays[i], v) for i, v in enumerate(values)]
    cap = 8
    rows.append(_row(mondays[8], cap, censored=True))

    out = unconstrain_demand(pd.DataFrame(rows), min_history=8)
    corrected = out[out["business_date"] == mondays[8]]["demand"].iloc[0]

    expected = _expected_tail_mean(values, cap)  # helper picks Poisson too (same rule)
    assert corrected == pytest.approx(expected)


def test_extreme_cap_falls_back_to_minimal_nudge():
    """A cap far beyond what the fitted distribution considers plausible (tail
    probability underflows) must return a small nudge above cap, not raise or
    return NaN/inf from an unstable near-zero-probability division."""
    values = [1, 2, 1, 0, 1, 2, 1, 1]  # low mean (~1.1) -> tight distribution
    mondays = [datetime.date(2024, 1, 1) + datetime.timedelta(weeks=i) for i in range(9)]
    rows = [_row(mondays[i], v) for i, v in enumerate(values)]
    cap = 50  # wildly beyond this distribution's plausible range
    rows.append(_row(mondays[8], cap, censored=True))

    out = unconstrain_demand(pd.DataFrame(rows), min_history=8)
    corrected = out[out["business_date"] == mondays[8]]["demand"].iloc[0]
    assert np.isfinite(corrected)
    assert corrected == pytest.approx(cap + 1.0)


def test_cold_start_censored_row_left_unchanged():
    """The very first row ever seen for an (item, service_period) has zero prior
    history at both grains -- there is no basis for a correction, so the censored
    row's observed value must pass through unchanged."""
    rows = [_row(datetime.date(2024, 1, 1), 3, censored=True)]
    out = unconstrain_demand(pd.DataFrame(rows))
    assert out["demand"].iloc[0] == pytest.approx(3.0)


def test_uncensored_rows_never_modified():
    """censored=False rows must carry their original demand value through untouched,
    regardless of what happens elsewhere in the series."""
    rng = np.random.default_rng(42)
    start = datetime.date(2024, 1, 1)
    rows = []
    for offset in range(30):
        d = start + datetime.timedelta(days=offset)
        censored = offset in (10, 20)
        demand = int(rng.poisson(10))
        rows.append(_row(d, demand, censored=censored))
    df = pd.DataFrame(rows)
    out = unconstrain_demand(df)
    uncensored_in = df[~df["censored"]].set_index("business_date")["demand"]
    uncensored_out = out[~out["censored"]].set_index("business_date")["demand"]
    pd.testing.assert_series_equal(
        uncensored_in.sort_index().astype(float), uncensored_out.sort_index(), check_names=False
    )


def test_recovered_never_below_observed():
    """The one structural invariant that must always hold: a censored observation
    is a LOWER bound on true demand, so recovery can only raise the target, never
    lower it -- checked across a whole randomized series, not just one hand-picked row."""
    rng = np.random.default_rng(7)
    start = datetime.date(2024, 1, 1)
    rows = []
    for offset in range(120):
        d = start + datetime.timedelta(days=offset)
        censored = bool(rng.random() < 0.15)
        demand = int(rng.poisson(8))
        rows.append(_row(d, demand, censored=censored))
    df = pd.DataFrame(rows)
    out = unconstrain_demand(df)
    merged = df.merge(out, on=["business_date", "item_id", "service_period"], suffixes=("_in", "_out"))
    assert (merged["demand_out"] >= merged["demand_in"]).all()


# ------------------------------------------------------------------ reproducibility --

def test_reproducible_across_repeated_calls():
    """Same input twice must produce byte-identical output -- no hidden randomness
    or mutable shared state."""
    rng = np.random.default_rng(3)
    start = datetime.date(2024, 1, 1)
    rows = [
        _row(start + datetime.timedelta(days=i), int(rng.poisson(9)), censored=(i % 9 == 0))
        for i in range(60)
    ]
    df = pd.DataFrame(rows)
    out1 = unconstrain_demand(df)
    out2 = unconstrain_demand(df)
    pd.testing.assert_frame_equal(out1, out2)


# ------------------------------------------------------------------ leakage guard --

def test_correction_is_prefix_stable():
    """A row's correction must depend only on data strictly before its own date --
    truncating the series to end exactly at a censored row's date must produce the
    SAME corrected value for that row as running on the full series. If a future
    date could change a past row's correction, that would be target leakage of
    exactly the kind rule 02-feature-eng forbids for features."""
    rng = np.random.default_rng(11)
    start = datetime.date(2024, 1, 1)
    rows = []
    for offset in range(80):
        d = start + datetime.timedelta(days=offset)
        censored = offset in (30, 60)
        demand = int(rng.poisson(9))
        if censored:
            demand = 2  # a deliberately low capped value
        rows.append(_row(d, demand, censored=censored))
    df = pd.DataFrame(rows)
    target_date = start + datetime.timedelta(days=30)

    full_out = unconstrain_demand(df)
    truncated_out = unconstrain_demand(df[df["business_date"] <= target_date].copy())

    full_val = full_out[full_out["business_date"] == target_date]["demand"].iloc[0]
    truncated_val = truncated_out[truncated_out["business_date"] == target_date]["demand"].iloc[0]
    assert full_val == pytest.approx(truncated_val)
    # And it must have actually been corrected (not a vacuous comparison of two unchanged 2.0s).
    assert full_val > 2.0


# ------------------------------------------------------------------ schema / edge cases --

def test_output_schema_and_dtypes():
    rows = [_row(datetime.date(2024, 1, 1), 5), _row(datetime.date(2024, 1, 2), 3, censored=True)]
    out = unconstrain_demand(pd.DataFrame(rows))
    assert list(out.columns) == ["business_date", "item_id", "service_period", "demand", "censored"]
    assert isinstance(out["business_date"].iloc[0], datetime.date)
    assert out["demand"].dtype.kind == "f"
    assert (out["demand"] >= 0).all()
    assert out["censored"].dtype == bool


def test_missing_required_column_raises():
    df = pd.DataFrame([{"business_date": datetime.date(2024, 1, 1), "item_id": "item_a",
                         "service_period": "dinner", "demand": 5}])  # no 'censored' column
    with pytest.raises(ValueError, match="missing required columns"):
        unconstrain_demand(df)


def test_empty_input_returns_empty_output():
    df = pd.DataFrame(columns=["business_date", "item_id", "service_period", "demand", "censored"])
    out = unconstrain_demand(df)
    assert out.empty
    assert list(out.columns) == ["business_date", "item_id", "service_period", "demand", "censored"]
