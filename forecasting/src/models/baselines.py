"""Honest baselines — the floor every model must beat in dollars.

All share one interface: fit(demand_df) → predict(dates, items, service_periods).
demand_df schema: [business_date (date/datetime), item_id (str),
                   service_period (str), demand (int)].
predict() returns [business_date, item_id, service_period, forecast (float)].

These baselines are deliberately POINT forecasts scored AS the prep quantity: the naive
operator preps roughly what they expect to sell. They are therefore biased to under-prep
whenever Cu > Co (true for every item here), which surfaces as a chronic negative bias —
that is honest, not a defect. The newsvendor correction (prep at F⁻¹(q*), q* = Cu/(Co+Cu))
is the engine's core move and is reserved for Phase 4; baking it into the baselines would
give away the moat and violate the Anti-Drift Standing Order. The point-to-point comparison
stays fair because the P2 point model is scored the same way, and an empirical-quantile-at-q*
floor is a Phase-4 baseline, not a P1 one. (audit #7)
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


def _to_date(col: pd.Series) -> pd.Series:
    """Coerce a date/datetime/string column to Python date objects.

    Strings are PARSED, not passed through: a string-dated demand_df would otherwise fail
    to align in the backtest merge and yield an EMPTY result with no error. Values that are
    genuinely unparseable raise loudly rather than silently becoming NaT. (audit #8)
    """
    if pd.api.types.is_datetime64_any_dtype(col):
        return col.dt.date
    parsed = pd.to_datetime(col, errors="coerce")
    unparseable = parsed.isna() & pd.notna(col)
    if unparseable.any():
        bad = list(pd.Series(col)[unparseable].unique()[:5])
        raise ValueError(f"_to_date: unparseable date values: {bad}")
    return parsed.dt.date


class BaseBaseline(ABC):
    """Common interface for all baselines."""

    @abstractmethod
    def fit(self, demand_df: pd.DataFrame) -> "BaseBaseline":
        """Store whatever training history is needed. Return self."""

    @abstractmethod
    def predict(
        self,
        dates: list,
        items: list[str],
        service_periods: list[str],
    ) -> pd.DataFrame:
        """Return forecast rows for all (date, item, service_period) combinations.
        Columns: [business_date, item_id, service_period, forecast].
        forecast is a float >= 0.
        """

    def _empty_result(
        self, dates: list, items: list[str], service_periods: list[str], fill: float = 0.0
    ) -> pd.DataFrame:
        rows = [
            {"business_date": d, "item_id": it, "service_period": sp, "forecast": fill}
            for d in dates
            for it in items
            for sp in service_periods
        ]
        return pd.DataFrame(rows)


class Lag7Baseline(BaseBaseline):
    """Same weekday last week (lag-7). The "same as last Thursday" gut check."""

    def fit(self, demand_df: pd.DataFrame) -> "Lag7Baseline":
        df = demand_df.copy()
        df["business_date"] = _to_date(df["business_date"])
        # Index: (date, item_id, service_period) → demand
        self._lookup: dict[tuple, int] = (
            df.set_index(["business_date", "item_id", "service_period"])["demand"]
            .to_dict()
        )
        # Fallback: per-item-period mean over training set
        self._means: dict[tuple, float] = (
            df.groupby(["item_id", "service_period"])["demand"].mean().to_dict()
        )
        return self

    def predict(self, dates, items, service_periods) -> pd.DataFrame:
        rows = []
        for d in dates:
            d_py = d.date() if hasattr(d, "date") else d
            lag = d_py - pd.Timedelta(days=7)
            if hasattr(lag, "date"):
                lag = lag.date()
            for it in items:
                for sp in service_periods:
                    val = self._lookup.get((lag, it, sp))
                    if val is None:
                        # Walk back to find most recent same weekday
                        for weeks_back in range(2, 8):
                            prev = d_py - pd.Timedelta(days=7 * weeks_back)
                            if hasattr(prev, "date"):
                                prev = prev.date()
                            val = self._lookup.get((prev, it, sp))
                            if val is not None:
                                break
                    if val is None:
                        val = self._means.get((it, sp), 0.0)
                    rows.append({
                        "business_date": d_py,
                        "item_id": it,
                        "service_period": sp,
                        "forecast": float(max(val, 0)),
                    })
        return pd.DataFrame(rows)


class RollingMean28Baseline(BaseBaseline):
    """Mean of the same weekday over the last 28 days (4 weeks of matching weekday)."""

    def fit(self, demand_df: pd.DataFrame) -> "RollingMean28Baseline":
        df = demand_df.copy()
        df["business_date"] = _to_date(df["business_date"])
        self._means: dict[tuple, float] = (
            df.groupby(["item_id", "service_period"])["demand"].mean().to_dict()
        )
        # Pre-index per (item, service_period) as a date-sorted Series so the 28-day window
        # is an O(log n) slice instead of a full-frame boolean scan per cell. (audit #10)
        self._series: dict[tuple, pd.Series] = {}
        for (it, sp), grp in df.groupby(["item_id", "service_period"]):
            s = grp.set_index(pd.DatetimeIndex(pd.to_datetime(grp["business_date"])))["demand"]
            self._series[(it, sp)] = s.sort_index()
        return self

    def _weekday_mean(self, d_py, item_id: str, service_period: str) -> float:
        fallback = float(self._means.get((item_id, service_period), 0.0))
        s = self._series.get((item_id, service_period))
        if s is None or len(s) == 0:
            return fallback
        ts = pd.Timestamp(d_py)
        # Same weekday within the prior 28 days (exclude the current day).
        window = s.loc[ts - pd.Timedelta(days=28): ts - pd.Timedelta(days=1)]
        if len(window):
            same_dow = window[window.index.weekday == ts.weekday()]
            if len(same_dow):
                return float(same_dow.mean())
        return fallback

    def predict(self, dates, items, service_periods) -> pd.DataFrame:
        rows = []
        for d in dates:
            d_py = d.date() if hasattr(d, "date") else d
            for it in items:
                for sp in service_periods:
                    forecast = max(self._weekday_mean(d_py, it, sp), 0.0)
                    rows.append({
                        "business_date": d_py,
                        "item_id": it,
                        "service_period": sp,
                        "forecast": forecast,
                    })
        return pd.DataFrame(rows)


class ChefGutBaseline(BaseBaseline):
    """28-day weekday rolling mean rounded to nearest 5 — the gut-feel proxy."""

    def fit(self, demand_df: pd.DataFrame) -> "ChefGutBaseline":
        self._inner = RollingMean28Baseline().fit(demand_df)
        return self

    def predict(self, dates, items, service_periods) -> pd.DataFrame:
        raw = self._inner.predict(dates, items, service_periods)
        raw["forecast"] = (raw["forecast"] / 5.0).round() * 5.0
        raw["forecast"] = raw["forecast"].clip(lower=0.0)
        return raw


class CrostonBaseline(BaseBaseline):
    """Croston's method for intermittent (zero-heavy) demand.

    Tracks average demand-per-occurrence and average inter-occurrence interval
    separately, smoothed with exponential smoothing (alpha=0.1).
    Forecast = smoothed_demand / smoothed_interval.
    Best suited for items with many zero periods (e.g. tuna_tartare).
    """

    def __init__(self, alpha: float = 0.10) -> None:
        self.alpha = alpha

    def fit(self, demand_df: pd.DataFrame) -> "CrostonBaseline":
        df = demand_df.copy()
        df["business_date"] = _to_date(df["business_date"])
        df = df.sort_values("business_date")

        self._state: dict[tuple, tuple[float, float]] = {}

        for (item_id, sp), grp in df.groupby(["item_id", "service_period"]):
            demands = grp["demand"].values
            pos_demands = demands[demands > 0]
            if len(pos_demands) == 0:
                self._state[(item_id, sp)] = (0.0, 1.0)
                continue

            # Initialise with first non-zero observation
            z = float(pos_demands[0])  # smoothed demand level
            p = 1.0                     # smoothed inter-occurrence interval
            intervals = np.diff(np.where(demands > 0)[0], prepend=0)
            intervals = intervals[intervals > 0]

            for i, d_val in enumerate(demands):
                if d_val > 0:
                    z = self.alpha * d_val + (1 - self.alpha) * z
                    interval = 1.0 if len(intervals) == 0 else float(
                        intervals[min(i, len(intervals) - 1)]
                    )
                    p = self.alpha * interval + (1 - self.alpha) * p

            self._state[(item_id, sp)] = (z, max(p, 1.0))

        return self

    def predict(self, dates, items, service_periods) -> pd.DataFrame:
        rows = []
        for d in dates:
            d_py = d.date() if hasattr(d, "date") else d
            for it in items:
                for sp in service_periods:
                    z, p = self._state.get((it, sp), (0.0, 1.0))
                    forecast = max(z / p, 0.0)
                    rows.append({
                        "business_date": d_py,
                        "item_id": it,
                        "service_period": sp,
                        "forecast": forecast,
                    })
        return pd.DataFrame(rows)


def score_predictions(
    preds: pd.DataFrame,
    test_demand_df: pd.DataFrame,
    items_economics: dict,
) -> pd.DataFrame:
    """Merge forecasts onto actuals and attach per-row realized dollar cost.

    The single merge/fill/cost path, shared by score_baseline() and the backtest harness so
    the logic exists exactly once and cannot drift. (audit #9) Returns [business_date,
    item_id, service_period, forecast, actual, dollar_cost]; a row whose item is absent from
    items_economics gets NaN cost. Missing forecasts fall back to the item's test mean.
    """
    from forecasting.src.evaluate.objective import dollar_loss

    test_df = test_demand_df.copy()
    test_df["business_date"] = _to_date(test_df["business_date"])
    preds = preds.copy()
    preds["business_date"] = _to_date(preds["business_date"])

    merged = test_df.merge(
        preds, on=["business_date", "item_id", "service_period"], how="left"
    )
    merged["forecast"] = merged["forecast"].fillna(
        merged.groupby("item_id")["demand"].transform("mean")
    )

    costs = np.full(len(merged), np.nan)
    item_col = merged["item_id"].values
    fc = merged["forecast"].values.astype(float)
    ac = merged["demand"].values.astype(float)
    for item_id, eco in items_economics.items():
        m = item_col == item_id
        if m.any():
            costs[m] = dollar_loss(fc[m], ac[m], eco.co, eco.cu)
    merged["dollar_cost"] = costs
    merged = merged.rename(columns={"demand": "actual"})
    return merged[
        ["business_date", "item_id", "service_period", "forecast", "actual", "dollar_cost"]
    ]


def score_baseline(
    baseline: BaseBaseline,
    test_demand_df: pd.DataFrame,
    items_economics: dict,
) -> pd.DataFrame:
    """Predict over the test window and score it. Thin wrapper over score_predictions()."""
    test_df = test_demand_df.copy()
    test_df["business_date"] = _to_date(test_df["business_date"])
    dates = sorted(test_df["business_date"].unique())
    items = sorted(test_df["item_id"].unique())
    sps = sorted(test_df["service_period"].unique())
    preds = baseline.predict(dates, items, sps)
    return score_predictions(preds, test_df, items_economics)
