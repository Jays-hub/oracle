"""Tests for the W3 invoice-capture pure compute (src/capture/invoice_upload.py).

Covers: schema-valid parsing, all row errors accumulated (not fail-fast), missing-column and
empty-file guards, the BOM cross-reference warning, and the atomic + idempotent price-history
append (distinct from seam_upload's full-replace semantics — this leg accumulates).
"""
import pandas as pd
import pytest

from schemas import PriceObservationRow
from src.capture import invoice_upload

_VALID_INVOICE = (
    b"ingredient_name,unit_price,source_invoice,observed_date\n"
    b"beef patty,3.50,INV-001,2026-06-01\n"
    b"romaine,1.20,INV-001,2026-06-01\n"
)


# -- parse_invoice_csv --------------------------------------------------------

def test_parse_invoice_csv_valid_rows_match_schema():
    """Correctness: a clean upload parses to the exact expected PriceObservationRow values."""
    result = invoice_upload.parse_invoice_csv(_VALID_INVOICE)
    assert result.ok
    assert result.errors == []
    assert len(result.rows) == 2
    assert result.rows[0] == PriceObservationRow(
        ingredient_id="beef patty", ingredient_name="beef patty",
        unit_price=3.50, source_invoice="INV-001", observed_date="2026-06-01",
    )


def test_parse_invoice_csv_derives_stable_id_from_name():
    result = invoice_upload.parse_invoice_csv(_VALID_INVOICE)
    assert result.rows[0].ingredient_id == "beef patty"


def test_parse_invoice_csv_blank_source_invoice_becomes_none():
    raw = b"ingredient_name,unit_price,source_invoice,observed_date\nbeef,3.50,,2026-06-01\n"
    result = invoice_upload.parse_invoice_csv(raw)
    assert result.ok
    assert result.rows[0].source_invoice is None


def test_parse_invoice_csv_accumulates_every_row_error_not_just_the_first():
    raw = (
        b"ingredient_name,unit_price,source_invoice,observed_date\n"
        b"beef,-3.50,INV-001,2026-06-01\n"     # unit_price must be > 0
        b"romaine,1.20,INV-001,2026-06-01\n"   # valid — must still be included
        b"stock,0,INV-001,2026-06-01\n"        # unit_price must be > 0
    )
    result = invoice_upload.parse_invoice_csv(raw)
    assert not result.ok
    assert len(result.errors) == 2
    assert any("beef" in e for e in result.errors)
    assert any("stock" in e for e in result.errors)
    assert len(result.rows) == 1
    assert result.rows[0].ingredient_name == "romaine"


def test_parse_invoice_csv_missing_column_fails_clean_not_a_crash():
    raw = b"ingredient_name,unit_price\nbeef,3.50\n"
    result = invoice_upload.parse_invoice_csv(raw)
    assert not result.ok
    assert result.rows == []
    assert "source_invoice" in result.errors[0]
    assert "observed_date" in result.errors[0]


def test_parse_invoice_csv_empty_file():
    result = invoice_upload.parse_invoice_csv(b"")
    assert not result.ok
    assert "empty" in result.errors[0].lower()


def test_parse_invoice_csv_header_only_has_no_data_rows():
    result = invoice_upload.parse_invoice_csv(
        b"ingredient_name,unit_price,source_invoice,observed_date\n"
    )
    assert not result.ok
    assert "no data rows" in result.errors[0].lower()


def test_parse_invoice_csv_non_utf8_fails_clean_not_a_crash():
    """Edge case: hostile/garbage input (rule 07) must not raise, only report."""
    result = invoice_upload.parse_invoice_csv(b"\xff\xfe\x00\x01not utf8")
    assert not result.ok
    assert "utf-8" in result.errors[0].lower()


# -- cross_reference_ingredients ----------------------------------------------

def test_cross_reference_ingredients_flags_unmatched_names():
    rows = invoice_upload.parse_invoice_csv(_VALID_INVOICE).rows
    unmatched = invoice_upload.cross_reference_ingredients(rows, known_ingredient_ids={"romaine"})
    assert unmatched == ["beef patty"]


def test_cross_reference_ingredients_matches_all_when_bom_covers_every_ingredient():
    rows = invoice_upload.parse_invoice_csv(_VALID_INVOICE).rows
    unmatched = invoice_upload.cross_reference_ingredients(
        rows, known_ingredient_ids={"beef patty", "romaine"},
    )
    assert unmatched == []


def test_cross_reference_ingredients_empty_bom_flags_everything():
    """No BOM captured yet is not an error state — every ingredient is honestly "unmatched"."""
    rows = invoice_upload.parse_invoice_csv(_VALID_INVOICE).rows
    unmatched = invoice_upload.cross_reference_ingredients(rows, known_ingredient_ids=set())
    assert set(unmatched) == {"beef patty", "romaine"}


# -- write_price_observations_atomic ------------------------------------------

def test_write_price_observations_atomic_round_trip(tmp_path):
    rows = invoice_upload.parse_invoice_csv(_VALID_INVOICE).rows
    invoice_upload.write_price_observations_atomic(rows, tmp_path)

    df = pd.read_parquet(tmp_path / "price_observations.parquet")
    assert len(df) == 2
    PriceObservationRow(**{k: df[k].iloc[0] for k in PriceObservationRow.model_fields})


def test_write_price_observations_atomic_accumulates_across_invoices(tmp_path):
    """Unlike bom/sales_export's full-replace model, price history is never discarded — a second
    invoice's rows are ADDED to the first's, not swapped in for them."""
    first = invoice_upload.parse_invoice_csv(_VALID_INVOICE).rows
    invoice_upload.write_price_observations_atomic(first, tmp_path)

    second_raw = (
        b"ingredient_name,unit_price,source_invoice,observed_date\n"
        b"beef patty,4.10,INV-002,2026-06-08\n"
    )
    second = invoice_upload.parse_invoice_csv(second_raw).rows
    invoice_upload.write_price_observations_atomic(second, tmp_path)

    df = pd.read_parquet(tmp_path / "price_observations.parquet")
    assert len(df) == 3
    assert set(df["source_invoice"]) == {"INV-001", "INV-002"}


def test_write_price_observations_atomic_is_idempotent_on_exact_resubmit(tmp_path):
    """Reproducibility/idempotency (rule 07): re-uploading the SAME invoice must not duplicate
    rows — a chef re-submitting after a network hiccup shouldn't double their price history."""
    rows = invoice_upload.parse_invoice_csv(_VALID_INVOICE).rows
    invoice_upload.write_price_observations_atomic(rows, tmp_path)
    invoice_upload.write_price_observations_atomic(rows, tmp_path)

    df = pd.read_parquet(tmp_path / "price_observations.parquet")
    assert len(df) == 2
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_price_observations_atomic_rejects_empty_input(tmp_path):
    with pytest.raises(ValueError, match="no price rows"):
        invoice_upload.write_price_observations_atomic([], tmp_path)


def test_write_price_observations_atomic_serializes_concurrent_writers(tmp_path, monkeypatch):
    """MINOR-5 (W3_review.md): the read-modify-write is not safe under concurrent writers on its
    own — only the final rename is atomic. Widen the race window with an injected delay inside the
    write: without the advisory lock, writer B's read (of the pre-write state) lands before writer
    A's rename, so B's later rename would silently discard A's row. With the lock, B blocks until
    A's whole read-combine-write-rename sequence finishes."""
    import threading
    import time

    real_stage = invoice_upload._stage_parquet

    def slow_stage(df, dest):
        time.sleep(0.05)
        return real_stage(df, dest)

    monkeypatch.setattr(invoice_upload, "_stage_parquet", slow_stage)

    row_a = PriceObservationRow(
        ingredient_id="beef", ingredient_name="beef", unit_price=3.00,
        source_invoice="INV-A", observed_date="2026-06-01",
    )
    row_b = PriceObservationRow(
        ingredient_id="pork", ingredient_name="pork", unit_price=2.00,
        source_invoice="INV-B", observed_date="2026-06-01",
    )

    t1 = threading.Thread(
        target=invoice_upload.write_price_observations_atomic, args=([row_a], tmp_path)
    )
    t2 = threading.Thread(
        target=invoice_upload.write_price_observations_atomic, args=([row_b], tmp_path)
    )
    t1.start()
    time.sleep(0.01)  # let t1 grab the lock first
    t2.start()
    t1.join()
    t2.join()

    df = pd.read_parquet(tmp_path / "price_observations.parquet")
    assert set(df["ingredient_id"]) == {"beef", "pork"}  # neither writer's row was lost
