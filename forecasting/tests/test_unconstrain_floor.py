"""Tests for the Phase-3 dollar-gate helpers (forecasting/src/evaluate/unconstrain_floor.py).

Scoped to the pure/composable helper functions with synthetic fixtures -- like the
other evaluate/*.py gate scripts (point_floor.py, baseline_floor.py, cleaning_check.py),
compute_unconstrain_floor() itself is exercised manually against real generated
data/raw/ + data/_truth/ (via `python -m`), not through pytest, since a fresh
checkout has no generated data for it to run against. These tests instead guard the
two specific defect classes P3_review.md found: an asymmetric scoring ruler
(BLOCKER-1) and a fold-boundary coverage gap (MINOR-1).
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest

from forecasting.src.evaluate.backtest import RollingOriginBacktest
from forecasting.src.evaluate.unconstrain_floor import (
    _min_train_weeks_reaching_tail,
    _oracle_actual,
    _splits_with_full_tail_coverage,
)


# ------------------------------------------------------------------ _oracle_actual --

def _clean_row(d, item_id, demand, censored=False, sp="dinner"):
    return {"business_date": d, "item_id": item_id, "service_period": sp,
            "demand": demand, "censored": censored}


def _write_truth_demand(truth_dir, rows):
    truth_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(truth_dir / "truth_demand.csv", index=False)


def test_oracle_actual_replaces_only_censored_rows(tmp_path):
    """BLOCKER-1 regression guard: the scoring ruler must raise ONLY the censored
    rows to their real true_demand -- an uncensored row's already-true observed
    value must pass through completely unchanged."""
    truth_dir = tmp_path / "_truth"
    d1, d2 = datetime.date(2024, 5, 1), datetime.date(2024, 5, 2)
    clean = pd.DataFrame([
        _clean_row(d1, "item_a", demand=10, censored=False),
        _clean_row(d2, "item_a", demand=12, censored=True),  # capped; true was higher
    ])
    _write_truth_demand(truth_dir, [
        {"business_date": d1, "item_id": "item_a", "service_period": "dinner", "true_demand": 10},
        {"business_date": d2, "item_id": "item_a", "service_period": "dinner", "true_demand": 19},
    ])
    ruler = _oracle_actual(clean, truth_dir=truth_dir)

    uncensored = ruler[ruler["business_date"] == d1]["demand"].iloc[0]
    censored = ruler[ruler["business_date"] == d2]["demand"].iloc[0]
    assert uncensored == 10, "uncensored row's observed value must be untouched"
    assert censored == 19, "censored row must be raised to the ORACLE's true_demand, not left capped"


def test_oracle_actual_is_identical_regardless_of_which_arm_it_scores():
    """The core BLOCKER-1 invariant: the ruler is a pure function of clean_demand()
    and the oracle -- it never depends on which model/target is being scored, so
    computing it once and reusing it for both arms (as compute_unconstrain_floor
    does) cannot reintroduce an asymmetric-ruler bug by construction."""
    import inspect
    sig = inspect.signature(_oracle_actual)
    assert "baseline" not in sig.parameters and "target" not in sig.parameters, (
        "_oracle_actual must not take a per-arm/per-model parameter -- if it ever "
        "does, the two arms could diverge onto different rulers again"
    )


def test_oracle_actual_raises_on_missing_truth_row(tmp_path):
    truth_dir = tmp_path / "_truth"
    d1, d2 = datetime.date(2024, 5, 1), datetime.date(2024, 5, 2)
    clean = pd.DataFrame([_clean_row(d1, "item_a", demand=10, censored=True)])
    # A truth file with rows, but none matching item_a on d1 -- the merge misses.
    _write_truth_demand(truth_dir, [
        {"business_date": d2, "item_id": "item_b", "service_period": "dinner", "true_demand": 5},
    ])
    with pytest.raises(RuntimeError, match="no matching truth_demand"):
        _oracle_actual(clean, truth_dir=truth_dir)


# ------------------------------------------------------------------ tail coverage --

def test_splits_with_full_tail_coverage_reaches_series_max_date():
    """MINOR-1 regression guard: RollingOriginBacktest's week-granularity test
    windows can leave the last few days of a series uncovered. The wrapped
    generator must extend exactly the LAST fold so its test window reaches the
    series' true final date."""
    all_dates = pd.DatetimeIndex(pd.date_range("2022-01-01", "2024-06-30", freq="D"))
    bt = RollingOriginBacktest(n_folds=4, test_weeks=4, min_train_weeks=114)

    plain_folds = list(bt.splits(all_dates))
    covered_folds = list(_splits_with_full_tail_coverage(bt, all_dates))

    assert plain_folds[-1][1].max() < all_dates.max(), (
        "test premise: the plain (unfixed) last fold must fall short of the series "
        "end, or this test isn't exercising the gap it's meant to guard"
    )
    assert covered_folds[-1][1].max() == all_dates.max(), (
        "the wrapped last fold must reach the series' true final date"
    )


def test_splits_with_full_tail_coverage_does_not_touch_other_folds():
    """The fix must be surgical: every fold except the last must be byte-identical
    to RollingOriginBacktest's own output, including the last fold's own START --
    only its END may move. (An earlier, rejected version of this fix trimmed days
    off the series START instead, which shifted every fold's boundaries and
    materially changed the dollar result along with the coverage -- see
    docs/phase_decisions/P3_review.md and unconstrain_floor.py's module docstring.)
    """
    all_dates = pd.DatetimeIndex(pd.date_range("2022-01-01", "2024-06-30", freq="D"))
    bt = RollingOriginBacktest(n_folds=4, test_weeks=4, min_train_weeks=114)

    plain_folds = list(bt.splits(all_dates))
    covered_folds = list(_splits_with_full_tail_coverage(bt, all_dates))

    assert len(plain_folds) == len(covered_folds)
    for idx, ((p_train, p_test), (c_train, c_test)) in enumerate(zip(plain_folds, covered_folds)):
        assert p_train.equals(c_train), f"fold {idx} train window must be untouched"
        if idx < len(plain_folds) - 1:
            assert p_test.equals(c_test), f"fold {idx} test window must be untouched (only the last fold may extend)"
        else:
            assert c_test.min() == p_test.min(), "the last fold's test START must not move, only its end"


def test_min_train_weeks_reaching_tail_reserves_the_requested_test_span():
    dates = pd.Series(pd.date_range("2022-01-01", "2024-06-30", freq="D"))
    n_folds, test_weeks = 4, 4
    min_train_weeks = _min_train_weeks_reaching_tail(dates, n_folds, test_weeks)

    total_days = (dates.max() - dates.min()).days + 1
    test_span_days = n_folds * test_weeks * 7
    assert min_train_weeks * 7 + test_span_days <= total_days, (
        "the computed training window plus the full test span must fit inside the "
        "available history"
    )
    # And it should leave less than a week unused (otherwise the tail isn't tight).
    assert total_days - (min_train_weeks * 7 + test_span_days) < 7
