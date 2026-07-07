"""Rolling-origin (walk-forward) cross-validation harness.

Enforces: test window is always strictly after train window.
Leakage_canary() is called inside run() automatically — a leak fails loudly.
"""
from __future__ import annotations

from typing import Iterator

import numpy as np
import pandas as pd

from forecasting.src.models.baselines import BaseBaseline, _to_date, score_predictions


def leakage_canary(feature_df: pd.DataFrame, target_df: pd.DataFrame) -> None:
    """Assert max(feature_date) < min(target_date). Hard fail on leakage.

    Called automatically inside RollingOriginBacktest.run(). Also importable
    as a standalone CI check (rule 02-feature-eng leakage canary).
    """
    feat_dates = _to_date(feature_df["business_date"])
    targ_dates = _to_date(target_df["business_date"])
    feat_max = feat_dates.max()
    targ_min = targ_dates.min()
    if feat_max >= targ_min:
        raise ValueError(
            f"Temporal leakage: max feature date ({feat_max}) >= "
            f"min target date ({targ_min}). Test data is visible to the model."
        )


class RollingOriginBacktest:
    """Walk-forward CV harness for time-series demand forecasting.

    Parameters
    ----------
    n_folds      : number of train/test folds (minimum 4 per rule 03)
    test_weeks   : width of each test window in calendar weeks
    min_train_weeks : minimum training history for the first fold
    """

    def __init__(
        self,
        n_folds: int = 4,
        test_weeks: int = 4,
        min_train_weeks: int = 12,
    ) -> None:
        if n_folds < 4:
            raise ValueError(f"n_folds must be >= 4 (rule 03); got {n_folds}")
        self.n_folds = n_folds
        self.test_weeks = test_weeks
        self.min_train_weeks = min_train_weeks

    def splits(
        self, dates: pd.DatetimeIndex | list
    ) -> Iterator[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
        """Yield (train_dates, test_dates) pairs. Test always strictly after train.

        Expanding window: each successive fold adds test_weeks to training.
        Raises ValueError immediately if any generated split would leak future data.
        """
        all_dates = pd.DatetimeIndex(sorted(set(dates)))
        total_days = (all_dates[-1] - all_dates[0]).days + 1
        test_days = self.test_weeks * 7
        needed = self.min_train_weeks * 7 + self.n_folds * test_days
        if total_days < needed:
            raise ValueError(
                f"Not enough data: need {needed} days, have {total_days}. "
                f"Reduce n_folds, test_weeks, or min_train_weeks."
            )

        start = all_dates[0]
        for fold in range(self.n_folds):
            train_end = start + pd.Timedelta(days=self.min_train_weeks * 7 + fold * test_days - 1)
            test_start = train_end + pd.Timedelta(days=1)
            test_end = test_start + pd.Timedelta(days=test_days - 1)

            train_mask = (all_dates >= start) & (all_dates <= train_end)
            test_mask = (all_dates >= test_start) & (all_dates <= test_end)
            train_dates = all_dates[train_mask]
            test_dates = all_dates[test_mask]

            if len(train_dates) == 0 or len(test_dates) == 0:
                continue

            # Hard leakage check at split construction time
            if test_dates.min() <= train_dates.max():
                raise ValueError(
                    f"Fold {fold}: test_start ({test_dates.min()}) <= "
                    f"train_end ({train_dates.max()}). Temporal leakage."
                )

            yield train_dates, test_dates

    def run(
        self,
        demand_df: pd.DataFrame,
        baselines: dict[str, BaseBaseline],
        items: dict,
    ) -> pd.DataFrame:
        """Fit and score each baseline on each fold.

        Parameters
        ----------
        demand_df  : [business_date, item_id, service_period, demand]
        baselines  : name → fitted-or-unfitted BaseBaseline instance
        items      : item_id → ItemEconomics (with .co and .cu attributes)

        Returns
        -------
        DataFrame with columns:
        [fold, baseline, item_id, service_period, train_end, test_start,
         test_end, dollar_cost, wape, bias, n_days]
        """
        df = demand_df.copy()
        df["business_date"] = _to_date(df["business_date"])
        all_dates = pd.DatetimeIndex(
            [pd.Timestamp(d) for d in sorted(df["business_date"].unique())]
        )
        item_ids = sorted(df["item_id"].unique())
        svc_periods = sorted(df["service_period"].unique())

        result_rows = []
        for fold_idx, (train_dates, test_dates) in enumerate(self.splits(all_dates)):
            train_date_set = set(d.date() for d in train_dates)
            test_date_set = set(d.date() for d in test_dates)

            train_df = df[df["business_date"].isin(train_date_set)].copy()
            test_df = df[df["business_date"].isin(test_date_set)].copy()

            # Leakage canary: feature dates (train) must all precede target dates (test)
            leakage_canary(train_df, test_df)

            train_end = max(train_date_set)
            test_start = min(test_date_set)
            test_end = max(test_date_set)

            for bl_name, baseline in baselines.items():
                fitted = baseline.fit(train_df)
                preds = fitted.predict(list(test_date_set), item_ids, svc_periods)
                scored = score_predictions(preds, test_df, items)

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

                    result_rows.append({
                        "fold": fold_idx,
                        "baseline": bl_name,
                        "item_id": item_id,
                        "train_end": train_end,
                        "test_start": test_start,
                        "test_end": test_end,
                        "dollar_cost": total_cost,
                        "wape": wape,
                        "bias": bias,
                        "n_days": int(sub["business_date"].nunique()),
                    })

        if not result_rows:
            raise RuntimeError(
                "Backtest produced no rows — demand_df dates may not align with the test "
                "windows, or no item_ids map to economics. (Empty results used to pass "
                "silently; see audit #8.)"
            )
        return pd.DataFrame(result_rows)


def min_train_weeks_reaching_tail(
    dates: pd.Series | pd.DatetimeIndex, n_folds: int, test_weeks: int
) -> int:
    """The min_train_weeks that anchors RollingOriginBacktest's test folds at the
    END of `dates` instead of its default fixed-at-the-start anchor.

    RollingOriginBacktest.splits() always starts every fold's training window at
    all_dates[0] and expands forward from there, so with small min_train_weeks the
    test folds land near the series START — fine for a stationary-enough series,
    but on this project's ~2.5-year simulated history it leaves the go-forward/
    censored window at the very END (where P3's unconstraining and P4's newsvendor
    read-off actually matter) never scored (P3_review.md BLOCKER-1's root cause;
    P4_review.md MAJOR-1's exact repeat one phase later). Pass this function's
    result as `min_train_weeks` when constructing RollingOriginBacktest, then wrap
    its .splits() output in splits_with_full_tail_coverage() below.

    RollingOriginBacktest.splits() itself is NOT changed by this — its own default
    behavior (used by baseline_floor.py/point_floor.py, whose already-logged
    numbers are cited in docs/progress_log.md and forecasting/CLAUDE.md) stays
    exactly as-is; this is an opt-in helper a gate script uses BEFORE constructing
    its own instance, not a new anchor mode on the class (see
    docs/phase_decisions/P3.md, "fix RollingOriginBacktest fold placement for this
    gate only, don't touch the shared harness" — same reasoning applies here).
    """
    ts = pd.to_datetime(pd.Series(list(dates)))
    total_days = (ts.max() - ts.min()).days + 1
    test_span_days = n_folds * test_weeks * 7
    return max(1, (total_days - test_span_days) // 7)


def splits_with_full_tail_coverage(
    bt: RollingOriginBacktest, all_dates: pd.DatetimeIndex
) -> Iterator[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
    """Wrap RollingOriginBacktest.splits() so the LAST fold's test window reaches
    `all_dates`'s true final date, without touching any other fold's boundaries or
    the last fold's own start.

    splits() sizes every test window at exactly test_weeks*7 days; when the
    available history isn't an exact multiple of that (true here, paired with
    min_train_weeks_reaching_tail() above), the last fold's nominal end falls a
    few days short of the series' true final date, silently excluding the most
    recent days from every fold (P3_review.md MINOR-1). Companion to
    min_train_weeks_reaching_tail(); use both together to anchor a gate at the end
    of a series without changing RollingOriginBacktest's own default splits().
    """
    folds = list(bt.splits(all_dates))
    last_max = all_dates.max()
    for idx, (train_dates, test_dates) in enumerate(folds):
        if idx == len(folds) - 1 and test_dates.max() < last_max:
            extra = all_dates[(all_dates > test_dates.max()) & (all_dates <= last_max)]
            test_dates = test_dates.union(extra)
        yield train_dates, test_dates
