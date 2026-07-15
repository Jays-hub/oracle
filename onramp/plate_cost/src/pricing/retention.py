"""Retention policy for the accumulating price-history seam leg (W7) —
``docs/website_production_overview.md`` row 10: "``price_observations.parquet`` accumulates
forever, no retention policy."

``price_observations.parquet`` APPENDS forever (``data/CONTRACT.md`` — every confirmed invoice
adds rows, never replaces). **400 days** is the chosen window: enough for a full year-over-year
comparison (the kind of "beef is up 16% vs. last summer" claim a chef would actually ask about)
plus headroom, without keeping every invoice line item indefinitely. This leg is not yet
consumed by ``forecasting/`` (the "Co provenance" forward note in ``data/CONTRACT.md`` — that
reads the *derived* ``food_cost`` leg, not this one, and even that isn't wired in yet), so the
window is sized for the on-ramp's own trend detection (``src/pricing/trends.py``), not an
engine training-window requirement — revisit once the engine actually reads this leg.

Pure pandas (rule 05: no FastAPI import) — ``scripts/apply_retention.py`` is the only caller
that knows this is meant to run periodically rather than on every request.
"""
from __future__ import annotations

import fcntl
import os
from datetime import date
from pathlib import Path

import pandas as pd

from ..capture.seam_upload import _stage_parquet

DEFAULT_RETENTION_DAYS = 400


def apply_retention_policy(
    df: pd.DataFrame, as_of: date | None = None, retention_days: int = DEFAULT_RETENTION_DAYS,
) -> pd.DataFrame:
    """Rows within ``retention_days`` of ``as_of`` (default: today), **plus** the single most
    recent observation per ingredient regardless of age.

    That second clause is load-bearing, not a nicety: ``src/pricing/compute.py::latest_prices``
    and ``trends.py::latest_price_per_ingredient`` both need at least one price per ingredient
    to compute a current cost/margin. Without it, an ingredient whose price hasn't moved in
    over a year would age out entirely and silently vanish from the grid — a false "this dish
    is free" rather than an honest "stale price," which rule 06 (never false precision) forbids.
    Returns a copy; never mutates ``df`` or its ``observed_date`` dtype, so a caller that reads
    straight from Parquet can round-trip the result without a dtype surprise.
    """
    if df.empty:
        return df

    observed = pd.to_datetime(df["observed_date"])
    cutoff = pd.Timestamp(as_of or date.today()) - pd.Timedelta(days=retention_days)
    is_latest_per_ingredient = observed == observed.groupby(df["ingredient_id"]).transform("max")
    keep = (observed >= cutoff) | is_latest_per_ingredient
    return df.loc[keep].reset_index(drop=True)


def prune_price_observations_atomic(
    raw_dir: Path, as_of: date | None = None, retention_days: int = DEFAULT_RETENTION_DAYS,
) -> tuple[int, int]:
    """Reads ``price_observations.parquet``, applies the retention policy, and full-replace-
    writes the result back. Returns ``(rows_before, rows_after)`` — ``(0, 0)`` if the leg
    doesn't exist yet (nothing to prune, not an error).

    Reuses ``seam_upload._stage_parquet`` (stage-then-rename) and the same ``fcntl.flock``
    exclusive lock ``write_price_observations_atomic`` takes on this file, so a retention pass
    can never race a concurrent ``/invoice/confirm`` append into a lost update — both paths
    serialize on the same lock file (rule 07: atomic, never-corrupting seam writes).
    """
    dest = raw_dir / "price_observations.parquet"
    if not dest.exists():
        return (0, 0)

    lock_path = raw_dir / "price_observations.parquet.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            df = pd.read_parquet(dest)
            pruned = apply_retention_policy(df, as_of=as_of, retention_days=retention_days)
            if len(pruned) != len(df):
                tmp_path = _stage_parquet(pruned, dest)
                os.replace(tmp_path, dest)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
    return (len(df), len(pruned))
