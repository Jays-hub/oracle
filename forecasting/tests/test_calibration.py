"""Tests for the Phase-4 calibration checkpoint (forecasting/src/evaluate/calibration.py).

Scoped to the pure/composable helper functions with synthetic fixtures — like the
other evaluate/*.py gate scripts (point_floor.py, unconstrain_floor.py,
cleaning_check.py; see test_unconstrain_floor.py's own docstring), the full
compute_calibration()/conformal_coverage() functions are exercised manually
against real generated data/raw/ + data/_truth/ (via `python -m`), not through
pytest, since a fresh checkout has no generated data for them to run against.
"""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from forecasting.src.evaluate.calibration import (
    _train_test_tail_split,
    empirical_coverage,
    pit_values,
)


def _pred_row(d, item_id, sp, quantile, forecast):
    return {
        "business_date": d, "item_id": item_id, "service_period": sp,
        "quantile": quantile, "forecast": forecast,
    }


def _truth_row(d, item_id, sp, true_demand):
    return {
        "business_date": d, "item_id": item_id, "service_period": sp,
        "true_demand": true_demand,
    }


# ------------------------------------------------------------------ empirical_coverage --

def test_empirical_coverage_matches_hand_computed_fractions():
    """Two item-days at quantile=0.5: forecast=10 covers one truth (8) but not the
    other (12) -> empirical coverage at q=0.5 should be exactly 0.5, matching a
    hand count, not just "close to nominal"."""
    d1, d2 = datetime.date(2024, 1, 1), datetime.date(2024, 1, 2)
    preds = pd.DataFrame([
        _pred_row(d1, "item_a", "dinner", 0.5, 10.0),
        _pred_row(d2, "item_a", "dinner", 0.5, 10.0),
    ])
    truth = pd.DataFrame([
        _truth_row(d1, "item_a", "dinner", 8.0),   # 8 <= 10 -> covered
        _truth_row(d2, "item_a", "dinner", 12.0),  # 12 <= 10 is False -> not covered
    ])
    coverage = empirical_coverage(preds, truth)
    assert len(coverage) == 1
    row = coverage.iloc[0]
    assert row["quantile"] == 0.5
    assert row["empirical"] == pytest.approx(0.5)
    assert row["n"] == 2


def test_empirical_coverage_one_row_per_fitted_quantile_level():
    d1 = datetime.date(2024, 1, 1)
    preds = pd.DataFrame([
        _pred_row(d1, "item_a", "dinner", 0.1, 2.0),
        _pred_row(d1, "item_a", "dinner", 0.9, 18.0),
    ])
    truth = pd.DataFrame([_truth_row(d1, "item_a", "dinner", 10.0)])
    coverage = empirical_coverage(preds, truth)
    assert sorted(coverage["quantile"]) == [0.1, 0.9]
    # 10 <= 2 is False (q=0.1 not covered); 10 <= 18 is True (q=0.9 covered)
    assert coverage.set_index("quantile").loc[0.1, "empirical"] == 0.0
    assert coverage.set_index("quantile").loc[0.9, "empirical"] == 1.0


def test_empirical_coverage_raises_on_no_overlap():
    preds = pd.DataFrame([_pred_row(datetime.date(2024, 1, 1), "item_a", "dinner", 0.5, 10.0)])
    truth = pd.DataFrame([_truth_row(datetime.date(2024, 1, 2), "item_b", "lunch", 5.0)])
    with pytest.raises(RuntimeError, match="no overlapping rows"):
        empirical_coverage(preds, truth)


# ------------------------------------------------------------------ pit_values --

def test_pit_values_matches_hand_computed_interpolation():
    """One item-day, quantile curve (0,0)-(10,0.5)-(20,1.0) (same anchors as
    test_newsvendor.py's hand-computed integral tests); true_demand=15 sits exactly
    halfway through the second segment (F(10)=0.5, F(20)=1.0) -> PIT = 0.75."""
    d1 = datetime.date(2024, 1, 1)
    preds = pd.DataFrame([
        _pred_row(d1, "item_a", "dinner", 0.5, 10.0),
        _pred_row(d1, "item_a", "dinner", 1.0, 20.0),
    ])
    truth = pd.DataFrame([_truth_row(d1, "item_a", "dinner", 15.0)])
    pits = pit_values(preds, truth)
    assert len(pits) == 1
    assert pits[0] == pytest.approx(0.75)


def test_pit_values_clamps_actual_outside_the_fitted_range():
    """A true_demand far above the top fitted quantile must clamp to PIT=1.0 (not
    extrapolate past the curve, and not raise)."""
    d1 = datetime.date(2024, 1, 1)
    preds = pd.DataFrame([
        _pred_row(d1, "item_a", "dinner", 0.5, 10.0),
        _pred_row(d1, "item_a", "dinner", 0.99, 20.0),
    ])
    truth = pd.DataFrame([_truth_row(d1, "item_a", "dinner", 1000.0)])
    pits = pit_values(preds, truth)
    assert pits[0] == pytest.approx(0.99)


def test_pit_values_are_reasonably_uniform_for_a_well_calibrated_model():
    """Independent re-derivation: if the fitted quantile curve for every item-day
    IS the true generating distribution exactly (Uniform(0,100)), PIT values are
    exactly the quantile-transform of Uniform draws -- i.e. themselves ~Uniform(0,1)
    with mean ~0.5. Built from many synthetic item-days, not a single row."""
    rng = np.random.default_rng(0)
    levels = [i / 100 for i in range(1, 100)]
    rows_pred, rows_truth = [], []
    for i in range(200):
        d = datetime.date(2024, 1, 1) + datetime.timedelta(days=i)
        for q in levels:
            rows_pred.append(_pred_row(d, "item_a", "dinner", q, q * 100.0))
        true_demand = float(rng.uniform(0, 100))
        rows_truth.append(_truth_row(d, "item_a", "dinner", true_demand))
    preds = pd.DataFrame(rows_pred)
    truth = pd.DataFrame(rows_truth)

    pits = pit_values(preds, truth)
    assert len(pits) == 200
    assert pits.mean() == pytest.approx(0.5, abs=0.05)


# ------------------------------------------------------------------ _train_test_tail_split --

def test_train_test_tail_split_reserves_exactly_the_requested_tail():
    dates = pd.date_range("2024-01-01", "2024-04-30", freq="D")
    demand_df = pd.DataFrame({
        "business_date": dates, "item_id": "item_a", "service_period": "dinner", "demand": 1,
    })
    train_df, test_dates = _train_test_tail_split(demand_df, test_weeks=2)

    assert len(test_dates) == 14
    assert max(train_df["business_date"]) < min(test_dates)
    assert set(train_df["business_date"]).isdisjoint(set(test_dates))


def test_train_test_tail_split_raises_when_history_too_short():
    dates = pd.date_range("2024-01-01", "2024-01-05", freq="D")
    demand_df = pd.DataFrame({
        "business_date": dates, "item_id": "item_a", "service_period": "dinner", "demand": 1,
    })
    with pytest.raises(ValueError, match="Not enough history"):
        _train_test_tail_split(demand_df, test_weeks=4)
