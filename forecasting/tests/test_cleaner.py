"""Tests for the Phase-2 signal cleaner (forecasting/src/data/cleaner.py)."""
from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

from forecasting.src.data.cleaner import clean_demand


# Era-3 names (dates 2022-10-01 to 2023-01-14 are era 3 in sim.yaml):
#   house_burger → "House Burger",  tuna_tartare → "Tuna Tartare"
_DATE = "2023-01-02"
_SOLD_LUNCH = f"{_DATE} 12:00:00"
_SOLD_DINNER = f"{_DATE} 19:00:00"


def _base_row(**overrides) -> dict:
    """Minimal valid pos_sales row; caller overrides any field."""
    row = {
        "check_id": "c",
        "line_id": "l",
        "business_date": _DATE,
        "sold_at": _SOLD_DINNER,
        "item_name": "House Burger",
        "category": "Entree",
        "menu_price": 20.0,
        "qty": 1,
        "modifiers": "",
        "discount_amount": 0.0,
        "comp_flag": None,
        "void_flag": False,
        "server_id": "S003",
    }
    row.update(overrides)
    return row


def _write_pos(raw_dir: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(raw_dir / "pos_sales.csv", index=False)


def _write_eightysix(raw_dir: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(raw_dir / "eightysix_log.csv", index=False)


@pytest.fixture
def raw_dir(tmp_path):
    rd = tmp_path / "raw"
    rd.mkdir()
    _write_eightysix(rd, [])  # default: no 86 events
    return rd


# ------------------------------------------------------------------ exclusions --

def test_comp_flagged_rows_kept(raw_dir):
    """comp_flag=True rows count toward demand — a comp tags a real, fulfilled order
    (the kitchen prepped and served it), not phantom demand. Verified against
    data/_truth/truth_demand.csv: excluding these rows moves observed demand further
    from truth, not closer (see cleaner.py module docstring)."""
    _write_pos(raw_dir, [
        _base_row(item_name="House Burger", comp_flag=True),   # real order, comped
        _base_row(item_name="House Burger", comp_flag=False),  # real order, full price
    ])
    d = clean_demand(raw_dir)
    row = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
        & (d["service_period"] == "dinner")
    ]
    assert row["demand"].iloc[0] == 2, "comp_flag=True row should count as demand"


def test_staff_server_rows_excluded(raw_dir):
    """Rows from staff server ids (S001, S002 per sim.yaml) must be excluded."""
    _write_pos(raw_dir, [
        _base_row(item_name="House Burger", server_id="S001"),  # staff — excluded
        _base_row(item_name="House Burger", server_id="S003"),  # guest — kept
    ])
    d = clean_demand(raw_dir)
    row = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
        & (d["service_period"] == "dinner")
    ]
    assert row["demand"].iloc[0] == 1, "Staff-server row should be excluded"


def test_void_rows_excluded(raw_dir):
    """void_flag=True rows must not count toward demand."""
    _write_pos(raw_dir, [
        _base_row(item_name="House Burger", void_flag=True),   # void — excluded
        _base_row(item_name="House Burger", void_flag=False),  # real sale — kept
    ])
    d = clean_demand(raw_dir)
    row = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
        & (d["service_period"] == "dinner")
    ]
    assert row["demand"].iloc[0] == 1, "Void row should be excluded"


# ------------------------------------------------------------------ data quality (rule 01) --

def test_missingness_report_printed(raw_dir, capsys):
    """clean_demand must print a missingness report before any exclusion (rule 01)."""
    _write_pos(raw_dir, [_base_row(item_name="House Burger")])
    clean_demand(raw_dir)
    assert "missingness report" in capsys.readouterr().out


def test_qty_zero_anomaly_quarantined_and_logged(raw_dir, capsys):
    """A qty==0 row with no void/comp flag is a data-quality anomaly (rule 01) --
    quarantined and logged, not silently treated as either a sale or censored demand."""
    _write_pos(raw_dir, [
        _base_row(item_name="House Burger", qty=0, void_flag=False, comp_flag=None),
        _base_row(item_name="House Burger", qty=1),
    ])
    clean_demand(raw_dir)
    assert "QUARANTINED 1 qty==0 rows" in capsys.readouterr().out


def test_qty_zero_void_row_not_flagged_as_anomaly(raw_dir, capsys):
    """A qty==0 row that IS void-flagged is explained by the void, not an anomaly."""
    _write_pos(raw_dir, [_base_row(item_name="House Burger", qty=0, void_flag=True)])
    clean_demand(raw_dir)
    assert "QUARANTINED" not in capsys.readouterr().out


def test_silent_comp_remains(raw_dir):
    """A row with no comp_flag (silent comp) is invisible at the information boundary
    and must remain in the demand count — removing it would require truth-side knowledge."""
    _write_pos(raw_dir, [
        _base_row(item_name="House Burger", comp_flag=None, discount_amount=20.0),
        _base_row(item_name="House Burger"),
    ])
    d = clean_demand(raw_dir)
    row = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
        & (d["service_period"] == "dinner")
    ]
    assert row["demand"].iloc[0] == 2, (
        "Silent comp (no comp_flag) must stay in demand — it is observable noise, "
        "not removable without ground-truth knowledge"
    )


# ------------------------------------------------------------------ censoring --

def test_86d_day_tagged_censored(raw_dir):
    """An item that was 86'd on a date is tagged censored=True for that date."""
    _write_pos(raw_dir, [_base_row(item_name="House Burger")])
    _write_eightysix(raw_dir, [
        {"business_date": _DATE, "item_name": "House Burger", "time_86d": "20:30:00"}
    ])
    d = clean_demand(raw_dir)
    row = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
    ]
    assert row["censored"].any(), "Item that was 86'd must be tagged censored=True"


def test_dinner_86_leaves_lunch_uncensored(raw_dir):
    """A dinner-service 86 must not mark that day's LUNCH row censored too (MINOR-4:
    censored_keys must be scoped by service_period via time_86d, not just date+item)."""
    _write_pos(raw_dir, [
        _base_row(item_name="House Burger", sold_at=_SOLD_LUNCH),
        _base_row(item_name="House Burger", sold_at=_SOLD_DINNER),
    ])
    _write_eightysix(raw_dir, [
        {"business_date": _DATE, "item_name": "House Burger", "time_86d": "20:30:00"}
    ])
    d = clean_demand(raw_dir)
    lunch = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
        & (d["service_period"] == "lunch")
    ]
    dinner = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
        & (d["service_period"] == "dinner")
    ]
    assert not lunch["censored"].iloc[0], "A dinner 86 must not censor the lunch row"
    assert dinner["censored"].iloc[0], "The dinner row itself must still be censored"


def test_non_86d_item_not_censored(raw_dir):
    """Items NOT in the eightysix_log on a date are tagged censored=False."""
    _write_pos(raw_dir, [
        _base_row(item_name="House Burger"),
        _base_row(item_name="Tuna Tartare"),
    ])
    _write_eightysix(raw_dir, [
        {"business_date": _DATE, "item_name": "House Burger", "time_86d": "20:30:00"}
    ])
    d = clean_demand(raw_dir)
    tartare = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "tuna_tartare")
    ]
    assert not tartare["censored"].any(), (
        "tuna_tartare was not 86'd on this date — must not be tagged censored"
    )


def test_86d_item_name_reconciled(raw_dir):
    """The eightysix_log also uses a drifting item_name; the cleaner must reconcile it
    using the same alias map so the censored tag lands on the right canonical item_id."""
    _write_pos(raw_dir, [_base_row(item_name="Tuna Tartare")])
    # Use an alternate era alias in the 86 log
    _write_eightysix(raw_dir, [
        {"business_date": _DATE, "item_name": "Tartare", "time_86d": "21:00:00"}
    ])
    d = clean_demand(raw_dir)
    row = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "tuna_tartare")
    ]
    assert row["censored"].any(), (
        "'Tartare' is an era alias for tuna_tartare — censored tag must reconcile via "
        "the alias map and land on the correct item_id"
    )


# ------------------------------------------------------------------ schema & types --

def test_output_schema(raw_dir):
    """Output must contain the five expected columns."""
    _write_pos(raw_dir, [_base_row()])
    d = clean_demand(raw_dir)
    required = {"business_date", "item_id", "service_period", "demand", "censored"}
    assert required.issubset(set(d.columns)), (
        f"Missing columns: {required - set(d.columns)}"
    )


def test_demand_nonneg_int(raw_dir):
    """Demand must be a non-negative integer after cleaning."""
    _write_pos(raw_dir, [_base_row(), _base_row(item_name="Tuna Tartare")])
    d = clean_demand(raw_dir)
    assert (d["demand"] >= 0).all(), "Negative demand after cleaning"
    assert d["demand"].dtype.kind in "iu", "Demand dtype is not integer"


def test_name_reconciliation(raw_dir):
    """Drifting display name 'House Burger' (era 3) maps to canonical 'house_burger'."""
    _write_pos(raw_dir, [_base_row(item_name="House Burger")])
    d = clean_demand(raw_dir)
    assert "house_burger" in d["item_id"].values, (
        "'House Burger' should reconcile to canonical item_id 'house_burger'"
    )
    assert "House Burger" not in d["item_id"].values, (
        "item_id column must contain canonical ids, not raw display names"
    )


def test_empty_daypart_is_zero_not_missing(raw_dir):
    """A date/item/daypart with no (clean) sales surfaces as demand=0, not absent."""
    _write_pos(raw_dir, [_base_row(item_name="House Burger", sold_at=_SOLD_DINNER)])
    d = clean_demand(raw_dir)
    lunch_row = d[
        (d["business_date"] == datetime.date(2023, 1, 2))
        & (d["item_id"] == "house_burger")
        & (d["service_period"] == "lunch")
    ]
    assert len(lunch_row) == 1, "Lunch daypart must appear even with zero demand"
    assert lunch_row["demand"].iloc[0] == 0


def test_business_date_is_date_object(raw_dir):
    """business_date column must hold real date objects (not strings)."""
    _write_pos(raw_dir, [_base_row()])
    d = clean_demand(raw_dir)
    assert isinstance(d["business_date"].iloc[0], datetime.date)
