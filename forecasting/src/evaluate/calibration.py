"""Phase-4 calibration checkpoint — does the fitted quantile distribution actually
match reality? (construction_roadmap.md Phase 4 "Done when": "Quantiles are
calibrated against `_truth/`".) One of evaluate/'s sanctioned data/_truth/ readers
(data/CONTRACT.md), alongside cleaning_check.py / unconstrain_check.py /
unconstrain_floor.py.

Four complementary checks, all scored against data/_truth/truth_demand.csv:

1. empirical_coverage() — rule 03's primary check: "for a q-quantile forecast,
   ~q% of actuals should fall below." Reported per fitted quantile level, pooled
   across folds AND per-fold (coverage_by_fold).
2. pit_values() — the probability-integral-transform of each held-out actual
   through its own item-day's fitted quantile curve (decision.newsvendor's
   piecewise-linear CDF). A well-calibrated model's PIT values are ~ Uniform(0,1).
3. per_item_underage_at_critical_ratio() — rule 03's PER-ITEM check ("the
   empirical underage rate should approximate (1 - q*) per item"), finer-grained
   than (1)'s pooled-across-items numbers — a single badly-calibrated high-Cu
   item can otherwise hide inside the pool (P4_review.md MINOR-5).
4. conformal_coverage() — an independent MAPIE split-conformal (CQR) interval,
   giving a FINITE-SAMPLE coverage GUARANTEE that (1)/(2)/(3) alone can't.
   Practices (a): "model-agnostic calibration wrapper" (construction_roadmap.md
   Phase 4).

Fixed 2026-07-05 after `/review-phase P4` (docs/phase_decisions/P4_review.md):

- **MINOR-5 (single tail holdout, pooled-only coverage).** The original version
  fit ONE model on a single train/tail-test split and pooled empirical_coverage()
  across all items. Rule 03 asks for rolling-origin (>=4 folds) and a per-item
  breakdown. Fixed: compute_calibration() now refits QuantileGBMModel across the
  SAME end-anchored rolling-origin folds newsvendor_floor.py's dollar gate uses
  (backtest.min_train_weeks_reaching_tail / splits_with_full_tail_coverage — see
  that module's own "Fixed 2026-07-05" note), reporting both pooled and per-fold
  coverage, plus the new per-item breakdown. `_train_test_tail_split` (the old
  single-split helper) is removed — superseded, not left as dead code.
- **MINOR-2 (upper-tail under-coverage, the newsvendor's own read-off region).**
  Not a numerical bug to fix (the model is honestly, if mildly, under-dispersed —
  see models/quantile.py) — `main()` now explicitly prints a directional caveat
  whenever the top quantile levels are under-covered, since "90% sure" silently
  meaning "86% sure" in the direction that under-buffers prep is the credibility
  risk rule 03 cares about, not just whether the pooled deviation clears the gate
  tolerance. Reporting calibration under the day_ahead_eval.py realistic-horizon
  replay (the review's "consider") is NOT built here — see docs/phase_decisions/
  P4.md "Explicitly Deferred" for why.

Why conformal_coverage() fits its OWN pair of models rather than wrapping
models/quantile.py's already-fitted estimators: MAPIE's
ConformalizedQuantileRegressor(prefit=False) fits and manages its own models
end-to-end (fit -> conformalize -> predict_interval). Accepting prefit externally-
fit estimators (prefit=True) would require exposing QuantileGBMModel's internal
per-quantile LGBMRegressor objects across the module boundary and guaranteeing
their alpha values exactly match what a chosen confidence_level needs (0.1/0.5/0.9
for confidence_level=0.8) — a tighter coupling for no real benefit, since the
whole point of this check is an INDEPENDENT verification of calibration, not
reuse of the production model's own artifact. It runs once, on the LAST (most
recent, end-anchored) fold's train/test split, not on every fold — repeating a
from-scratch conformal fit 4x is real added cost for a checkpoint script that
this phase's "done when" doesn't require.

Run:  python -m forecasting.src.evaluate.calibration
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from mapie.regression import ConformalizedQuantileRegressor

from forecasting.src.config import load_items
from forecasting.src.data.cleaner import clean_demand
from forecasting.src.decision.newsvendor import critical_ratio, quantile_curve, required_quantile_levels
from forecasting.src.evaluate.backtest import (
    RollingOriginBacktest,
    min_train_weeks_reaching_tail,
    splits_with_full_tail_coverage,
)
from forecasting.src.features.pipeline import FeaturePipeline, _coerce_date
from forecasting.src.models.quantile import QuantileGBMModel
from forecasting.src.models.unconstrain import unconstrain_demand

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TRUTH_DIR = _REPO_ROOT / "data" / "_truth"
_CAT_COLS = ["item_id", "service_period", "day_of_week", "era_id"]

# Generous, documented tolerances for a checkpoint gate (not the dollar gate) —
# sample sizes here are ~11 items x 2 periods x a few weeks, not the whole series.
_COVERAGE_TOLERANCE = 0.15
_CONFORMAL_UNDERSHOOT_TOLERANCE = 0.10
# MINOR-2: a directional print-only caveat, not a gate tolerance — fires when a
# quantile level at or above this fires under-covered (empirical < nominal),
# exactly the direction that under-buffers the newsvendor's own prep read-off.
_UPPER_TAIL_LEVEL_THRESHOLD = 0.75


def _assert_truth_only(path: Path) -> None:
    if Path(path).name != "_truth":
        raise ValueError(
            f"calibration reads the data/_truth/ store only; refused non-truth path: {path}"
        )


def _load_truth_demand(truth_dir: Path = _DEFAULT_TRUTH_DIR) -> pd.DataFrame:
    _assert_truth_only(truth_dir)
    df = pd.read_csv(Path(truth_dir) / "truth_demand.csv")
    df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    return df[["business_date", "item_id", "service_period", "true_demand"]]


def empirical_coverage(quantile_forecasts: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    """Per quantile level: fraction of true_demand <= forecast, vs. the nominal
    level. Rule 03's core calibration check. Returns
    [quantile, nominal, empirical, n], one row per fitted level.
    """
    merged = quantile_forecasts.merge(
        truth, on=["business_date", "item_id", "service_period"], how="inner"
    )
    if merged.empty:
        raise RuntimeError("empirical_coverage: no overlapping rows between forecasts and truth")
    rows = []
    for q, grp in merged.groupby("quantile"):
        covered = (grp["true_demand"] <= grp["forecast"]).mean()
        rows.append({"quantile": q, "nominal": q, "empirical": float(covered), "n": len(grp)})
    return pd.DataFrame(rows).sort_values("quantile").reset_index(drop=True)


def pit_values(quantile_forecasts: pd.DataFrame, truth: pd.DataFrame) -> np.ndarray:
    """Probability-integral-transform of each held-out true_demand through its own
    item-day's fitted quantile curve (piecewise-linear CDF, decision.newsvendor
    .quantile_curve). A well-calibrated model produces PIT values ~ Uniform(0, 1).
    """
    merged = quantile_forecasts.merge(
        truth, on=["business_date", "item_id", "service_period"], how="inner"
    )
    pits = []
    for _, grp in merged.groupby(["business_date", "item_id", "service_period"]):
        xs, qs = quantile_curve(grp[["quantile", "forecast"]])
        actual = float(grp["true_demand"].iloc[0])
        actual_c = min(max(actual, xs[0]), xs[-1])
        pits.append(float(np.interp(actual_c, xs, qs)))
    return np.array(pits)


def per_item_underage_at_critical_ratio(
    quantile_forecasts: pd.DataFrame, truth: pd.DataFrame, items: dict
) -> pd.DataFrame:
    """Per item: empirical underage rate at the item's OWN critical ratio q*, vs.
    the nominal target (1 - q*) — rule 03-model-training.md's per-item calibration
    check ("the empirical underage rate should approximate (1 - q*) per item"),
    finer-grained than empirical_coverage()'s pooled-across-items numbers
    (P4_review.md MINOR-5: a single badly-calibrated high-Cu item can be masked by
    the pool). Requires `quantile_forecasts` to have been fit with a grid covering
    every item's own critical ratio (required_quantile_levels(items)) — a missing
    level is skipped, not interpolated, so this reads the model's ACTUAL fitted
    read-off, not an approximation of it.

    Returns [item_id, q_star, nominal_underage, empirical_underage, n], one row
    per item with at least one overlapping (forecast at q*, truth) row.
    """
    rows = []
    for item_id, eco in items.items():
        r = round(critical_ratio(eco.co, eco.cu), 6)
        sub_fc = quantile_forecasts[
            (quantile_forecasts["item_id"] == item_id)
            & np.isclose(quantile_forecasts["quantile"].astype(float), r)
        ]
        if sub_fc.empty:
            continue
        merged = sub_fc.merge(
            truth, on=["business_date", "item_id", "service_period"], how="inner"
        )
        if merged.empty:
            continue
        empirical_underage = float((merged["true_demand"] > merged["forecast"]).mean())
        rows.append({
            "item_id": item_id,
            "q_star": r,
            "nominal_underage": round(1.0 - r, 6),
            "empirical_underage": empirical_underage,
            "n": len(merged),
        })
    if not rows:
        raise RuntimeError(
            "per_item_underage_at_critical_ratio: no item had an overlapping "
            "forecast-at-its-own-q*/truth row — was quantile_forecasts fit with "
            "required_quantile_levels(items) so every item's q* is a fitted level?"
        )
    return pd.DataFrame(rows).sort_values("item_id").reset_index(drop=True)


def conformal_coverage(
    train_df: pd.DataFrame,
    test_dates: list,
    item_ids: list[str],
    service_periods: list[str],
    truth: pd.DataFrame,
    confidence_level: float = 0.8,
    conformalize_frac: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Independent MAPIE split-conformal (CQR) check: a finite-sample coverage
    GUARANTEE at confidence_level, cross-checking empirical_coverage()'s raw
    numbers with a from-scratch conformalized interval (see module docstring "Why
    conformal_coverage() fits its own pair of models").
    """
    pipeline = FeaturePipeline().fit(train_df)
    featured = pipeline.transform(train_df, check_leakage=False)
    feat_cols = pipeline.feature_columns()

    dates_sorted = sorted(featured["business_date"].unique())
    split_idx = int(len(dates_sorted) * (1 - conformalize_frac))
    if split_idx < 1 or split_idx >= len(dates_sorted):
        raise ValueError("conformal_coverage: not enough training history to split fit/conformalize")
    fit_dates = set(dates_sorted[:split_idx])
    conf_dates = set(dates_sorted[split_idx:])

    def _xy(mask_dates: set) -> tuple[pd.DataFrame, pd.Series]:
        sub = featured[featured["business_date"].isin(mask_dates)]
        X = sub[feat_cols].copy()
        for col in _CAT_COLS:
            X[col] = X[col].astype("category")
        return X, sub["demand"].astype(float)

    X_fit, y_fit = _xy(fit_dates)
    X_conf, y_conf = _xy(conf_dates)

    base_est = LGBMRegressor(
        objective="quantile",
        alpha=0.5,
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=5,
        random_state=random_state,
        verbosity=-1,
    )
    cqr = ConformalizedQuantileRegressor(estimator=base_est, confidence_level=confidence_level)
    cqr.fit(X_fit, y_fit)
    cqr.conformalize(X_conf, y_conf)

    rows = [
        {"business_date": d, "item_id": it, "service_period": sp}
        for d in test_dates
        for it in item_ids
        for sp in service_periods
    ]
    input_df = pd.DataFrame(rows)
    input_df["business_date"] = _coerce_date(input_df["business_date"])
    input_df["demand"] = 0
    test_featured = pipeline.transform(input_df, check_leakage=True)
    X_test = test_featured[feat_cols].copy()
    for col in _CAT_COLS:
        X_test[col] = X_test[col].astype("category")

    _, intervals = cqr.predict_interval(X_test)
    lower = np.maximum(intervals[:, 0, 0], 0.0)
    upper = np.maximum(intervals[:, 1, 0], 0.0)

    out = test_featured[["business_date", "item_id", "service_period"]].copy()
    out["lower"] = lower
    out["upper"] = upper
    merged = out.merge(truth, on=["business_date", "item_id", "service_period"], how="inner")
    if merged.empty:
        raise RuntimeError("conformal_coverage: no overlapping rows between predictions and truth")
    covered = (merged["true_demand"] >= merged["lower"]) & (merged["true_demand"] <= merged["upper"])
    return {
        "confidence_level": confidence_level,
        "empirical_coverage": float(covered.mean()),
        "n": int(len(merged)),
        "mean_interval_width": float((merged["upper"] - merged["lower"]).mean()),
    }


def compute_calibration(
    n_folds: int = 4,
    test_weeks: int = 4,
    quantile_levels: list[float] | None = None,
    truth_dir: Path = _DEFAULT_TRUTH_DIR,
) -> dict:
    """Refit QuantileGBMModel across `n_folds` end-anchored rolling-origin folds —
    the SAME fold placement newsvendor_floor.py's dollar gate uses
    (backtest.min_train_weeks_reaching_tail / splits_with_full_tail_coverage) —
    score empirical coverage/PIT both pooled and per-fold, add a per-item
    breakdown at each item's own critical ratio, and cross-check the LAST
    (most recent) fold with an independent MAPIE conformal fit. See module
    docstring "Fixed 2026-07-05" for why this replaced the old single-tail split.

    Returns {"coverage": DataFrame, "coverage_by_fold": DataFrame,
    "pit": np.ndarray, "per_item": DataFrame, "conformal": dict}.
    """
    items = load_items()
    levels = quantile_levels or required_quantile_levels(items)
    demand_df = unconstrain_demand(clean_demand()).drop(columns=["censored"]).copy()
    demand_df["business_date"] = pd.to_datetime(demand_df["business_date"]).dt.date
    truth = _load_truth_demand(truth_dir)

    item_ids = sorted(demand_df["item_id"].unique())
    service_periods = sorted(demand_df["service_period"].unique())

    min_train_weeks = min_train_weeks_reaching_tail(
        demand_df["business_date"], n_folds=n_folds, test_weeks=test_weeks
    )
    bt = RollingOriginBacktest(n_folds=n_folds, test_weeks=test_weeks, min_train_weeks=min_train_weeks)
    all_dates = pd.DatetimeIndex(
        sorted(pd.Timestamp(d) for d in demand_df["business_date"].unique())
    )

    fold_preds = []
    fold_coverage_rows = []
    last_train_df: pd.DataFrame | None = None
    last_test_dates: list | None = None
    for fold_idx, (train_dates, test_dates) in enumerate(splits_with_full_tail_coverage(bt, all_dates)):
        train_date_set = set(d.date() for d in train_dates)
        test_date_list = sorted(d.date() for d in test_dates)
        train_df = demand_df[demand_df["business_date"].isin(train_date_set)].copy()

        model = QuantileGBMModel(quantile_levels=levels).fit(train_df)
        preds = model.predict_quantiles(test_date_list, item_ids, service_periods)

        cov = empirical_coverage(preds, truth)
        cov["fold"] = fold_idx
        fold_coverage_rows.append(cov)
        fold_preds.append(preds)

        last_train_df, last_test_dates = train_df, test_date_list

    all_preds = pd.concat(fold_preds, ignore_index=True)
    coverage_by_fold = pd.concat(fold_coverage_rows, ignore_index=True)
    coverage = empirical_coverage(all_preds, truth)
    pit = pit_values(all_preds, truth)
    per_item = per_item_underage_at_critical_ratio(all_preds, truth, items)
    conformal = conformal_coverage(last_train_df, last_test_dates, item_ids, service_periods, truth)

    return {
        "coverage": coverage,
        "coverage_by_fold": coverage_by_fold,
        "pit": pit,
        "per_item": per_item,
        "conformal": conformal,
    }


def main() -> None:
    print("=" * 64)
    print("P4 CALIBRATION CHECKPOINT  (quantiles vs. data/_truth/truth_demand.csv)")
    print("=" * 64)
    result = compute_calibration()
    coverage = result["coverage"]
    coverage_by_fold = result["coverage_by_fold"]
    pit = result["pit"]
    per_item = result["per_item"]
    conformal = result["conformal"]

    n_folds = coverage_by_fold["fold"].nunique()
    print(f"\nEmpirical coverage per fitted quantile level, pooled across {n_folds} "
          f"end-anchored rolling-origin folds (should track 'nominal'):")
    print(coverage.round(3).to_string(index=False))

    deviation = (coverage["empirical"] - coverage["nominal"]).abs()
    max_dev = float(deviation.max())
    worst = coverage.loc[deviation.idxmax()]

    print("\nBy fold (rule 03: >=4 rolling-origin folds):")
    by_fold_wide = coverage_by_fold.pivot(index="quantile", columns="fold", values="empirical")
    print(by_fold_wide.round(3).to_string())

    print(f"\nPIT values: n={len(pit)}, mean={pit.mean():.3f} (target ~0.5), "
          f"std={pit.std():.3f} (target ~0.289 for Uniform(0,1))")

    print("\nPer-item underage rate at each item's OWN critical ratio q* "
          "(should track 'nominal_underage' = 1 - q*):")
    print(per_item.round(3).to_string(index=False))

    print(
        f"\nConformal (MAPIE CQR) check, last (most recent) fold: target confidence_level="
        f"{conformal['confidence_level']:.2f}, empirical_coverage="
        f"{conformal['empirical_coverage']:.3f}, n={conformal['n']}, "
        f"mean_interval_width={conformal['mean_interval_width']:.2f}"
    )

    # MINOR-2: a directional caveat, not a gate failure -- upper-tail
    # under-coverage means the newsvendor's own read-off region (q* up to 0.81 on
    # the real config) is where prep systematically under-buffers demand.
    upper = coverage[coverage["quantile"] >= _UPPER_TAIL_LEVEL_THRESHOLD]
    under_covered = upper[upper["empirical"] < upper["nominal"]]
    if not under_covered.empty:
        worst_upper = under_covered.loc[(under_covered["nominal"] - under_covered["empirical"]).idxmax()]
        print(
            f"\nCAVEAT (P4_review.md MINOR-2): upper quantile levels are under-covered "
            f"(worst: q={worst_upper['quantile']:.2f} nominal={worst_upper['nominal']:.2f} "
            f"empirical={worst_upper['empirical']:.3f}) -- the distribution is mildly "
            f"under-dispersed in exactly the direction the newsvendor read-off queries "
            f"(q* up to ~0.81 on real items), so prep systematically under-buffers the "
            f"true right tail slightly more than the nominal service level promises. "
            f"Within tolerance (not a gate failure) but worth watching once Phase 8 "
            f"monitoring lands."
        )

    failures = []
    if max_dev > _COVERAGE_TOLERANCE:
        failures.append(
            f"worst quantile-level deviation {max_dev:.3f} exceeds tolerance "
            f"{_COVERAGE_TOLERANCE} (quantile={worst['quantile']:.2f}, "
            f"nominal={worst['nominal']:.2f}, empirical={worst['empirical']:.2f})"
        )
    conformal_gap = conformal["confidence_level"] - conformal["empirical_coverage"]
    if conformal_gap > _CONFORMAL_UNDERSHOOT_TOLERANCE:
        failures.append(
            f"conformal coverage {conformal['empirical_coverage']:.3f} undershoots "
            f"target {conformal['confidence_level']:.2f} by more than "
            f"{_CONFORMAL_UNDERSHOOT_TOLERANCE}"
        )
    if failures:
        raise SystemExit("P4 calibration check FAILED: " + "; ".join(failures))
    print("\nP4 calibration check: PASS")


if __name__ == "__main__":
    main()
