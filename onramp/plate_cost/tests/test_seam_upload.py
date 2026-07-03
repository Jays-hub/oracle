"""Tests for the W1 capture-funnel pure compute (src/capture/seam_upload.py).

Covers: schema-valid parsing, ALL row errors accumulated (not fail-fast), missing-column and
empty-file guards, the cross-file dish-name check, and the atomic seam write (including that a
failed write leaves no partial/leftover file behind).
"""
import pandas as pd
import pytest

from schemas import BomRow, SalesExportRow
from src.capture import seam_upload

_VALID_SALES = (
    b"dish_name,count,period_start,period_end\n"
    b"Burger,120,2026-06-01,2026-06-07\n"
    b"Salad,40,2026-06-01,2026-06-07\n"
)
_VALID_BOM = (
    b"dish_name,ingredient_name,qty,recipe_unit,canonical_unit,yield_factor\n"
    b"Burger,beef patty,6,oz,oz,0.9\n"
    b"Burger,brioche bun,1,each,each,1.0\n"
    b"Salad,romaine,4,oz,oz,0.85\n"
)


# ── parse_sales_csv ──────────────────────────────────────────────────────────

def test_parse_sales_csv_valid_rows_match_schema():
    """Correctness: a clean upload parses to the exact expected SalesExportRow values."""
    result = seam_upload.parse_sales_csv(_VALID_SALES)
    assert result.ok
    assert result.errors == []
    assert len(result.rows) == 2
    assert result.rows[0] == SalesExportRow(
        dish_name="Burger", count=120, period_start="2026-06-01", period_end="2026-06-07",
    )


def test_parse_sales_csv_accumulates_every_row_error_not_just_the_first():
    """A chef sees everything wrong in one pass — validation must not stop at the first bad row."""
    raw = (
        b"dish_name,count,period_start,period_end\n"
        b"Burger,-5,2026-06-01,2026-06-07\n"        # count must be >= 0
        b"Salad,40,2026-06-10,2026-06-01\n"          # period_end before period_start
        b"Soup,30,2026-06-01,2026-06-07\n"           # valid — must still be included
    )
    result = seam_upload.parse_sales_csv(raw)
    assert not result.ok
    assert len(result.errors) == 2
    assert any("Burger" in e for e in result.errors)
    assert any("Salad" in e for e in result.errors)
    assert len(result.rows) == 1
    assert result.rows[0].dish_name == "Soup"


def test_parse_sales_csv_missing_column_fails_clean_not_a_crash():
    raw = b"dish_name,count\nBurger,10\n"
    result = seam_upload.parse_sales_csv(raw)
    assert not result.ok
    assert result.rows == []
    assert "period_start" in result.errors[0]
    assert "period_end" in result.errors[0]


def test_parse_sales_csv_empty_file():
    result = seam_upload.parse_sales_csv(b"")
    assert not result.ok
    assert "empty" in result.errors[0].lower()


def test_parse_sales_csv_header_only_has_no_data_rows():
    result = seam_upload.parse_sales_csv(b"dish_name,count,period_start,period_end\n")
    assert not result.ok
    assert "no data rows" in result.errors[0].lower()


def test_parse_sales_csv_non_utf8_fails_clean_not_a_crash():
    """Edge case: hostile/garbage input (rule 07) must not raise, only report."""
    result = seam_upload.parse_sales_csv(b"\xff\xfe\x00\x01not utf8")
    assert not result.ok
    assert "utf-8" in result.errors[0].lower()


def test_parse_sales_csv_tolerates_excel_bom():
    raw = "﻿dish_name,count,period_start,period_end\nBurger,10,2026-06-01,2026-06-07\n".encode("utf-8")
    result = seam_upload.parse_sales_csv(raw)
    assert result.ok
    assert result.rows[0].dish_name == "Burger"


# ── parse_bom_csv ────────────────────────────────────────────────────────────

def test_parse_bom_csv_valid_rows_derive_stable_ids_from_names():
    """dish_id/ingredient_id are derived via normalize_name, not supplied — and are stable/reused
    across rows sharing the same dish (both Burger rows must get the same dish_id)."""
    result = seam_upload.parse_bom_csv(_VALID_BOM)
    assert result.ok
    assert len(result.rows) == 3
    burger_rows = [r for r in result.rows if r.dish_name == "Burger"]
    assert len(burger_rows) == 2
    assert burger_rows[0].dish_id == burger_rows[1].dish_id == "burger"
    assert burger_rows[0].ingredient_id == "beef patty"


def test_parse_bom_csv_accumulates_every_row_error():
    raw = (
        b"dish_name,ingredient_name,qty,recipe_unit,canonical_unit,yield_factor\n"
        b"Burger,beef,-6,oz,oz,0.9\n"        # qty must be > 0
        b"Burger,bun,1,each,each,1.5\n"      # yield_factor must be <= 1.0
        b"Salad,romaine,4,oz,oz,0.85\n"      # valid
    )
    result = seam_upload.parse_bom_csv(raw)
    assert not result.ok
    assert len(result.errors) == 2
    assert len(result.rows) == 1


def test_parse_bom_csv_missing_column_fails_clean():
    raw = b"dish_name,ingredient_name,qty\nBurger,beef,6\n"
    result = seam_upload.parse_bom_csv(raw)
    assert not result.ok
    assert result.rows == []


# ── cross_reference_dishes ───────────────────────────────────────────────────

def test_cross_reference_dishes_flags_mismatches_both_directions():
    bom_rows = [BomRow(
        dish_id="a", dish_name="Burger", ingredient_id="i", ingredient_name="beef",
        qty=1.0, recipe_unit="oz", canonical_unit="oz", yield_factor=0.9,
    )]
    sales_rows = [SalesExportRow(
        dish_name="Salad", count=5, period_start="2026-06-01", period_end="2026-06-07",
    )]
    only_in_bom, only_in_sales = seam_upload.cross_reference_dishes(bom_rows, sales_rows)
    assert only_in_bom == ["Burger"]
    assert only_in_sales == ["Salad"]


def test_cross_reference_dishes_matches_despite_case_and_whitespace():
    bom_rows = [BomRow(
        dish_id="a", dish_name=" Burger", ingredient_id="i", ingredient_name="beef",
        qty=1.0, recipe_unit="oz", canonical_unit="oz", yield_factor=0.9,
    )]
    sales_rows = [SalesExportRow(
        dish_name="burger ", count=5, period_start="2026-06-01", period_end="2026-06-07",
    )]
    only_in_bom, only_in_sales = seam_upload.cross_reference_dishes(bom_rows, sales_rows)
    assert only_in_bom == []
    assert only_in_sales == []


# ── write_seam_atomic ────────────────────────────────────────────────────────

def test_write_seam_atomic_round_trip(tmp_path):
    bom_rows = seam_upload.parse_bom_csv(_VALID_BOM).rows
    sales_rows = seam_upload.parse_sales_csv(_VALID_SALES).rows

    seam_upload.write_seam_atomic(bom_rows, sales_rows, tmp_path)

    bom_df = pd.read_parquet(tmp_path / "bom.parquet")
    sales_df = pd.read_parquet(tmp_path / "sales_export.parquet")
    assert len(bom_df) == 3
    assert len(sales_df) == 2
    # Round-trip must still satisfy the seam schema (mirrors test_store.py's discipline).
    BomRow(**{k: bom_df[k].iloc[0] for k in BomRow.model_fields})
    SalesExportRow(**{k: sales_df[k].iloc[0] for k in SalesExportRow.model_fields})


def test_write_seam_atomic_is_repeatable(tmp_path):
    """Reproducibility: writing the same validated rows twice must not error or corrupt state."""
    bom_rows = seam_upload.parse_bom_csv(_VALID_BOM).rows
    sales_rows = seam_upload.parse_sales_csv(_VALID_SALES).rows

    seam_upload.write_seam_atomic(bom_rows, sales_rows, tmp_path)
    seam_upload.write_seam_atomic(bom_rows, sales_rows, tmp_path)

    bom_df = pd.read_parquet(tmp_path / "bom.parquet")
    assert len(bom_df) == 3
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_seam_atomic_rejects_empty_input(tmp_path):
    sales_rows = seam_upload.parse_sales_csv(_VALID_SALES).rows
    with pytest.raises(ValueError, match="no BOM rows"):
        seam_upload.write_seam_atomic([], sales_rows, tmp_path)


def test_write_seam_atomic_leaves_no_partial_file_on_failure(tmp_path, monkeypatch):
    """A failed write must not leave a truncated destination file, a stray temp file, OR a
    one-sided commit behind — both destinations must be untouched, not just the one that failed.

    This is the joint-atomicity guarantee: staging both legs before committing either means a
    failure while WRITING either file (this test fails the second one) can never result in a new
    bom.parquet paired with an old/missing sales_export.parquet (rule 07).
    """
    bom_rows = seam_upload.parse_bom_csv(_VALID_BOM).rows
    sales_rows = seam_upload.parse_sales_csv(_VALID_SALES).rows

    original_to_parquet = pd.DataFrame.to_parquet
    calls = {"n": 0}

    def flaky_to_parquet(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # let the BOM stage succeed, fail while staging the sales file
            raise OSError("simulated disk failure")
        return original_to_parquet(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", flaky_to_parquet)

    with pytest.raises(OSError, match="simulated disk failure"):
        seam_upload.write_seam_atomic(bom_rows, sales_rows, tmp_path)

    assert not (tmp_path / "bom.parquet").exists()
    assert not (tmp_path / "sales_export.parquet").exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_seam_atomic_leaves_old_pair_untouched_on_failure(tmp_path, monkeypatch):
    """Reproduces the exact scenario the review flagged: a seam pair already exists, a new
    upload's write fails partway through — the OLD pair must survive completely intact, never a
    new-bom/old-sales (or vice versa) mismatch.
    """
    old_bom_rows = seam_upload.parse_bom_csv(_VALID_BOM).rows
    old_sales_rows = seam_upload.parse_sales_csv(_VALID_SALES).rows
    seam_upload.write_seam_atomic(old_bom_rows, old_sales_rows, tmp_path)
    old_bom_df = pd.read_parquet(tmp_path / "bom.parquet")
    old_sales_df = pd.read_parquet(tmp_path / "sales_export.parquet")

    new_bom_rows = seam_upload.parse_bom_csv(
        b"dish_name,ingredient_name,qty,recipe_unit,canonical_unit,yield_factor\n"
        b"Soup,stock,10,oz,oz,1.0\n"
    ).rows
    new_sales_rows = seam_upload.parse_sales_csv(
        b"dish_name,count,period_start,period_end\nSoup,20,2026-06-01,2026-06-07\n"
    ).rows

    original_to_parquet = pd.DataFrame.to_parquet
    calls = {"n": 0}

    def flaky_to_parquet(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated disk failure")
        return original_to_parquet(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", flaky_to_parquet)

    with pytest.raises(OSError, match="simulated disk failure"):
        seam_upload.write_seam_atomic(new_bom_rows, new_sales_rows, tmp_path)

    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "bom.parquet"), old_bom_df)
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "sales_export.parquet"), old_sales_df)
    assert list(tmp_path.glob("*.tmp")) == []


def test_raw_dir_invariant():
    """Structural firewall: RAW_DIR always resolves under data/raw (mirrors src/store.py)."""
    assert seam_upload.RAW_DIR.parts[-2:] == ("data", "raw")
    assert seam_upload.RAW_DIR.is_dir()


def test_max_upload_bytes_stays_under_the_base64_inflated_form_field_cap():
    """Guards the fix for a review finding: /confirm round-trips the raw bytes through a base64
    form field, and Starlette's default per-field cap on a POSTed form is 1 MiB. If MAX_UPLOAD_BYTES
    is ever raised without checking this, a file that legitimately passes /upload could still
    dead-end at /confirm with an opaque framework error instead of the app's friendly one."""
    from math import ceil

    starlette_default_field_cap = 1024 * 1024
    encoded_size = ceil(seam_upload.MAX_UPLOAD_BYTES / 3) * 4
    assert encoded_size < starlette_default_field_cap
