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
    rd = tmp_path / "raw"
    rd.mkdir()
    _write_pos(rd)
    return rd


def test_rejects_non_raw_dir(tmp_path):
    """The loader whitelists the raw store — a non-raw (e.g. oracle) dir is refused."""
    bad = tmp_path / "_truth"
    bad.mkdir()
    with pytest.raises(ValueError, match="raw"):
        load_pos_sales(bad)


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
