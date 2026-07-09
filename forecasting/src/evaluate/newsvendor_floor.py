"""The P4 dollar gate: does the quantile model + newsvendor read-off beat the
Phase-2/3 point model used AS the mean (naive prep = point forecast) in realized
dollar cost? (construction_roadmap.md Phase 4 "Done when", the second of its two
conjunctive conditions — the first, calibration, is evaluate/calibration.py's job.)

Both arms train on the IDENTICAL target — unconstrain_demand(clean_demand()), the
best available observable demand series (Phase 2's cleaning + Phase 3's censoring
correction) — so a single shared `test_df` per fold is already one fixed ruler for
both, exactly like point_floor.py. This is NOT unconstrain_floor.py's situation
(BLOCKER-1, P3_review.md): that gate compared two arms trained on TWO DIFFERENT
targets and needed a hand-built oracle-anchored actual so both were scored on one
fixed ruler. Here both arms share one target, so building that extra machinery
would be solving a problem this comparison doesn't have (Anti-Drift: build only
what this phase needs).

_NewsvendorAdapter wraps QuantileGBMModel + the newsvendor read-off behind the
BaseBaseline fit/predict contract — forecast == prep_qty (F^{-1} at the item's own
critical ratio), not a naive point prediction.

Fixed 2026-07-05 after `/review-phase P4` (docs/phase_decisions/P4_review.md):

- **MAJOR-1 (fold placement).** The original version called RollingOriginBacktest
  .run() directly, which anchors every fold's training window at the series START
  and expands forward. On this project's ~2.5-year simulated series that clusters
  all 4 test folds in spring 2022, never touching the go-forward/censored window
  at the very end (2024-04-05..06-30) where P3's unconstraining actually bites —
  the exact same root cause P3_review.md's BLOCKER-1 found one phase earlier (see
  docs/phase_decisions/P3.md, "fix RollingOriginBacktest fold placement for this
  gate only"). Fixed the same way: `backtest.min_train_weeks_reaching_tail` +
  `backtest.splits_with_full_tail_coverage` anchor the folds at the series end
  instead, via a manual per-fold fit/predict/score loop (mirroring
  unconstrain_floor.py's own loop) rather than RollingOriginBacktest.run(), which
  has no way to consume the wrapped splits. RollingOriginBacktest's own default
  behavior is untouched — point_floor.py/baseline_floor.py's already-logged
  numbers don't move.
- **MINOR-3 (prep_type routing).** The original version ran the dish-count
  newsvendor read-off against all 11 configured items, including the 4
  `made_to_order` ones (rule 04-deployment.md: made_to_order items must NEVER get
  a dish-count Q*, they route to ingredient par-level logic in Phase 7). Fixed:
  `decision.newsvendor.route_batch_items()` restricts both the adapter's item
  economics and the reported gate to the 7 `prep_type=batch` items. Both models
  still TRAIN on the full unrestricted demand series (more signal for the global
  LightGBM model, and made_to_order items' patterns don't hurt the fit); only the
  predicted/scored item set is batch-only.

Run:  python -m forecasting.src.evaluate.newsvendor_floor
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from forecasting.src.config import load_items
from forecasting.src.data.cleaner import clean_demand
from forecasting.src.decision.newsvendor import (
    critical_ratio,
    prep_quantity,
    required_quantile_levels,
    route_batch_items,
)
from forecasting.src.evaluate.backtest import (
    RollingOriginBacktest,
    leakage_canary,
    min_train_weeks_reaching_tail,
    splits_with_full_tail_coverage,
)
from forecasting.src.models.baselines import BaseBaseline, score_predictions
from forecasting.src.models.point import GlobalLGBMModel
from forecasting.src.models.quantile import QuantileGBMModel
from forecasting.src.models.unconstrain import unconstrain_demand

_POINT_MEAN_KEY = "lgbm_point_as_mean"
_NEWSVENDOR_KEY = "quantile_newsvendor"


class _NewsvendorAdapter(BaseBaseline):
    """QuantileGBMModel + newsvendor read-off, packaged as a BaseBaseline so the
    dollar gate can reuse RollingOriginBacktest's fit/predict contract unchanged
    (see module docstring). `items` should already be routed to batch-only (see
    decision.newsvendor.route_batch_items) — any item absent from `items` is
    silently skipped here, same contract as score_predictions()'s own
    missing-item handling.
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
) -> pd.DataFrame:
    """Run the point-as-mean baseline and the quantile+newsvendor policy through
    a shared, end-anchored rolling-origin backtest on
    unconstrain_demand(clean_demand()), reported over `prep_type=batch` items only.

    min_train_weeks is computed (not a parameter) so the folds land at the series
    END — see min_train_weeks_reaching_tail's docstring and this module's own
    "Fixed 2026-07-05" note above.

    Returns the same per-(fold, baseline, item) results frame as point_floor.py /
    baseline_floor.py, with baseline in {_POINT_MEAN_KEY, _NEWSVENDOR_KEY}.
    """
    items = load_items()
    batch_items = route_batch_items(items)
    if not batch_items:
        raise RuntimeError(
            "newsvendor_floor: route_batch_items(items) is empty — no prep_type=batch "
            "item in config/items.yaml for the dish-count newsvendor gate to score."
        )

    demand_df = unconstrain_demand(clean_demand()).drop(columns=["censored"]).copy()
    demand_df["business_date"] = pd.to_datetime(demand_df["business_date"]).dt.date
    quantile_levels = required_quantile_levels(batch_items)

    min_train_weeks = min_train_weeks_reaching_tail(
        demand_df["business_date"], n_folds=n_folds, test_weeks=test_weeks
    )
    bt = RollingOriginBacktest(n_folds=n_folds, test_weeks=test_weeks, min_train_weeks=min_train_weeks)
    all_dates = pd.DatetimeIndex(
        sorted(pd.Timestamp(d) for d in demand_df["business_date"].unique())
    )

    batch_item_ids = sorted(batch_items)
    svc_periods = sorted(demand_df["service_period"].unique())
    models = {
        _POINT_MEAN_KEY: GlobalLGBMModel(),
        _NEWSVENDOR_KEY: _NewsvendorAdapter(batch_items, quantile_levels),
    }

    result_rows = []
    for fold_idx, (train_dates, test_dates) in enumerate(splits_with_full_tail_coverage(bt, all_dates)):
        train_date_set = set(d.date() for d in train_dates)
        test_date_set = set(d.date() for d in test_dates)
        train_df = demand_df[demand_df["business_date"].isin(train_date_set)].copy()
        test_df = demand_df[demand_df["business_date"].isin(test_date_set)].copy()
        leakage_canary(train_df, test_df)

        train_end = max(train_date_set)
        test_start = min(test_date_set)
        test_end = max(test_date_set)

        for model_key, model in models.items():
            fitted = model.fit(train_df)
            preds = fitted.predict(sorted(test_date_set), batch_item_ids, svc_periods)
            scored = score_predictions(preds, test_df, batch_items)

            for item_id in batch_item_ids:
                sub = scored[scored["item_id"] == item_id]
                if sub.empty:
                    continue
                forecasts = sub["forecast"].values.astype(float)
                actuals = sub["actual"].values.astype(float)
                total_cost = float(np.nansum(sub["dollar_cost"].values))
                denom = float(np.sum(np.abs(actuals)))
                wape = (
                    float(np.sum(np.abs(forecasts - actuals))) / denom
                    if denom > 0 else float("nan")
                )
                bias = float(np.mean(forecasts - actuals))
                result_rows.append({
                    "fold": fold_idx,
                    "baseline": model_key,
                    "item_id": item_id,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "dollar_cost": total_cost,
                    "wape": wape,
                    "bias": bias,
                    "n_days": int(sub["business_date"].nunique()),
                })

    results = pd.DataFrame(result_rows)
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
    items = load_items()
    batch_items = route_batch_items(items)
    print(
        f"Scope: prep_type=batch items only ({len(batch_items)} of {len(items)} configured) "
        f"— rule 04-deployment.md's dish-count newsvendor never applies to made_to_order items.\n"
    )

    results = compute_newsvendor_floor()
    totals = results.groupby("baseline")["dollar_cost"].sum().sort_values()
    fold = results.groupby(["baseline", "fold"])["dollar_cost"].sum().unstack("fold")
    fold_dates = results.groupby("fold")[["test_start", "test_end"]].first()
    print(totals.round(2).to_string())
    print("\nBy fold:")
    print(fold.round(2).to_string())
    print("\nFold test windows (should reach the series' final date):")
    print(fold_dates.to_string())

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
