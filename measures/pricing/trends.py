"""Price-trend detection over the accumulated price-history seam leg (W3, Phase 3's "second hook").

Pure pandas functions operating on the **on-disk seam shape** of ``price_observations.parquet``
(``ingredient_id, ingredient_name, unit_price, source_invoice, observed_date`` —
``schemas/seam.py::PriceObservationRow``), the same DataFrame ``store.read_price_observations()``
returns. No FastAPI import (rule 05): unit-testable with a bare DataFrame, independent of the web
layer and of ``src/pricing/compute.py``'s UUID-keyed CLI models (a different ID universe — the CLI
side was never wired to the seam's accumulating history).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

_TREND_COLUMNS = [
    "ingredient_id", "ingredient_name", "current_price", "prior_price", "pct_change", "direction",
    "current_observed_date", "prior_observed_date",
]


def latest_price_per_ingredient(df: pd.DataFrame) -> pd.DataFrame:
    """Most recent unit_price per ingredient_id.

    Tie-break mirrors ``src/pricing/compute.py::latest_prices``: on equal ``observed_date``, the
    last observation in input row order wins (a same-day re-entry supersedes an earlier one) —
    a defined, deterministic rule, not a silent first-wins.
    """
    columns = ["ingredient_id", "ingredient_name", "unit_price", "observed_date"]
    if df.empty:
        return df.reindex(columns=columns).iloc[0:0]

    ordered = df.reset_index(drop=True)
    ordered = ordered.assign(_order=ordered.index)
    ordered = ordered.sort_values(["ingredient_id", "observed_date", "_order"])
    latest = ordered.groupby("ingredient_id", as_index=False).last()
    return latest[columns]


def price_trend(df: pd.DataFrame, as_of: date | None = None, lookback_days: int = 7) -> pd.DataFrame:
    """Per-ingredient current price vs. the most recent price at least ``lookback_days`` earlier.

    ``as_of`` defaults to the latest observed_date in ``df`` (simulates "today" against whatever
    history has been captured). An ingredient with no observation old enough to serve as a "prior"
    is skipped, not defaulted to 0%/None — there isn't enough history yet to claim a trend, and a
    fabricated 0% would be a false-precision claim (rule 06).
    """
    if df.empty:
        return pd.DataFrame(columns=_TREND_COLUMNS)

    working = df.copy()
    working["observed_date"] = pd.to_datetime(working["observed_date"])
    cutoff = pd.Timestamp(as_of) if as_of is not None else working["observed_date"].max()

    rows: list[dict] = []
    for ingredient_id, group in working.groupby("ingredient_id"):
        as_of_group = group[group["observed_date"] <= cutoff]
        if as_of_group.empty:
            continue
        current = as_of_group.sort_values("observed_date").iloc[-1]

        prior_cutoff = current["observed_date"] - pd.Timedelta(days=lookback_days)
        prior_candidates = as_of_group[as_of_group["observed_date"] <= prior_cutoff]
        if prior_candidates.empty:
            continue  # not enough history yet to compute a trend for this ingredient
        prior = prior_candidates.sort_values("observed_date").iloc[-1]

        pct_change = (current["unit_price"] - prior["unit_price"]) / prior["unit_price"]
        rows.append({
            "ingredient_id": ingredient_id,
            "ingredient_name": current["ingredient_name"],
            "current_price": float(current["unit_price"]),
            "prior_price": float(prior["unit_price"]),
            "pct_change": float(pct_change),
            "direction": "up" if pct_change > 0 else ("down" if pct_change < 0 else "flat"),
            # Carried through so a caller can state the ACTUAL span between the two observations
            # (e.g. "this week" vs. "over the last 45 days") rather than assuming lookback_days —
            # prior_candidates only requires AT LEAST lookback_days earlier, so the true gap can be
            # arbitrarily larger (W3_review.md MINOR-2: a 45-day-old prior was mislabeled "this week").
            "current_observed_date": current["observed_date"],
            "prior_observed_date": prior["observed_date"],
        })
    return pd.DataFrame(rows, columns=_TREND_COLUMNS)


def significant_moves(trend_df: pd.DataFrame, threshold: float = 0.10) -> pd.DataFrame:
    """Trend rows whose |pct_change| meets or exceeds ``threshold`` (default 10%), ranked by
    magnitude descending — the "worth alerting on" filter Phase 3's alert logic needs."""
    if trend_df.empty:
        return trend_df
    moves = trend_df[trend_df["pct_change"].abs() >= threshold]
    return moves.reindex(moves["pct_change"].abs().sort_values(ascending=False).index).reset_index(drop=True)
