"""Day-ahead diagnostic for the point model (P2_review.md MAJOR-3).

RollingOriginBacktest scores a whole multi-week test window in one predict() call, so
lag features deep in that window are mostly NaN (see forecasting/src/models/point.py
docstring) -- FeaturePipeline never sees the intervening test days' actuals. That
skew is symmetric across baselines and the GBM, so point_floor.py's dollar comparison
stays fair, but it understates what a properly-served day-ahead model looks like.

This script replays the REAL production regime instead: fit once on a training window,
then walk a short held-out window one day at a time, revealing each day's ACTUAL demand
(FeaturePipeline.extend_history) before the next day is scored. Never a predicted value
-- only already-elapsed actuals -- so this is not leakage and not recursive-forecast
error compounding, just "tomorrow's prep sheet" with the lookback a real kitchen has.

NOT a gate: point_floor.py remains the committed dollar-gate artifact. This is a
supplementary diagnostic reporting the lag fill-rate and dollar cost under the
realistic horizon, for comparison against the block-backtest numbers.

Run:  python -m forecasting.src.evaluate.day_ahead_eval
"""
from __future__ import annotations

import pandas as pd

from forecasting.src.config import load_items
from forecasting.src.data.cleaner import clean_demand
from forecasting.src.evaluate.objective import dollar_loss
from forecasting.src.models.point import GlobalLGBMModel

_LAG_COLS = ["lag_1", "lag_7", "rolling_mean_7"]


def _lag_fill_rate(model: GlobalLGBMModel, date, item_ids: list[str], svc_periods: list[str]) -> dict[str, float]:
    """Fraction of (item, service_period) rows with a non-null lag feature on `date`,
    at the pipeline's current (possibly extended) history state."""
    input_df = pd.DataFrame([
        {"business_date": date, "item_id": it, "service_period": sp, "demand": 0}
        for it in item_ids
        for sp in svc_periods
    ])
    featured = model._pipeline.transform(input_df)
    return {col: float(featured[col].notna().mean()) for col in _LAG_COLS}


def run_day_ahead(test_days: int = 14, min_train_weeks: int = 12) -> pd.DataFrame:
    """Fit on everything before the test window, then score test_days one at a time,
    revealing each day's actual demand before scoring the next.

    Returns [business_date, item_id, service_period, forecast, actual, dollar_cost,
    lag_1_fill, lag_7_fill, rolling_mean_7_fill].
    """
    items = load_items()
    demand_df = clean_demand().drop(columns=["censored"])
    demand_df["business_date"] = pd.to_datetime(demand_df["business_date"]).dt.date

    all_dates = sorted(demand_df["business_date"].unique())
    train_cutoff_idx = len(all_dates) - test_days
    if train_cutoff_idx < min_train_weeks * 7:
        raise ValueError(
            "Not enough history for the requested test_days/min_train_weeks: "
            f"{len(all_dates)} days available, need >= {min_train_weeks * 7 + test_days}."
        )
    train_dates = set(all_dates[:train_cutoff_idx])
    test_dates = all_dates[train_cutoff_idx:]

    train_df = demand_df[demand_df["business_date"].isin(train_dates)]
    model = GlobalLGBMModel().fit(train_df)

    item_ids = sorted(demand_df["item_id"].unique())
    svc_periods = sorted(demand_df["service_period"].unique())

    rows = []
    for d in test_dates:
        fill = _lag_fill_rate(model, d, item_ids, svc_periods)
        preds = model.predict([d], item_ids, svc_periods)
        actual_today = demand_df[demand_df["business_date"] == d]
        merged = preds.merge(
            actual_today, on=["business_date", "item_id", "service_period"], how="left"
        )
        for _, r in merged.iterrows():
            eco = items.get(r["item_id"])
            if eco is None:
                continue
            cost = dollar_loss(float(r["forecast"]), float(r["demand"]), eco.co, eco.cu)
            rows.append({
                "business_date": d,
                "item_id": r["item_id"],
                "service_period": r["service_period"],
                "forecast": float(r["forecast"]),
                "actual": float(r["demand"]),
                "dollar_cost": cost,
                "lag_1_fill": fill["lag_1"],
                "lag_7_fill": fill["lag_7"],
                "rolling_mean_7_fill": fill["rolling_mean_7"],
            })
        # Reveal today's actuals before scoring tomorrow -- the real day-ahead regime.
        model._pipeline.extend_history(
            actual_today[["business_date", "item_id", "service_period", "demand"]]
        )

    return pd.DataFrame(rows)


def main() -> None:
    print("=" * 64)
    print("DAY-AHEAD DIAGNOSTIC  (supplementary, non-gating — see point.py docstring)")
    print("=" * 64)
    results = run_day_ahead()
    total_cost = float(results["dollar_cost"].sum())
    avg_fill = results[["lag_1_fill", "lag_7_fill", "rolling_mean_7_fill"]].mean()
    print(f"Total dollar cost over {results['business_date'].nunique()} day-ahead days: "
          f"{total_cost:,.2f}")
    print("\nAverage lag fill rate (fraction non-null):")
    print(avg_fill.round(3).to_string())
    print(
        "\n(Contrast with the block backtest's ~4-25% fill rate reported in "
        "docs/phase_decisions/P2_review.md MAJOR-3.)"
    )


if __name__ == "__main__":
    main()
