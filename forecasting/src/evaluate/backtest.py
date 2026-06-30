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
