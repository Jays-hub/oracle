"""Tests for the P0 dollar objective and critical ratio.

Done-when criterion (construction_roadmap.md Phase 0):
  "The objective function runs on a dummy forecast and returns a dollar number."
"""
import numpy as np
import pytest

from forecasting.src.evaluate.objective import (
    critical_ratio,
    dollar_loss,
    total_realized_cost,
)


# --- dollar_loss ---

def test_exact_prep_costs_nothing():
    assert dollar_loss(prep=10, demand=10, co=14.0, cu=28.0) == 0.0


def test_overage_only():
    # prepped 12, only 10 demanded → 2 wasted at Co=$14 → $28
    assert dollar_loss(prep=12, demand=10, co=14.0, cu=28.0) == pytest.approx(28.0)


def test_underage_only():
    # prepped 8, 10 demanded → 2 stockouts at Cu=$28 → $56
    assert dollar_loss(prep=8, demand=10, co=14.0, cu=28.0) == pytest.approx(56.0)


def test_dollar_loss_never_negative():
    assert dollar_loss(prep=5, demand=5, co=10.0, cu=20.0) >= 0.0
    assert dollar_loss(prep=0, demand=5, co=10.0, cu=20.0) >= 0.0
    assert dollar_loss(prep=5, demand=0, co=10.0, cu=20.0) >= 0.0


def test_vectorized_returns_array():
    preps = np.array([10.0, 8.0, 12.0])
    demands = np.array([10.0, 10.0, 10.0])
    result = dollar_loss(preps, demands, co=14.0, cu=28.0)
    assert isinstance(result, np.ndarray)
    np.testing.assert_allclose(result, [0.0, 56.0, 28.0])


def test_asymmetry_cu_gt_co():
    # Cu > Co → underage is costlier → q* > 0.5 (prep above median)
    over_cost = dollar_loss(prep=12, demand=10, co=14.0, cu=28.0)  # 2 wasted
    under_cost = dollar_loss(prep=8, demand=10, co=14.0, cu=28.0)  # 2 short
    assert under_cost > over_cost


def test_scalar_input_returns_python_float():
    # Scalar in -> plain float out (not np.float64 leaking through).
    result = dollar_loss(prep=12, demand=10, co=14.0, cu=28.0)
    assert type(result) is float


def test_dollar_loss_rejects_nonpositive_costs():
    # Same guard as critical_ratio — a bad cost can't slip into the dollar verdict.
    with pytest.raises(ValueError):
        dollar_loss(prep=10, demand=10, co=0.0, cu=28.0)
    with pytest.raises(ValueError):
        dollar_loss(prep=10, demand=10, co=14.0, cu=-1.0)


def test_total_realized_cost_rejects_nonpositive_costs():
    with pytest.raises(ValueError):
        total_realized_cost(np.array([10.0]), np.array([10.0]), co=-14.0, cu=28.0)


# --- critical_ratio ---

def test_critical_ratio_short_rib():
    # Short rib: Co=$14, Cu=$28 → q* = 28/42 ≈ 0.667
    q = critical_ratio(co=14.0, cu=28.0)
    assert q == pytest.approx(28.0 / 42.0)


def test_critical_ratio_expensive_steak():
    # Ribeye: Co=$22, Cu=$36 → q* = 36/58 ≈ 0.621 (lean — wasting $22 hurts)
    q = critical_ratio(co=22.0, cu=36.0)
    assert q == pytest.approx(36.0 / 58.0)


def test_critical_ratio_symmetric_gives_half():
    assert critical_ratio(co=10.0, cu=10.0) == pytest.approx(0.5)


def test_critical_ratio_bounds():
    q = critical_ratio(co=5.0, cu=20.0)
    assert 0.0 < q < 1.0


def test_critical_ratio_rejects_nonpositive():
    with pytest.raises(ValueError):
        critical_ratio(co=0.0, cu=28.0)
    with pytest.raises(ValueError):
        critical_ratio(co=14.0, cu=0.0)


# --- total_realized_cost ---

def test_total_realized_cost_sums_correctly():
    preps = np.array([10.0, 8.0, 12.0])
    demands = np.array([10.0, 10.0, 10.0])
    # 0 + 56 + 28 = 84
    assert total_realized_cost(preps, demands, co=14.0, cu=28.0) == pytest.approx(84.0)


def test_total_realized_cost_returns_float():
    result = total_realized_cost(
        np.array([5.0]), np.array([5.0]), co=10.0, cu=20.0
    )
    assert isinstance(result, float)
