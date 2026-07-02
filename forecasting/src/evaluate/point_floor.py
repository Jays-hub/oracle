"""The dollar gate: does the P2 point model beat the Phase-1 baselines?

This reads the CLEAN demand series (via forecasting/src/data/cleaner.py) -- the signal
the point model is actually trained on -- and runs GlobalLGBMModel alongside the three
required baselines through the same RollingOriginBacktest harness baseline_floor.py
uses for the naive floor. GlobalLGBMModel implements the same fit(demand_df) /
predict(dates, items, service_periods) contract as every BaseBaseline, so it drops
into the baselines dict unchanged -- no harness fork.

This is the committed, runnable artifact for P2's dollar-gated "done when": the point
model must beat Phase-1 baselines in dollars on the backtest. Before this script, that
claim was demonstrated only ad hoc during a phase review (docs/phase_decisions/P2_review.md
BLOCKER-1) and reproduced nowhere in the repo.

Run:  python -m forecasting.src.evaluate.point_floor
"""
from __future__ import annotations

import pandas as pd

from forecasting.src.config import load_items
from forecasting.src.data.cleaner import clean_demand
from forecasting.src.evaluate.backtest import RollingOriginBacktest
from forecasting.src.models.baselines import (
    ChefGutBaseline,
    Lag7Baseline,
    RollingMean28Baseline,
)
from forecasting.src.models.point import GlobalLGBMModel

_POINT_MODEL_KEY = "lgbm_point"


def compute_point_floor(
    n_folds: int = 4,
    test_weeks: int = 4,
    min_train_weeks: int = 12,
) -> pd.DataFrame:
    """Run the point model + the three baselines through the backtest on clean_demand().

    Returns the same per-(fold, baseline, item) results frame as baseline_floor's
    compute_floor()/compute_clean_floor(), with baseline == "lgbm_point" for the GBM rows.
    """
    items = load_items()
    demand_df = clean_demand().drop(columns=["censored"])
    models = {
        "lag7": Lag7Baseline(),
        "rolling28": RollingMean28Baseline(),
        "chef_gut": ChefGutBaseline(),
        _POINT_MODEL_KEY: GlobalLGBMModel(),
    }
    bt = RollingOriginBacktest(
        n_folds=n_folds, test_weeks=test_weeks, min_train_weeks=min_train_weeks
    )
    results = bt.run(demand_df, models, items)
    if results.empty:
        raise RuntimeError(
            "point_floor backtest produced no results — the cleaned demand series is "
            "empty or misaligned."
        )
    return results


def main() -> None:
    print("=" * 64)
    print("P2 DOLLAR GATE  (clean demand — point model vs. Phase-1 baselines)")
    print("=" * 64)
    results = compute_point_floor()
    totals = results.groupby("baseline")["dollar_cost"].sum().sort_values()
    fold = results.groupby(["baseline", "fold"])["dollar_cost"].sum().unstack("fold")
    print(totals.round(2).to_string())
    print("\nBy fold:")
    print(fold.round(2).to_string())

    baseline_totals = totals.drop(_POINT_MODEL_KEY)
    best_baseline_name = baseline_totals.idxmin()
    best_baseline_total = float(baseline_totals.min())
    point_total = float(totals[_POINT_MODEL_KEY])
    gap = best_baseline_total - point_total

    print(
        f"\nPoint model ({_POINT_MODEL_KEY}): {point_total:,.2f}  |  "
        f"best baseline ({best_baseline_name}): {best_baseline_total:,.2f}  |  "
        f"win: {gap:,.2f}"
    )
    if point_total >= best_baseline_total:
        raise SystemExit(
            f"P2 dollar gate FAILED: point model ({point_total:,.2f}) does not beat "
            f"the best baseline {best_baseline_name} ({best_baseline_total:,.2f})."
        )
    print("P2 dollar gate: PASS")


if __name__ == "__main__":
    main()
