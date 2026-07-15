"""Tests for the W7 price-history retention policy (src/pricing/retention.py)."""
from datetime import date

import pandas as pd

from schemas import PriceObservationRow
from src.pricing.retention import DEFAULT_RETENTION_DAYS, apply_retention_policy, prune_price_observations_atomic


def _row(ingredient_id, unit_price, observed_date, source="inv-1"):
    return PriceObservationRow(
        ingredient_id=ingredient_id, ingredient_name=ingredient_id, unit_price=unit_price,
        source_invoice=source, observed_date=observed_date,
    ).model_dump()


def test_empty_dataframe_is_returned_unchanged():
    df = pd.DataFrame(columns=["ingredient_id", "unit_price", "observed_date"])
    result = apply_retention_policy(df)
    assert result.empty


def test_rows_within_the_window_are_kept():
    df = pd.DataFrame([_row("beef", 4.5, "2026-06-01")])
    result = apply_retention_policy(df, as_of=date(2026, 6, 15), retention_days=400)
    assert len(result) == 1


def test_rows_older_than_the_window_are_dropped_unless_they_are_the_latest_for_their_ingredient():
    df = pd.DataFrame([_row("beef", 4.5, "2020-01-01")])  # far outside any 400-day window
    as_of = date(2026, 6, 15)
    result = apply_retention_policy(df, as_of=as_of, retention_days=400)
    # It's the ONLY observation for "beef" -- the latest-per-ingredient guard keeps it, even
    # though it's ancient, so the grid never silently loses its one price for this ingredient.
    assert len(result) == 1


def test_old_row_is_dropped_when_a_newer_observation_exists_for_the_same_ingredient():
    df = pd.DataFrame([
        _row("beef", 4.0, "2020-01-01"),  # ancient AND superseded -- must be pruned
        _row("beef", 4.5, "2026-06-01"),  # the latest -- must survive
    ])
    result = apply_retention_policy(df, as_of=date(2026, 6, 15), retention_days=400)
    assert len(result) == 1
    assert result["unit_price"].iloc[0] == 4.5


def test_default_retention_window_is_400_days():
    assert DEFAULT_RETENTION_DAYS == 400


def test_apply_retention_policy_never_mutates_the_input_dataframe():
    df = pd.DataFrame([_row("beef", 4.0, "2020-01-01"), _row("pork", 3.0, "2026-06-01")])
    before = df.copy(deep=True)
    apply_retention_policy(df, as_of=date(2026, 6, 15), retention_days=400)
    pd.testing.assert_frame_equal(df, before)


def test_prune_price_observations_atomic_is_a_noop_when_no_leg_exists_yet(tmp_path):
    before, after = prune_price_observations_atomic(tmp_path)
    assert (before, after) == (0, 0)


def test_prune_price_observations_atomic_rewrites_the_file_with_only_kept_rows(tmp_path):
    df = pd.DataFrame([
        _row("beef", 4.0, "2020-01-01"),
        _row("beef", 4.5, "2026-06-01"),
        _row("pork", 3.0, "2026-06-05"),
    ])
    dest = tmp_path / "price_observations.parquet"
    df.to_parquet(dest, index=False, engine="pyarrow")

    before, after = prune_price_observations_atomic(tmp_path, as_of=date(2026, 6, 15), retention_days=400)
    assert before == 3
    assert after == 2

    on_disk = pd.read_parquet(dest)
    assert len(on_disk) == 2
    assert set(on_disk["ingredient_id"]) == {"beef", "pork"}
    assert 4.0 not in on_disk["unit_price"].values  # the pruned ancient+superseded row is gone


def test_prune_price_observations_atomic_is_a_noop_when_everything_is_within_window(tmp_path):
    df = pd.DataFrame([_row("beef", 4.5, "2026-06-01")])
    dest = tmp_path / "price_observations.parquet"
    df.to_parquet(dest, index=False, engine="pyarrow")
    mtime_before = dest.stat().st_mtime

    before, after = prune_price_observations_atomic(tmp_path, as_of=date(2026, 6, 15), retention_days=400)
    assert before == after == 1
    # Nothing needed pruning -- the file is left untouched (not rewritten-with-same-content).
    assert dest.stat().st_mtime == mtime_before
