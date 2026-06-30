"""Seam schema accept/reject tests -- the data-quality gate (schemas/seam.py).

Good data passes; every category of malformed data is rejected. This is the "head chef checks
every dish before it goes out" gate, exercised directly.
"""
import pytest
from pydantic import ValidationError

from schemas import BomRow, SalesExportRow


def _bom(**over):
    base = dict(
        dish_id="d1", dish_name="Short Rib", ingredient_id="i1", ingredient_name="beef",
        qty=12.0, recipe_unit="oz", canonical_unit="oz", yield_factor=0.7,
    )
    base.update(over)
    return base


def test_bomrow_accepts_valid():
    BomRow(**_bom())


@pytest.mark.parametrize("bad", [
    {"yield_factor": 1.4},   # > 1 is impossible (can't yield more than purchased)
    {"yield_factor": 0.0},   # must be > 0
    {"qty": 0.0},            # must be > 0
    {"dish_name": ""},       # required, non-empty
    {"ingredient_id": ""},   # required, non-empty
])
def test_bomrow_rejects_bad(bad):
    with pytest.raises(ValidationError):
        BomRow(**_bom(**bad))


def _sales(**over):
    base = dict(dish_name="Burger", count="120", period_start="2026-06-01", period_end="2026-06-07")
    base.update(over)
    return base


def test_salesrow_accepts_valid_and_coerces_count():
    row = SalesExportRow(**_sales())
    assert row.count == 120  # str "120" coerced to int


@pytest.mark.parametrize("bad", [
    {"count": -5},                                                # covers can't be negative
    {"count": "lots"},                                           # non-numeric
    {"dish_name": ""},                                          # required, non-empty
    {"period_start": "2026-06-07", "period_end": "2026-06-01"},  # end before start
])
def test_salesrow_rejects_bad(bad):
    with pytest.raises(ValidationError):
        SalesExportRow(**_sales(**bad))
