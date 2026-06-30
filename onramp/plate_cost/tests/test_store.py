"""Tests for the on-ramp DuckDB store helper (src/store.py).

Verifies the structural constraints from .claude/rules/05-fullstack-architecture.md:
- _RAW_DIR is hard-coded to data/raw/ and cannot be parameterized
- read_bom() / read_sales() return DataFrames from the expected Parquet files
- the public API accepts no path parameters (the firewall is structural, not conventional)
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

from src import store


def test_raw_dir_invariant():
    """_RAW_DIR is hard-wired to data/raw/ — the structural firewall constraint."""
    assert store._RAW_DIR.parts[-1] == "raw"
    assert store._RAW_DIR.parts[-2] == "data"


def test_raw_dir_exists():
    assert store._RAW_DIR.is_dir()


def test_raw_dir_not_parameterizable():
    """Calling read_bom / read_sales with an alternate path must not be possible — there is no
    such parameter. Verify both functions take zero arguments (the structural constraint)."""
    import inspect as _inspect
    sig_bom = _inspect.signature(store.read_bom)
    sig_sales = _inspect.signature(store.read_sales)
    assert len(sig_bom.parameters) == 0, "read_bom must not accept a path parameter"
    assert len(sig_sales.parameters) == 0, "read_sales must not accept a path parameter"


def test_read_bom_round_trip(tmp_path, monkeypatch):
    """A BOM Parquet written with the correct schema is readable and schema-valid via read_bom()."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from schemas import BomRow

    row = BomRow(
        dish_id="d1", dish_name="Short Rib",
        ingredient_id="i1", ingredient_name="beef",
        qty=12.0, recipe_unit="oz", canonical_unit="oz", yield_factor=0.7,
    )
    pd.DataFrame([row.model_dump()]).to_parquet(
        tmp_path / "bom.parquet", index=False, engine="pyarrow"
    )

    monkeypatch.setattr(store, "_RAW_DIR", tmp_path)
    df = store.read_bom()

    assert len(df) == 1
    assert df["dish_name"].iloc[0] == "Short Rib"
    assert df["qty"].iloc[0] == pytest.approx(12.0)
    # Round-trip must still satisfy the seam schema.
    BomRow(**{k: df[k].iloc[0] for k in BomRow.model_fields})


def test_read_sales_round_trip(tmp_path, monkeypatch):
    """A sales Parquet written with the correct schema is readable and schema-valid via read_sales()."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from schemas import SalesExportRow

    row = SalesExportRow(
        dish_name="Burger", count=120,
        period_start="2026-06-01", period_end="2026-06-07",
    )
    pd.DataFrame([row.model_dump()]).to_parquet(
        tmp_path / "sales_export.parquet", index=False, engine="pyarrow"
    )

    monkeypatch.setattr(store, "_RAW_DIR", tmp_path)
    df = store.read_sales()

    assert len(df) == 1
    assert df["dish_name"].iloc[0] == "Burger"
    assert int(df["count"].iloc[0]) == 120


def test_read_missing_file_fails_legibly(tmp_path, monkeypatch):
    """A missing seam file raises a legible FileNotFoundError (rule 07), not a raw DuckDB IO error."""
    monkeypatch.setattr(store, "_RAW_DIR", tmp_path)  # empty dir — no parquet present
    with pytest.raises(FileNotFoundError, match="data/raw/bom.parquet"):
        store.read_bom()
