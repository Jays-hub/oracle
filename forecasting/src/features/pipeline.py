"""Phase-2 feature pipeline — calendar, era, lags, rolling stats.

FeaturePipeline.fit(demand_df) stores per-(item, service_period) training history
so that .transform(df) can compute all lag/rolling features without touching
future demand. All rolling windows use .shift(1) before .rolling(), so the
current row's demand is never its own feature (the most common time-series
leakage pattern). Rule 02-feature-eng.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SIM_CFG = _REPO_ROOT / "config" / "sim.yaml"

# The complete feature column list consumed by the point model (and later phases).
# business_date is excluded — it feeds calendar features but is not a raw model input.
FEATURE_COLS: list[str] = [
    "item_id",          # categorical: which dish
    "service_period",   # categorical: lunch vs. dinner
    "day_of_week",      # 0 (Mon) – 6 (Sun); strong demand driver
    "is_weekend",       # 0/1; coarser weekend signal for interactions
    "week_of_year",     # 1–53; captures seasonal arc within the year
    "month",            # 1–12; slower seasonal drift
    "era_id",           # categorical: menu era (structural break in demand level)
    "era_days_elapsed", # continuous: recency within the current era
    "lag_1",            # demand yesterday (same item + period)
    "lag_7",            # demand same weekday last week
    "lag_14",           # demand same weekday two weeks ago
    "rolling_mean_7",   # mean of [d-7 … d-1] (shift(1) already applied)
    "rolling_std_7",    # std of [d-7 … d-1]; NaN when < 2 observations
    "rolling_mean_28",  # mean of [d-28 … d-1]
]


def _load_era_boundaries(cfg_path: Path | None = None) -> list[tuple[date, int]]:
    """Parse menu_eras from sim.yaml → sorted (start_date, era_id) list."""
    path = cfg_path or _DEFAULT_SIM_CFG
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    return sorted(
        [(date.fromisoformat(e["start"]), int(e["id"])) for e in cfg["menu_eras"]],
        key=lambda t: t[0],
    )


def _era_for_date(d: date, boundaries: list[tuple[date, int]]) -> tuple[int, int]:
    """Return (era_id, era_days_elapsed) for date d.

    Iterates sorted boundaries; the last one whose start_date <= d wins.
    era_days_elapsed is clamped to 0 so dates before the first boundary don't
    produce a negative elapsed count.
    """
    era_id, era_start = boundaries[0][1], boundaries[0][0]
    for start, eid in boundaries:
        if d >= start:
            era_id, era_start = eid, start
        else:
            break
    return era_id, max(0, (d - era_start).days)


def _coerce_date(col: pd.Series) -> pd.Series:
    """Coerce date/datetime/string column to Python date objects."""
    if pd.api.types.is_datetime64_any_dtype(col):
        return col.dt.date
    return pd.to_datetime(col).dt.date


class FeaturePipeline:
    """Stateful feature pipeline: fit on training data, transform any window.

    fit(demand_df):
      - Stores per-(item_id, service_period) daily demand history as the
        look-back source for all lag and rolling computations.
      - Stores train_max_date for the optional leakage check.
      - Loads era boundaries (injectable for tests, otherwise read from sim.yaml).

    transform(df, check_leakage=True):
      - Adds feature columns to a copy of df.
      - Does NOT read the 'demand' column for features — only date and id columns
        are used, so transform is safe to call on test data without a demand column.
      - check_leakage=True (the default): hard-fails if any transform date <=
        train_max_date. Opt out with check_leakage=False ONLY for the one legitimate
        exception -- transforming the same rows just passed to fit(), to build
        training features (see GlobalLGBMModel.fit() in models/point.py).

    The authoritative leakage canary (max feature_date < min target_date) runs
    automatically inside RollingOriginBacktest.run() (backtest.py). The pipeline's
    own check is a second line of defense for direct callers, and now runs by
    default rather than opt-in (efficiency_backlog.md #6) -- a caller has to
    deliberately pass check_leakage=False to silence it, not the other way around.
    """

    def __init__(
        self,
        era_boundaries: list[tuple[date, int]] | None = None,
        sim_cfg_path: Path | None = None,
    ) -> None:
        self._era_boundaries: list[tuple[date, int]] = (
            era_boundaries if era_boundaries is not None
            else _load_era_boundaries(sim_cfg_path)
        )
        self._history: dict[tuple[str, str], pd.Series] = {}
        self._train_max_date: date | None = None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def fit(self, demand_df: pd.DataFrame) -> "FeaturePipeline":
        """Store per-(item, service_period) daily demand history from training data.

        Parameters
        ----------
        demand_df : columns [business_date, item_id, service_period, demand (int)]
        """
        df = demand_df.copy()
        df["business_date"] = _coerce_date(df["business_date"])
        self._train_max_date = df["business_date"].max()

        self._history = {}
        for (item_id, sp), grp in df.groupby(["item_id", "service_period"]):
            s = grp.set_index("business_date")["demand"].astype(float)
            s.index = pd.DatetimeIndex(pd.to_datetime(s.index))
            self._history[(item_id, sp)] = s.sort_index()

        n_items = df["item_id"].nunique()
        n_days = df["business_date"].nunique()
        print(
            f"[features] fit: {n_items} items, {n_days} training days "
            f"(max: {self._train_max_date})"
        )
        return self

    def transform(
        self, df: pd.DataFrame, check_leakage: bool = True
    ) -> pd.DataFrame:
        """Add feature columns to df without using current-row demand.

        Parameters
        ----------
        df             : must contain [business_date, item_id, service_period];
                         'demand' is kept if present but never used to build features.
        check_leakage  : hard-fail if any transform date <= train_max_date. Defaults
                         to True (rule 02: the leakage canary runs on the production
                         path, not opt-in). Pass False ONLY for the training
                         self-transform (see class docstring).
        """
        if self._train_max_date is None:
            raise RuntimeError("FeaturePipeline.fit() must be called before transform()")

        out = df.copy()
        out["business_date"] = _coerce_date(out["business_date"])

        if check_leakage:
            test_min = out["business_date"].min()
            if pd.Timestamp(self._train_max_date) >= pd.Timestamp(test_min):
                raise ValueError(
                    f"Pipeline leakage: train_max_date ({self._train_max_date}) >= "
                    f"min transform date ({test_min}). Test window overlaps training."
                )

        out = self._add_calendar_features(out)
        out = self._add_era_features(out)
        out = self._add_lag_features(out)
        return out

    def feature_columns(self) -> list[str]:
        """The feature column names the model should consume."""
        return list(FEATURE_COLS)

    # ------------------------------------------------------------------ #
    #  Private feature builders                                            #
    # ------------------------------------------------------------------ #

    def _add_calendar_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df["day_of_week"] = df["business_date"].apply(lambda d: d.weekday())
        df["is_weekend"] = df["day_of_week"].apply(lambda dow: 1 if dow >= 5 else 0)
        df["week_of_year"] = df["business_date"].apply(
            lambda d: d.isocalendar()[1]
        )
        df["month"] = df["business_date"].apply(lambda d: d.month)
        return df

    def _add_era_features(self, df: pd.DataFrame) -> pd.DataFrame:
        era_ids, elapsed = [], []
        for d in df["business_date"]:
            eid, el = _era_for_date(d, self._era_boundaries)
            era_ids.append(eid)
            elapsed.append(el)
        df["era_id"] = era_ids
        df["era_days_elapsed"] = elapsed
        return df

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute lag_1/7/14 and rolling stats per (item, service_period).

        For each group:
          1. Build a daily-frequency series spanning history + transform dates.
             Transform rows are NaN in this series so they can't pollute look-backs.
          2. Reindex to a dense daily grid so positional .shift() == calendar .shift().
          3. .shift(1) gives demand at d-1; .rolling(7).mean() over shifted series
             gives the mean of [d-7 … d-1] — no current-day leakage.
        """
        result_parts = []
        for (item_id, sp), grp in df.groupby(
            ["item_id", "service_period"], sort=False
        ):
            grp = grp.sort_values("business_date").copy()
            history = self._history.get((item_id, sp), pd.Series(dtype=float))
            transform_dates = pd.DatetimeIndex(pd.to_datetime(grp["business_date"]))

            if len(history) > 0:
                full_idx = history.index.union(transform_dates)
            else:
                full_idx = transform_dates

            # history has real values; transform rows reindex to NaN
            full_series = history.reindex(full_idx)

            # Dense daily grid: positional shift == 1-calendar-day shift
            daily_idx = pd.date_range(full_idx.min(), full_idx.max(), freq="D")
            dense = full_series.reindex(daily_idx)

            # shift(1)-before-rolling discipline: at day d, shifted1 holds demand at d-1
            shifted1 = dense.shift(1)
            lag7 = dense.shift(7)
            lag14 = dense.shift(14)

            # Rolling over shifted1 covers [d-7 … d-1] (7 prior days)
            roll_m7 = shifted1.rolling(7, min_periods=1).mean()
            roll_s7 = shifted1.rolling(7, min_periods=2).std()
            roll_m28 = shifted1.rolling(28, min_periods=1).mean()

            grp["lag_1"] = shifted1.reindex(transform_dates).values
            grp["lag_7"] = lag7.reindex(transform_dates).values
            grp["lag_14"] = lag14.reindex(transform_dates).values
            grp["rolling_mean_7"] = roll_m7.reindex(transform_dates).values
            grp["rolling_std_7"] = roll_s7.reindex(transform_dates).values
            grp["rolling_mean_28"] = roll_m28.reindex(transform_dates).values
            result_parts.append(grp)

        if not result_parts:
            for col in ["lag_1", "lag_7", "lag_14",
                        "rolling_mean_7", "rolling_std_7", "rolling_mean_28"]:
                df[col] = np.nan
            return df

        return (
            pd.concat(result_parts)
            .sort_values(["business_date", "item_id", "service_period"])
            .reset_index(drop=True)
        )
