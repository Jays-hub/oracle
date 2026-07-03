"""Phase-3 dollar gate: does training the point model on UNCONSTRAINED demand beat
training it on Phase-2's clean (still-censored) demand, on the items that actually
sold out?

Both arms are trained on their OWN target (clean vs. unconstrained -- that's the
whole point of the comparison) but SCORED against ONE common actual: true demand
from the oracle on the go-forward window, `clean_demand()`'s own observed value
everywhere else. This module lives in `evaluate/` and is one of the sanctioned
oracle readers (data/CONTRACT.md), same footing as `unconstrain_check.py` and
`cleaning_check.py`.

Fixed 2026-07-02 after `/review-phase P3` (docs/phase_decisions/P3_review.md
BLOCKER-1): the first version of this gate scored the clean arm against
clean_demand()'s CAPPED actual and the unconstrained arm against its own CORRECTED
actual -- two different answer keys. On exactly the censored test days, the
unconstrained arm's bar was raised while the clean arm's stayed artificially low,
so the unconstrained arm mechanically accrued more "underage" for hitting the same
predictions, and the gate reported a false -$3,533.87 "regression." Scoring both
arms against one fixed ruler (this file, now) shows unconstraining actually WINS on
popular items -- see the module-level result printed by `main()` for the current
number. A dollar comparison is only meaningful if the actual is held fixed between
the two things being compared; changing the label mid-comparison measures the
label change, not the model -- the same principle `baseline_floor.py`'s own
docstring states for the mirror-image mistake ("computing the floor on truth
inflates the target and lets a mediocre model look like a winner").

Fold placement is NOT point_floor.py's default, for a different, orthogonal reason.
RollingOriginBacktest.splits() anchors every fold's training window at the FIRST
date in whatever demand_df it is given and expands forward -- with point_floor.py's
defaults (min_train_weeks=12, test_weeks=4, n_folds=4) on this project's ~2.5-year
simulated series, all 4 folds' test windows land in 2022-03-26..2022-07-15, nowhere
near the observable censored window at the very END of the series (config/sim.yaml
goforward_days, the last ~90 days). `_min_train_weeks_reaching_tail` computes
min_train_weeks dynamically so the test folds land at the end of history instead.

`_splits_with_full_tail_coverage` then closes a second, smaller gap
(P3_review.md MINOR-1): RollingOriginBacktest sizes every test window at exactly
test_weeks*7 days, so when the available history isn't an exact multiple of that,
the LAST fold's nominal end falls a few days short of the series' true final date
(on this data: test ends 2024-06-28, 2 days before the go-forward window's actual
end 2024-06-30, silently excluding 2 of 66 observable censored rows from every
fold). Fixed by extending ONLY the last fold's test window to the series' true max
date -- fold 0..n-2 and the last fold's own START are untouched, so this cannot
shift any training window or change what any other fold scores. (An earlier version
of this fix instead trimmed days off the START of the whole series so
min_train_weeks divided evenly -- rejected after it moved every fold's exact date
boundaries by 2 days and materially changed the dollar result along with the
coverage; a fix for a 2-day tail gap should not perturb the other three folds.)

"Popular" items, per construction_roadmap.md Phase 3's done-when clause, are
operationalized here as the items with at least one censored row in clean_demand()
-- the only items unconstraining can possibly move (a model trained on an
unchanged target scores identically against an unchanged actual). Items with zero
censored rows are still reported for transparency but excluded from the pass/fail
gate.

Run:  python -m forecasting.src.evaluate.unconstrain_floor
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

from forecasting.src.config import load_items
from forecasting.src.data.cleaner import clean_demand
from forecasting.src.evaluate.backtest import RollingOriginBacktest, leakage_canary
from forecasting.src.models.baselines import score_predictions
from forecasting.src.models.point import GlobalLGBMModel
from forecasting.src.models.unconstrain import unconstrain_demand

_CLEAN_KEY = "lgbm_point_clean"
_UNCONSTRAINED_KEY = "lgbm_point_unconstrained"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TRUTH_DIR = _REPO_ROOT / "data" / "_truth"


def _assert_truth_only(path: Path) -> None:
    if Path(path).name != "_truth":
        raise ValueError(
            f"unconstrain_floor reads the data/_truth/ store only; refused non-truth path: {path}"
        )


def _load_truth_demand(truth_dir: Path = _DEFAULT_TRUTH_DIR) -> pd.DataFrame:
    _assert_truth_only(truth_dir)
    df = pd.read_csv(Path(truth_dir) / "truth_demand.csv")
    df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    return df[["business_date", "item_id", "service_period", "true_demand"]]


def _censored_item_ids(clean: pd.DataFrame) -> set[str]:
    return set(clean.loc[clean["censored"], "item_id"].unique())


def _oracle_actual(clean: pd.DataFrame, truth_dir: Path = _DEFAULT_TRUTH_DIR) -> pd.DataFrame:
    """The single, fixed scoring ruler for BOTH gate arms: clean_demand()'s observed
    series, with observably-censored rows replaced by their real true_demand from
    the oracle. Uncensored rows are untouched (their observed value already IS true
    demand). This is the fix for P3_review.md BLOCKER-1 -- both arms are trained on
    different targets but must be SCORED against this one fixed actual, never their
    own respective training target.
    """
    truth = _load_truth_demand(truth_dir)
    merged = clean.merge(truth, on=["business_date", "item_id", "service_period"], how="left")
    missing = merged[merged["censored"] & merged["true_demand"].isna()]
    if not missing.empty:
        raise RuntimeError(
            f"unconstrain_floor: {len(missing)} censored row(s) have no matching truth_demand "
            f"entry -- date/item/period grid mismatch, e.g. "
            f"{missing.iloc[0][['business_date', 'item_id', 'service_period']].to_dict()}"
        )
    merged["demand"] = merged["demand"].where(~merged["censored"], merged["true_demand"])
    return merged[["business_date", "item_id", "service_period", "demand"]]


def _min_train_weeks_reaching_tail(
    dates: pd.Series, n_folds: int, test_weeks: int
) -> int:
    """Train on ~all history except a fixed-size test tail, so the test folds land
    at the end of the series (where the observable go-forward/censored window is)
    instead of RollingOriginBacktest's default fixed-at-the-start anchor."""
    ts = pd.to_datetime(dates)
    total_days = (ts.max() - ts.min()).days + 1
    test_span_days = n_folds * test_weeks * 7
    return max(1, (total_days - test_span_days) // 7)


def _splits_with_full_tail_coverage(
    bt: RollingOriginBacktest, all_dates: pd.DatetimeIndex
) -> Iterator[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
    """Wrap RollingOriginBacktest.splits() so the LAST fold's test window reaches
    the series' true final date (P3_review.md MINOR-1), without touching any other
    fold's boundaries or the last fold's own start -- see module docstring."""
    folds = list(bt.splits(all_dates))
    last_max = all_dates.max()
    for idx, (train_dates, test_dates) in enumerate(folds):
        if idx == len(folds) - 1 and test_dates.max() < last_max:
            extra = all_dates[(all_dates > test_dates.max()) & (all_dates <= last_max)]
            test_dates = test_dates.union(extra)
        yield train_dates, test_dates


def _fold_items_touching_censored_rows(
    clean: pd.DataFrame, bt: RollingOriginBacktest, all_dates: pd.DatetimeIndex
) -> set[tuple[int, str]]:
    """(fold, item_id) pairs whose TEST window contains at least one censored day --
    the only pairs the clean-vs-unconstrained comparison can possibly move, since
    every other pair's train data AND scored actual are identical between the two
    arms."""
    censored = clean.loc[clean["censored"], ["business_date", "item_id"]].copy()
    censored["business_date"] = pd.to_datetime(censored["business_date"])
    touching = set()
    for fold_idx, (_, test_dates) in enumerate(_splits_with_full_tail_coverage(bt, all_dates)):
        test_date_set = set(test_dates.date)
        for item_id in censored["item_id"].unique():
            item_dates = set(censored.loc[censored["item_id"] == item_id, "business_date"].dt.date)
            if item_dates & test_date_set:
                touching.add((fold_idx, item_id))
    return touching


def compute_unconstrain_floor(
    n_folds: int = 4,
    test_weeks: int = 4,
) -> tuple[pd.DataFrame, set[str], set[tuple[int, str]]]:
    """Fit the point model on clean vs. unconstrained targets, score both against
    the SAME oracle-anchored actual (see module docstring / _oracle_actual).

    Returns (results, popular_item_ids, touching_fold_items): results has columns
    [fold, baseline, item_id, train_end, test_start, test_end, dollar_cost, wape,
    bias, n_days] with baseline in {_CLEAN_KEY, _UNCONSTRAINED_KEY}; popular_item_ids
    is the set of items with at least one censored row; touching_fold_items is the
    (fold, item_id) subset whose test window actually contains a censored day.
    """
    items = load_items()
    clean = clean_demand()
    popular_item_ids = _censored_item_ids(clean)
    if not popular_item_ids:
        raise RuntimeError(
            "unconstrain_floor: clean_demand() has zero censored rows -- nothing for "
            "Phase 3 to unconstrain. Regenerate data/raw/ (the go-forward window should "
            "contain eightysix_log entries)."
        )

    unconstrained = unconstrain_demand(clean)
    oracle_actual = _oracle_actual(clean)
    min_train_weeks = _min_train_weeks_reaching_tail(
        clean["business_date"], n_folds=n_folds, test_weeks=test_weeks
    )

    bt = RollingOriginBacktest(
        n_folds=n_folds, test_weeks=test_weeks, min_train_weeks=min_train_weeks
    )
    all_dates = pd.DatetimeIndex(
        sorted(pd.Timestamp(d) for d in clean["business_date"].unique())
    )
    touching_fold_items = _fold_items_touching_censored_rows(clean, bt, all_dates)

    train_targets = {
        _CLEAN_KEY: clean.drop(columns=["censored"]).copy(),
        _UNCONSTRAINED_KEY: unconstrained.drop(columns=["censored"]).copy(),
    }
    for df in train_targets.values():
        df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    oracle_d = oracle_actual.copy()
    oracle_d["business_date"] = pd.to_datetime(oracle_d["business_date"]).dt.date

    item_ids = sorted(oracle_d["item_id"].unique())
    svc_periods = sorted(oracle_d["service_period"].unique())

    rows = []
    for fold_idx, (train_dates, test_dates) in enumerate(_splits_with_full_tail_coverage(bt, all_dates)):
        train_date_set = set(d.date() for d in train_dates)
        test_date_set = set(d.date() for d in test_dates)
        train_end = max(train_date_set)
        test_start = min(test_date_set)
        test_end = max(test_date_set)
        test_actual = oracle_d[oracle_d["business_date"].isin(test_date_set)]

        for baseline_key, target_df in train_targets.items():
            train_df = target_df[target_df["business_date"].isin(train_date_set)]
            leakage_canary(train_df, test_actual)

            model = GlobalLGBMModel().fit(train_df)
            preds = model.predict(sorted(test_date_set), item_ids, svc_periods)
            scored = score_predictions(preds, test_actual, items)

            for item_id in item_ids:
                if item_id not in items:
                    continue
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
                rows.append({
                    "fold": fold_idx,
                    "baseline": baseline_key,
                    "item_id": item_id,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "dollar_cost": total_cost,
                    "wape": wape,
                    "bias": bias,
                    "n_days": int(sub["business_date"].nunique()),
                })

    results = pd.DataFrame(rows)
    if results.empty:
        raise RuntimeError(
            "unconstrain_floor backtest produced no results -- dates/items may not align."
        )
    return results, popular_item_ids, touching_fold_items


def main() -> None:
    print("=" * 64)
    print("P3 DOLLAR GATE  (unconstrained-target vs. clean-target, scored on one common ruler)")
    print("=" * 64)
    results, popular_item_ids, touching_fold_items = compute_unconstrain_floor()

    totals = results.groupby("baseline")["dollar_cost"].sum().sort_values()
    print("All 11 items:")
    print(totals.round(2).to_string())

    popular = results[results["item_id"].isin(popular_item_ids)]
    popular_totals = popular.groupby("baseline")["dollar_cost"].sum().sort_values()
    print(
        f"\nPopular items only ({sorted(popular_item_ids)}, {len(popular_item_ids)} of 11 -- "
        f"the only items with censored rows):"
    )
    print(popular_totals.round(2).to_string())

    # Decompose: (fold, item) pairs whose test window actually contains a censored
    # day vs. the rest -- every OTHER pair's train data AND scored actual are
    # identical between the clean and unconstrained runs, so any cost delta there
    # is noise, not signal.
    is_touching = [
        (f, i) in touching_fold_items
        for f, i in zip(popular["fold"], popular["item_id"])
    ]
    touching_mask = pd.Series(is_touching, index=popular.index)
    for label, mask in [("touching a censored test day", touching_mask), ("no censored test day", ~touching_mask)]:
        sub_totals = popular[mask].groupby("baseline")["dollar_cost"].sum()
        if sub_totals.empty:
            continue
        print(
            f"\n  ({label}, {mask.sum()} rows) clean: {sub_totals.get(_CLEAN_KEY, 0.0):,.2f}  |  "
            f"unconstrained: {sub_totals.get(_UNCONSTRAINED_KEY, 0.0):,.2f}"
        )

    clean_total = float(popular_totals[_CLEAN_KEY])
    unconstrained_total = float(popular_totals[_UNCONSTRAINED_KEY])
    gap = clean_total - unconstrained_total
    print(
        f"\nPopular-item cost (scored on one common ruler) -- clean: {clean_total:,.2f}  |  "
        f"unconstrained: {unconstrained_total:,.2f}  |  improvement: {gap:,.2f}"
    )

    if unconstrained_total >= clean_total:
        raise SystemExit(
            f"P3 dollar gate FAILED: unconstrained-target model ({unconstrained_total:,.2f}) "
            f"does not beat the Phase-2 clean-target model ({clean_total:,.2f}) on popular items."
        )
    print("P3 dollar gate: PASS")


if __name__ == "__main__":
    main()
