"""Phase-4 calibration checkpoint — does the fitted quantile distribution actually
match reality? (construction_roadmap.md Phase 4 "Done when": "Quantiles are
calibrated against `_truth/`".) One of evaluate/'s sanctioned data/_truth/ readers
(data/CONTRACT.md), alongside cleaning_check.py / unconstrain_check.py /
unconstrain_floor.py.

Three complementary checks, all scored against data/_truth/truth_demand.csv:

1. empirical_coverage() — rule 03's primary check: "for a q-quantile forecast,
   ~q% of actuals should fall below." Reported per fitted quantile level.
2. pit_values() — the probability-integral-transform of each held-out actual
   through its own item-day's fitted quantile curve (decision.newsvendor's
   piecewise-linear CDF). A well-calibrated model's PIT values are ~ Uniform(0,1).
3. conformal_coverage() — an independent MAPIE split-conformal (CQR) interval,
   giving a FINITE-SAMPLE coverage GUARANTEE that (1)/(2) alone can't. Practices
   (a): "model-agnostic calibration wrapper" (construction_roadmap.md Phase 4).

Why conformal_coverage() fits its OWN pair of models rather than wrapping
models/quantile.py's already-fitted estimators: MAPIE's
ConformalizedQuantileRegressor(prefit=False) fits and manages its own models
end-to-end (fit -> conformalize -> predict_interval). Accepting prefit externally-
fit estimators (prefit=True) would require exposing QuantileGBMModel's internal
per-quantile LGBMRegressor objects across the module boundary and guaranteeing
their alpha values exactly match what a chosen confidence_level needs (0.1/0.5/0.9
for confidence_level=0.8) — a tighter coupling for no real benefit, since the
whole point of this check is an INDEPENDENT verification of calibration, not
reuse of the production model's own artifact.

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
from forecasting.src.decision.newsvendor import quantile_curve, required_quantile_levels
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


def _train_test_tail_split(demand_df: pd.DataFrame, test_weeks: int) -> tuple[pd.DataFrame, list]:
    """Simplest honest split for a CHECKPOINT (not the dollar gate, which uses the
    full 4-fold RollingOriginBacktest in newsvendor_floor.py): train on everything
    except the last `test_weeks` calendar weeks, test on that tail.
    """
    df = demand_df.copy()
    df["business_date"] = pd.to_datetime(df["business_date"])
    dates = sorted(df["business_date"].unique())
    test_days = test_weeks * 7
    if len(dates) <= test_days:
        raise ValueError(f"Not enough history ({len(dates)} days) for a {test_days}-day test tail")
    cutoff = dates[-test_days]
    train_df = df[df["business_date"] < cutoff].copy()
    train_df["business_date"] = train_df["business_date"].dt.date
    test_dates = sorted(d.date() for d in dates if d >= cutoff)
    return train_df, test_dates


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
    test_weeks: int = 4,
    quantile_levels: list[float] | None = None,
    truth_dir: Path = _DEFAULT_TRUTH_DIR,
) -> dict:
    """Fit QuantileGBMModel on everything but the last `test_weeks`, predict the
    held-out tail, and score both the raw quantile grid and an independent
    conformal check against data/_truth/truth_demand.csv.

    Returns {"coverage": DataFrame, "pit": np.ndarray, "conformal": dict}.
    """
    items = load_items()
    levels = quantile_levels or required_quantile_levels(items)
    demand_df = unconstrain_demand(clean_demand()).drop(columns=["censored"])
    train_df, test_dates = _train_test_tail_split(demand_df, test_weeks)

    item_ids = sorted(demand_df["item_id"].unique())
    service_periods = sorted(demand_df["service_period"].unique())

    model = QuantileGBMModel(quantile_levels=levels).fit(train_df)
    preds = model.predict_quantiles(test_dates, item_ids, service_periods)

    truth = _load_truth_demand(truth_dir)
    coverage = empirical_coverage(preds, truth)
    pit = pit_values(preds, truth)
    conformal = conformal_coverage(train_df, test_dates, item_ids, service_periods, truth)

    return {"coverage": coverage, "pit": pit, "conformal": conformal}


def main() -> None:
    print("=" * 64)
    print("P4 CALIBRATION CHECKPOINT  (quantiles vs. data/_truth/truth_demand.csv)")
    print("=" * 64)
    result = compute_calibration()
    coverage = result["coverage"]
    pit = result["pit"]
    conformal = result["conformal"]

    print("\nEmpirical coverage per fitted quantile level (should track 'nominal'):")
    print(coverage.round(3).to_string(index=False))

    deviation = (coverage["empirical"] - coverage["nominal"]).abs()
    max_dev = float(deviation.max())
    worst = coverage.loc[deviation.idxmax()]

    print(f"\nPIT values: n={len(pit)}, mean={pit.mean():.3f} (target ~0.5), "
          f"std={pit.std():.3f} (target ~0.289 for Uniform(0,1))")

    print(
        f"\nConformal (MAPIE CQR) check: target confidence_level="
        f"{conformal['confidence_level']:.2f}, empirical_coverage="
        f"{conformal['empirical_coverage']:.3f}, n={conformal['n']}, "
        f"mean_interval_width={conformal['mean_interval_width']:.2f}"
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
