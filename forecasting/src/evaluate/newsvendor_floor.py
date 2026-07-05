"""The P4 dollar gate: does the quantile model + newsvendor read-off beat the
Phase-2/3 point model used AS the mean (naive prep = point forecast) in realized
dollar cost? (construction_roadmap.md Phase 4 "Done when", the second of its two
conjunctive conditions — the first, calibration, is evaluate/calibration.py's job.)

Both arms train on the IDENTICAL target — unconstrain_demand(clean_demand()), the
best available observable demand series (Phase 2's cleaning + Phase 3's censoring
correction) — so RollingOriginBacktest.run() can score them through one call with
one shared `test_df` per fold, exactly like point_floor.py. This is NOT
unconstrain_floor.py's situation (BLOCKER-1, P3_review.md): that gate compared two
arms trained on TWO DIFFERENT targets and needed a hand-built oracle-anchored
actual so both were scored on one fixed ruler. Here both arms share one target, so
the harness's own single `test_df` per fold already is that one fixed ruler —
building unconstrain_floor.py's extra machinery here would be solving a problem
this comparison doesn't have (Anti-Drift: build only what this phase needs).

_NewsvendorAdapter wraps QuantileGBMModel + the newsvendor read-off behind the
BaseBaseline fit/predict contract so it drops into the existing harness unchanged
— forecast == prep_qty (F^{-1} at the item's own critical ratio), not a naive
point prediction.

Run:  python -m forecasting.src.evaluate.newsvendor_floor
"""
from __future__ import annotations

import pandas as pd

from forecasting.src.config import load_items
from forecasting.src.data.cleaner import clean_demand
from forecasting.src.decision.newsvendor import critical_ratio, prep_quantity, required_quantile_levels
from forecasting.src.evaluate.backtest import RollingOriginBacktest
from forecasting.src.models.baselines import BaseBaseline
from forecasting.src.models.point import GlobalLGBMModel
from forecasting.src.models.quantile import QuantileGBMModel
from forecasting.src.models.unconstrain import unconstrain_demand

_POINT_MEAN_KEY = "lgbm_point_as_mean"
_NEWSVENDOR_KEY = "quantile_newsvendor"


class _NewsvendorAdapter(BaseBaseline):
    """QuantileGBMModel + newsvendor read-off, packaged as a BaseBaseline so the
    dollar gate can reuse RollingOriginBacktest unchanged (see module docstring).
    """

    def __init__(self, items: dict, quantile_levels: list[float], **model_kwargs) -> None:
        self._items = items
        self._model = QuantileGBMModel(quantile_levels=quantile_levels, **model_kwargs)

    def fit(self, demand_df: pd.DataFrame) -> "_NewsvendorAdapter":
        self._model.fit(demand_df)
        return self

    def predict(self, dates, items, service_periods) -> pd.DataFrame:
        long_preds = self._model.predict_quantiles(dates, items, service_periods)
        rows = []
        for (d, it, sp), grp in long_preds.groupby(
            ["business_date", "item_id", "service_period"], sort=False
        ):
            eco = self._items.get(it)
            if eco is None:
                continue
            r = critical_ratio(eco.co, eco.cu)
            q = prep_quantity(grp, r)
            rows.append({"business_date": d, "item_id": it, "service_period": sp, "forecast": q})
        return pd.DataFrame(rows)


def compute_newsvendor_floor(
    n_folds: int = 4,
    test_weeks: int = 4,
    min_train_weeks: int = 12,
) -> pd.DataFrame:
    """Run the point-as-mean baseline and the quantile+newsvendor policy through
    the same backtest on unconstrain_demand(clean_demand()).

    Returns the same per-(fold, baseline, item) results frame as point_floor.py /
    baseline_floor.py, with baseline in {_POINT_MEAN_KEY, _NEWSVENDOR_KEY}.
    """
    items = load_items()
    demand_df = unconstrain_demand(clean_demand()).drop(columns=["censored"])
    quantile_levels = required_quantile_levels(items)

    models = {
        _POINT_MEAN_KEY: GlobalLGBMModel(),
        _NEWSVENDOR_KEY: _NewsvendorAdapter(items, quantile_levels),
    }
    bt = RollingOriginBacktest(
        n_folds=n_folds, test_weeks=test_weeks, min_train_weeks=min_train_weeks
    )
    results = bt.run(demand_df, models, items)
    if results.empty:
        raise RuntimeError(
            "newsvendor_floor backtest produced no results — the demand series is "
            "empty or misaligned."
        )
    return results


def main() -> None:
    print("=" * 64)
    print("P4 DOLLAR GATE  (quantile + newsvendor read-off vs. point-model-as-mean)")
    print("=" * 64)
    results = compute_newsvendor_floor()
    totals = results.groupby("baseline")["dollar_cost"].sum().sort_values()
    fold = results.groupby(["baseline", "fold"])["dollar_cost"].sum().unstack("fold")
    print(totals.round(2).to_string())
    print("\nBy fold:")
    print(fold.round(2).to_string())

    point_total = float(totals[_POINT_MEAN_KEY])
    newsvendor_total = float(totals[_NEWSVENDOR_KEY])
    gap = point_total - newsvendor_total

    print(
        f"\nQuantile+newsvendor ({_NEWSVENDOR_KEY}): {newsvendor_total:,.2f}  |  "
        f"point-as-mean ({_POINT_MEAN_KEY}): {point_total:,.2f}  |  win: {gap:,.2f}"
    )
    if newsvendor_total >= point_total:
        raise SystemExit(
            f"P4 dollar gate FAILED: quantile+newsvendor ({newsvendor_total:,.2f}) does "
            f"not beat point-model-as-mean ({point_total:,.2f})."
        )
    print("P4 dollar gate: PASS")


if __name__ == "__main__":
    main()
