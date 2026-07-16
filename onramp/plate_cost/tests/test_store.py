"""Tests for the on-ramp DuckDB store helper (src/store.py).

Verifies the structural constraints from .claude/rules/05-fullstack-architecture.md:
- RAW_DIR is hard-coded to data/raw/ and cannot be parameterized (this is the ONE canonical
  definition of the seam directory — seam_upload.py and web/app.py's writes both reference it
  directly rather than each keeping their own copy; W3_review.md LOW-1)
- read_bom() / read_sales() / read_price_observations() return DataFrames from the expected
  Parquet files, scoped to the restaurant_id the caller names (W9 tenant partitioning)
- tenant_raw_dir() validates restaurant_id before it ever becomes a filesystem path, and two
  tenants' data physically cannot leak into each other's read
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

from src import store


def test_raw_dir_invariant():
    """RAW_DIR is hard-wired to data/raw/ — the structural firewall constraint. It is the
    container of one subdirectory per tenant (W9); it is no longer itself a set of files."""
    assert store.RAW_DIR.parts[-1] == "raw"
    assert store.RAW_DIR.parts[-2] == "data"


def test_raw_dir_exists():
    assert store.RAW_DIR.is_dir()


def test_read_functions_require_restaurant_id():
    """W9: read_bom / read_sales / read_price_observations / read_food_cost must each require a
    restaurant_id — the seam is no longer a single flat store where a zero-arg read could ever
    have been correct. Replaces the pre-W9 test_raw_dir_not_parameterizable invariant (which
    asserted the opposite), since a partitioned seam structurally needs to know which tenant."""
    import inspect as _inspect
    for fn in (store.read_bom, store.read_sales, store.read_price_observations, store.read_food_cost):
        params = list(_inspect.signature(fn).parameters)
        assert params == ["restaurant_id"], f"{fn.__name__} must take exactly restaurant_id"


def test_tenant_raw_dir_rejects_path_traversal():
    """tenant_raw_dir() is the one place a caller-supplied string becomes a filesystem path in
    this module — it must reject anything that isn't a bare path-safe segment (rule 07)."""
    for hostile in ("../escape", "a/b", "a\\b", "..", "", "a" * 65, "abc\n"):
        with pytest.raises(ValueError, match="restaurant_id"):
            store.tenant_raw_dir(hostile)


def test_tenant_raw_dir_resolves_under_raw_dir():
    path = store.tenant_raw_dir("tenant-a")
    assert path == store.RAW_DIR / "tenant-a"
    assert path.parent == store.RAW_DIR


def test_tenant_isolation_reading_one_restaurant_never_returns_another(tmp_path, monkeypatch):
    """Two tenants' Parquet files can coexist under RAW_DIR without either leaking into the
    other's read (the concrete regression a subdirectory scheme exists to make impossible)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from schemas import BomRow

    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    tenant_a_dir = tmp_path / "tenant-a"
    tenant_b_dir = tmp_path / "tenant-b"
    tenant_a_dir.mkdir()
    tenant_b_dir.mkdir()

    a_row = BomRow(
        dish_id="d1", dish_name="Tenant A Dish", ingredient_id="i1", ingredient_name="beef",
        qty=1.0, recipe_unit="oz", canonical_unit="oz", yield_factor=1.0,
    )
    b_row = BomRow(
        dish_id="d2", dish_name="Tenant B Dish", ingredient_id="i2", ingredient_name="pork",
        qty=1.0, recipe_unit="oz", canonical_unit="oz", yield_factor=1.0,
    )
    pd.DataFrame([a_row.model_dump()]).to_parquet(
        tenant_a_dir / "bom.parquet", index=False, engine="pyarrow"
    )
    pd.DataFrame([b_row.model_dump()]).to_parquet(
        tenant_b_dir / "bom.parquet", index=False, engine="pyarrow"
    )

    df_a = store.read_bom("tenant-a")
    df_b = store.read_bom("tenant-b")
    assert df_a["dish_name"].tolist() == ["Tenant A Dish"]
    assert df_b["dish_name"].tolist() == ["Tenant B Dish"]


def test_read_bom_round_trip(tmp_path, monkeypatch):
    """A BOM Parquet written with the correct schema is readable and schema-valid via read_bom()."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from schemas import BomRow

    row = BomRow(
        dish_id="d1", dish_name="Short Rib",
        ingredient_id="i1", ingredient_name="beef",
        qty=12.0, recipe_unit="oz", canonical_unit="oz", yield_factor=0.7,
    )
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    tenant_dir = tmp_path / "tenant-a"
    tenant_dir.mkdir()
    pd.DataFrame([row.model_dump()]).to_parquet(
        tenant_dir / "bom.parquet", index=False, engine="pyarrow"
    )

    df = store.read_bom("tenant-a")

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
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    tenant_dir = tmp_path / "tenant-a"
    tenant_dir.mkdir()
    pd.DataFrame([row.model_dump()]).to_parquet(
        tenant_dir / "sales_export.parquet", index=False, engine="pyarrow"
    )

    df = store.read_sales("tenant-a")

    assert len(df) == 1
    assert df["dish_name"].iloc[0] == "Burger"
    assert int(df["count"].iloc[0]) == 120


def test_read_missing_file_fails_legibly(tmp_path, monkeypatch):
    """A missing seam file raises a legible FileNotFoundError (rule 07), not a raw DuckDB IO error."""
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    (tmp_path / "tenant-a").mkdir()  # tenant dir exists, but empty — no parquet present
    with pytest.raises(FileNotFoundError, match="data/raw/tenant-a/bom.parquet"):
        store.read_bom("tenant-a")


def test_read_price_observations_round_trip(tmp_path, monkeypatch):
    """W3: a price-observations Parquet written with the correct schema is readable and
    schema-valid via read_price_observations()."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from schemas import PriceObservationRow

    row = PriceObservationRow(
        ingredient_id="beef", ingredient_name="beef",
        unit_price=3.50, source_invoice="INV-001", observed_date="2026-06-01",
    )
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    tenant_dir = tmp_path / "tenant-a"
    tenant_dir.mkdir()
    pd.DataFrame([row.model_dump()]).to_parquet(
        tenant_dir / "price_observations.parquet", index=False, engine="pyarrow"
    )

    df = store.read_price_observations("tenant-a")

    assert len(df) == 1
    assert df["ingredient_name"].iloc[0] == "beef"
    assert df["unit_price"].iloc[0] == pytest.approx(3.50)
    PriceObservationRow(**{k: df[k].iloc[0] for k in PriceObservationRow.model_fields})


def test_read_price_observations_missing_file_fails_legibly(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    (tmp_path / "tenant-a").mkdir()
    with pytest.raises(FileNotFoundError, match="data/raw/tenant-a/price_observations.parquet"):
        store.read_price_observations("tenant-a")
