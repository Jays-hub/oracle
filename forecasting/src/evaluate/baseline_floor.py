"""The dollar floor: the baselines' realized cost on data/raw/ (the reproducible source
of the number P2 must beat).

This reads the OBSERVED demand series from data/raw/ ONLY (via
forecasting/src/data/loader.py) -- never the hidden ground-truth oracle. The floor is
therefore the cost of naive forecasting on the censored, polluted data the engine actually
receives, not on a truth series no model ever sees. Computing the floor on truth inflates
the target and lets a mediocre model look like a winner; that mistake is exactly what this
module exists to prevent.

The baselines are point forecasts scored AS the prep quantity (see models/baselines.py): the
newsvendor q* prep is the Phase-4 move and is deliberately not front-run into this floor.

Run:  python -m forecasting.src.evaluate.baseline_floor
"""
from __future__ import annotations

import pandas as pd

from forecasting.src.config import load_items
from forecasting.src.data.cleaner import clean_demand
from forecasting.src.data.loader import build_observed_demand
from forecasting.src.evaluate.backtest import RollingOriginBacktest
from forecasting.src.models.baselines import (
    ChefGutBaseline,
    Lag7Baseline,
    RollingMean28Baseline,
)


def compute_floor(
    n_folds: int = 4,
    test_weeks: int = 4,
    min_train_weeks: int = 12,
) -> pd.DataFrame:
    """Run the rolling-origin backtest of the naive baselines on the raw demand series.

    Returns the per-(fold, baseline, item) results frame from RollingOriginBacktest.run().
    """
    items = load_items()
    demand_df = build_observed_demand()  # data/raw/ only
    baselines = {
        "lag7": Lag7Baseline(),
        "rolling28": RollingMean28Baseline(),
        "chef_gut": ChefGutBaseline(),
    }
    bt = RollingOriginBacktest(
        n_folds=n_folds, test_weeks=test_weeks, min_train_weeks=min_train_weeks
    )
    results = bt.run(demand_df, baselines, items)
    if results.empty:
        raise RuntimeError(
            "Backtest produced no results — the raw demand series is empty or misaligned."
        )
    return results


def compute_clean_floor(
    n_folds: int = 4,
    test_weeks: int = 4,
    min_train_weeks: int = 12,
) -> pd.DataFrame:
    """Run the rolling-origin backtest on the Phase-2 cleaned demand series.

    Uses clean_demand() (comps/staff/censoring-tagged) instead of build_observed_demand()
    so the floor reflects what a model trained on the cleaned signal must beat.
    The 'censored' column produced by clean_demand is passed through but not used for
    scoring here — censored-demand unconstraining is the Phase-3 step.

    Returns the same per-(fold, baseline, item) frame as compute_floor().
    """
    items = load_items()
    demand_df = clean_demand()
    baselines = {
        "lag7": Lag7Baseline(),
        "rolling28": RollingMean28Baseline(),
        "chef_gut": ChefGutBaseline(),
    }
    bt = RollingOriginBacktest(
        n_folds=n_folds, test_weeks=test_weeks, min_train_weeks=min_train_weeks
    )
    results = bt.run(demand_df.drop(columns=["censored"]), baselines, items)
    if results.empty:
        raise RuntimeError(
            "Clean-floor backtest produced no results — cleaned demand series is empty "
            "or misaligned."
        )
    return results


def main() -> None:
    print("=" * 64)
    print("DIRTY floor  (data/raw/, naive observable — the P1 reference)")
    print("=" * 64)
    dirty = compute_floor()
    dirty_totals = dirty.groupby("baseline")["dollar_cost"].sum().sort_values()
    dirty_fold = dirty.groupby(["baseline", "fold"])["dollar_cost"].sum().unstack("fold")
    print(dirty_totals.round(2).to_string())
    print("\nBy fold:")
    print(dirty_fold.round(2).to_string())
    print(f"\nFLOOR TO BEAT (dirty, best baseline): {dirty_totals.min():,.2f}  "
          f"[{dirty_totals.idxmin()}]")

    print()
    print("=" * 64)
    print("CLEAN floor  (comps/staff stripped — the P2 model must beat this)")
    print("=" * 64)
    clean = compute_clean_floor()
    clean_totals = clean.groupby("baseline")["dollar_cost"].sum().sort_values()
    clean_fold = clean.groupby(["baseline", "fold"])["dollar_cost"].sum().unstack("fold")
    print(clean_totals.round(2).to_string())
    print("\nBy fold:")
    print(clean_fold.round(2).to_string())
    print(f"\nFLOOR TO BEAT (clean, best baseline): {clean_totals.min():,.2f}  "
          f"[{clean_totals.idxmin()}]")

    gap = dirty_totals.min() - clean_totals.min()
    print(f"\nCleaning gap (dirty − clean best): {gap:,.2f}")


if __name__ == "__main__":
    main()
