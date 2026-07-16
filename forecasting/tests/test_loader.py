"""Tests for the raw -> observed-demand loader (Phase 1)."""
from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

from forecasting.src.data.loader import build_observed_demand, load_pos_sales


def _write_pos(raw_dir: Path) -> None:
    """A tiny, hand-checkable POS export: two dayparts, a void, an empty daypart.

    Uses era-3 display names (2023-01-02 falls in Fall 2022, era 3):
      house_burger → "House Burger", tuna_tartare → "Tuna Tartare"
    pos_sales no longer contains a stable item_id (issue #5); build_observed_demand
    reconciles item_name → item_id via the alias map in config/sim.yaml.
    """
    rows = [
        ("2023-01-02", "2023-01-02 12:00:00", "House Burger", 1, False),
        ("2023-01-02", "2023-01-02 12:30:00", "House Burger", 1, False),
        ("2023-01-02", "2023-01-02 19:00:00", "House Burger", 1, False),
        ("2023-01-02", "2023-01-02 19:30:00", "House Burger", 1, True),   # void -> excluded
        ("2023-01-02", "2023-01-02 13:00:00", "Tuna Tartare", 1, False),
        ("2023-01-03", "2023-01-03 19:00:00", "House Burger", 1, False),
    ]
    df = pd.DataFrame(
        rows, columns=["business_date", "sold_at", "item_name", "qty", "void_flag"]
    )
    df["check_id"] = "c"
    df["line_id"] = "l"
    df["category"] = "Entree"
    df["menu_price"] = 10.0
    df["modifiers"] = ""
    df["discount_amount"] = 0.0
    df["comp_flag"] = None
    df["server_id"] = "S003"
    df.to_csv(raw_dir / "pos_sales.csv", index=False)


@pytest.fixture
def raw_dir(tmp_path):
    # W9: the loader now reads a tenant subdirectory of raw/, not raw/ itself.
    rd = tmp_path / "raw" / "tenant-a"
    rd.mkdir(parents=True)
    _write_pos(rd)
    return rd


def test_rejects_non_raw_dir(tmp_path):
    """The loader whitelists the raw store — a non-raw (e.g. oracle) dir is refused."""
    bad = tmp_path / "_truth" / "tenant-a"
    bad.mkdir(parents=True)
    with pytest.raises(ValueError, match="raw"):
        load_pos_sales(bad)


def test_rejects_bare_raw_dir_with_no_tenant_segment(tmp_path):
    """W9: data/raw/ itself is a container, not a readable tenant directory — a caller must
    always name a specific tenant subdirectory, never the flat store."""
    bad = tmp_path / "raw"
    bad.mkdir()
    with pytest.raises(ValueError, match="raw"):
        load_pos_sales(bad)


def test_tenant_isolation_reads_only_the_named_restaurants_rows(tmp_path):
    """Two tenants' data can coexist under data/raw/ without either leaking into the other's
    read -- the loader only ever opens the one subdirectory it's given."""
    tenant_a = tmp_path / "raw" / "tenant-a"
    tenant_b = tmp_path / "raw" / "tenant-b"
    tenant_a.mkdir(parents=True)
    tenant_b.mkdir(parents=True)
    _write_pos(tenant_a)
    pd.DataFrame(
        [("2023-01-02", "2023-01-02 12:00:00", "Tuna Tartare", 5, False)],
        columns=["business_date", "sold_at", "item_name", "qty", "void_flag"],
    ).assign(
        check_id="c", line_id="l", category="Entree", menu_price=10.0, modifiers="",
        discount_amount=0.0, comp_flag=None, server_id="S003",
    ).to_csv(tenant_b / "pos_sales.csv", index=False)

    demand_a = build_observed_demand(tenant_a)
    demand_b = build_observed_demand(tenant_b)

    a_burger_dinner = demand_a[
        (demand_a["item_id"] == "house_burger") & (demand_a["service_period"] == "dinner")
    ]["demand"].iloc[0]
    assert a_burger_dinner == 1  # tenant-a's own rows, unaffected by tenant-b's data existing

    # tenant-b never sold a burger -- its own read must show 0, not tenant-a's rows leaking in.
    # (build_observed_demand reindexes onto the full known-item grid, so "house_burger" is
    # still a row for tenant-b -- at demand 0, never at tenant-a's actual count.)
    b_burger_lunch = demand_b[
        (demand_b["item_id"] == "house_burger") & (demand_b["service_period"] == "lunch")
    ]["demand"].iloc[0]
    assert b_burger_lunch == 0


def test_voids_excluded(raw_dir):
    d = build_observed_demand(raw_dir)
    # 2023-01-02 dinner house_burger: 2 rung, 1 voided -> 1 counted
    val = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
        & (d["service_period"] == "dinner")
    ]["demand"].iloc[0]
    assert val == 1


def test_service_period_derived_from_timestamp(raw_dir):
    d = build_observed_demand(raw_dir)
    lunch = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
        & (d["service_period"] == "lunch")
    ]["demand"].iloc[0]
    assert lunch == 2  # the two noon burgers


def test_empty_daypart_is_zero_not_missing(raw_dir):
    """A date/item/daypart with no sales must surface as 0 so overage is chargeable."""
    d = build_observed_demand(raw_dir)
    row = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "tuna_tartare")
        & (d["service_period"] == "dinner")
    ]
    assert len(row) == 1
    assert row["demand"].iloc[0] == 0


def test_demand_is_nonneg_int(raw_dir):
    d = build_observed_demand(raw_dir)
    assert (d["demand"] >= 0).all()
    assert d["demand"].dtype.kind in "iu"


def test_business_date_is_date_object(raw_dir):
    """Loader returns real date objects, not strings (the backtest needs this; a string
    column silently produces an empty backtest)."""
    d = build_observed_demand(raw_dir)
    assert isinstance(d["business_date"].iloc[0], datetime.date)


def test_loader_source_never_names_the_oracle():
    """Structural belt-and-suspenders: the loader must not even reference a _truth path."""
    src = (Path(__file__).resolve().parents[1] / "src" / "data" / "loader.py").read_text()
    assert "_truth" not in src
