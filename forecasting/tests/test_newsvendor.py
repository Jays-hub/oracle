"""Tests for the Phase-4 newsvendor policy (forecasting/src/decision/newsvendor.py).

Pure math, no LightGBM dependency — every test builds a small hand-authored
quantile-forecast DataFrame and checks against a hand-computed (or independently
re-derived) expected value, per Step 2's "correctness test against a known
expected value, hand-computed where you can."
"""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from forecasting.src.decision.newsvendor import (
    critical_ratio,
    expected_stockout,
    expected_waste,
    prep_quantity,
    quantile_curve,
    required_quantile_levels,
    route_batch_items,
)


def _curve_df(quantiles: list[float], forecasts: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "business_date": [datetime.date(2024, 1, 1)] * len(quantiles),
        "item_id": ["item_a"] * len(quantiles),
        "service_period": ["dinner"] * len(quantiles),
        "quantile": quantiles,
        "forecast": forecasts,
    })


# ------------------------------------------------------------------ critical_ratio --

def test_critical_ratio_matches_hand_computed_value():
    # co=10, cu=15 -> q* = 15/25 = 0.6 (same numbers as evaluate/objective.py's own test suite)
    assert critical_ratio(10.0, 15.0) == pytest.approx(0.6)


@pytest.mark.parametrize("co,cu", [(0.0, 5.0), (-1.0, 5.0), (5.0, 0.0), (5.0, -1.0)])
def test_critical_ratio_rejects_non_positive_costs(co, cu):
    with pytest.raises(ValueError):
        critical_ratio(co, cu)


# ------------------------------------------------------------------ required_quantile_levels --

def test_required_quantile_levels_includes_standard_grid_and_each_items_ratio():
    class _Eco:
        def __init__(self, co, cu):
            self.co, self.cu = co, cu

    items = {"a": _Eco(10.0, 15.0), "b": _Eco(1.0, 1.0)}  # q* = 0.6 and 0.5
    standard = (0.1, 0.5, 0.9)
    levels = required_quantile_levels(items, standard_grid=standard)

    assert 0.1 in levels and 0.5 in levels and 0.9 in levels
    assert 0.6 in levels  # item a's own critical ratio, not on the standard grid
    assert levels == sorted(levels)
    assert len(levels) == len(set(levels))  # de-duplicated (item b's 0.5 already in standard)


# ------------------------------------------------------------------ route_batch_items --

def test_route_batch_items_keeps_only_batch():
    class _Eco:
        def __init__(self, prep_type):
            self.prep_type = prep_type

    items = {
        "braise": _Eco("batch"),
        "risotto": _Eco("made_to_order"),
        "burger": _Eco("batch"),
    }
    batch = route_batch_items(items)
    assert set(batch) == {"braise", "burger"}


def test_route_batch_items_matches_real_config_prep_type_enum():
    """route_batch_items must also work against a REAL config.ItemEconomics
    (prep_type is a config.PrepType, a `str, Enum` subclass, not a plain str) --
    guards the duck-typed `== "batch"` comparison against the actual type used
    everywhere else in the engine, not just a bespoke test double."""
    from forecasting.src.config import ItemEconomics, PrepType

    items = {
        "a": ItemEconomics(id="a", name="A", prep_type=PrepType.BATCH, co=1.0, cu=1.0, lead_time_days=1),
        "b": ItemEconomics(id="b", name="B", prep_type=PrepType.MADE_TO_ORDER, co=1.0, cu=1.0, lead_time_days=1),
    }
    assert set(route_batch_items(items)) == {"a"}


def test_route_batch_items_empty_when_none_are_batch():
    class _Eco:
        def __init__(self, prep_type):
            self.prep_type = prep_type

    items = {"risotto": _Eco("made_to_order")}
    assert route_batch_items(items) == {}


# ------------------------------------------------------------------ quantile_curve --

def test_quantile_curve_prepends_zero_floor_anchor():
    df = _curve_df([0.5, 1.0], [10.0, 20.0])
    xs, qs = quantile_curve(df)
    assert xs[0] == 0.0 and qs[0] == 0.0
    np.testing.assert_allclose(xs, [0.0, 10.0, 20.0])
    np.testing.assert_allclose(qs, [0.0, 0.5, 1.0])


def test_quantile_curve_skips_floor_anchor_when_already_zero():
    df = _curve_df([0.0, 0.5, 1.0], [0.0, 10.0, 20.0])
    xs, qs = quantile_curve(df)
    np.testing.assert_allclose(xs, [0.0, 10.0, 20.0])


def test_quantile_curve_rejects_crossing_quantiles():
    df = _curve_df([0.25, 0.75], [10.0, 5.0])  # forecast DECREASES as quantile increases
    with pytest.raises(ValueError, match="non-crossing"):
        quantile_curve(df)


def test_quantile_curve_sorts_unsorted_input():
    df = _curve_df([1.0, 0.5], [20.0, 10.0])  # rows out of order
    xs, qs = quantile_curve(df)
    np.testing.assert_allclose(xs, [0.0, 10.0, 20.0])
    np.testing.assert_allclose(qs, [0.0, 0.5, 1.0])


# ------------------------------------------------------------------ prep_quantity (F^-1(r)) --

def test_prep_quantity_exact_at_a_fitted_level():
    df = _curve_df([0.5, 0.75, 0.9], [10.0, 15.0, 18.0])
    assert prep_quantity(df, 0.75) == pytest.approx(15.0)


def test_prep_quantity_interpolates_between_fitted_levels():
    # Midpoint between quantile=0.5 (forecast=10) and quantile=1.0 (forecast=20):
    # r=0.75 is exactly halfway -> linear interpolation gives forecast=15.
    df = _curve_df([0.5, 1.0], [10.0, 20.0])
    assert prep_quantity(df, 0.75) == pytest.approx(15.0)


@pytest.mark.parametrize("r", [0.0, 1.0, -0.1, 1.1])
def test_prep_quantity_rejects_r_outside_open_unit_interval(r):
    df = _curve_df([0.5], [10.0])
    with pytest.raises(ValueError):
        prep_quantity(df, r)


# ------------------------------------------------------------------ expected_waste / expected_stockout --
# Hand-computed against the SAME piecewise-linear curve used by quantile_curve():
# anchors (0, 0), (10, 0.5), (20, 1.0) -- i.e. quantile=[0.5, 1.0], forecast=[10, 20].
# For Q=15 (inside the second segment, F(10)=0.5, F(20)=1.0, F(15)=0.75 by linearity):
#   waste    = integral_0^15 F(x)dx
#            = integral_0^10 F dx (triangle, 0->0.5 over [0,10])  = 0.5*10*0.5      = 2.5
#            + integral_10^15 F dx (trapezoid, 0.5->0.75 over 5)  = (0.5+0.75)/2*5  = 3.125
#            = 5.625
#   stockout = integral_15^20 (1-F)dx = trapezoid, (1-0.75)+(1-1.0))/2 * 5 = 0.625

def test_expected_waste_matches_hand_computed_trapezoidal_integral():
    df = _curve_df([0.5, 1.0], [10.0, 20.0])
    assert expected_waste(df, 15.0) == pytest.approx(5.625)


def test_expected_stockout_matches_hand_computed_trapezoidal_integral():
    df = _curve_df([0.5, 1.0], [10.0, 20.0])
    assert expected_stockout(df, 15.0) == pytest.approx(0.625)


def test_expected_waste_is_zero_at_or_below_the_floor():
    df = _curve_df([0.5, 1.0], [10.0, 20.0])
    assert expected_waste(df, 0.0) == 0.0
    assert expected_waste(df, -5.0) == 0.0


def test_expected_stockout_is_zero_at_or_above_the_top_fitted_level():
    df = _curve_df([0.5, 1.0], [10.0, 20.0])
    assert expected_stockout(df, 20.0) == 0.0
    assert expected_stockout(df, 25.0) == 0.0


def test_expected_waste_and_stockout_bracket_a_uniform_distribution():
    """Independent re-derivation, not a tautology: for D ~ Uniform(0, 100) (whose
    quantile function IS exactly piecewise-linear, so the grid approximation is
    exact), the closed-form newsvendor identities are
        E[(Q-D)^+] = Q^2 / (2*100),  E[(D-Q)^+] = (100-Q)^2 / (2*100).
    Fit the grid at fine-enough levels that the closed form and this module's
    trapezoidal integration agree to a tight tolerance.
    """
    # Grid stops at quantile=0.99 (forecast=99), one short of the true support's
    # right edge (100) -- the documented truncation ("top fitted level treated as
    # the effective right tail"). That truncation is negligible for interior Q, but
    # measurable for Q=90 (close to the truncation boundary itself); use a looser,
    # explicitly-justified tolerance there instead of hiding the approximation.
    levels = [i / 100 for i in range(1, 100)]
    forecasts = [q * 100.0 for q in levels]  # F^-1(q) = 100q for Uniform(0,100)
    df = _curve_df(levels, forecasts)

    for Q, stockout_tol in [(10.0, 1e-3), (37.5, 1e-3), (50.0, 1e-3), (90.0, 2e-2)]:
        expected_w = Q**2 / (2 * 100)
        expected_s = (100 - Q) ** 2 / (2 * 100)
        assert expected_waste(df, Q) == pytest.approx(expected_w, rel=1e-3)
        assert expected_stockout(df, Q) == pytest.approx(expected_s, rel=stockout_tol)


def test_waste_plus_stockout_relates_to_mean_minus_prep():
    """Structural identity check: E[(Q-D)^+] - E[(D-Q)^+] = Q - E[D] for any
    distribution. Verified here against the same fine Uniform(0,100) grid
    (E[D] = 50 exactly), independent of the hand-computed segment tests above.
    """
    levels = [i / 100 for i in range(1, 100)]
    forecasts = [q * 100.0 for q in levels]
    df = _curve_df(levels, forecasts)
    mean_d = 50.0
    for Q in [20.0, 50.0, 80.0]:
        waste = expected_waste(df, Q)
        stockout = expected_stockout(df, Q)
        assert (waste - stockout) == pytest.approx(Q - mean_d, abs=0.5)
