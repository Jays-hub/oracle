"""Tests for src/costing/tenant_grid.py — the W6 costed reveal over real captured data.

Covers: build_tenant_grid's hand-computed cost/margin/quadrant correctness, that a dish with no
menu price (or no costable ingredients) is excluded from the grid and named as unpriced rather
than dropped silently, that build_food_cost_rows derives Co independent of menu_price, and that
write_food_cost_atomic is a full-replace write (mirrors write_seam_atomic, not the accumulating
price_observations model).
"""
from datetime import date

import pandas as pd
import pytest

from src.costing.tenant_grid import (
    build_dish_line_items,
    build_food_cost_rows,
    build_tenant_grid,
    clear_food_cost,
    write_food_cost_atomic,
)
from src.report.grid import round_to_quarter

_BOM = pd.DataFrame([
    {"dish_id": "burger", "dish_name": "Burger", "ingredient_id": "beef", "ingredient_name": "beef",
     "qty": 6.0, "recipe_unit": "oz", "canonical_unit": "oz", "yield_factor": 0.9},
    {"dish_id": "salad", "dish_name": "Salad", "ingredient_id": "romaine", "ingredient_name": "romaine",
     "qty": 4.0, "recipe_unit": "oz", "canonical_unit": "oz", "yield_factor": 1.0},
])
_SALES = pd.DataFrame([
    {"dish_name": "Burger", "count": 100},
    {"dish_name": "Salad", "count": 10},
])
_PRICES = pd.DataFrame([
    {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.0,
     "source_invoice": "inv-1", "observed_date": "2026-06-01"},
    # no romaine price -> Salad can't be costed
])


def test_build_tenant_grid_hand_computed_cost_and_margin():
    menu_prices = {"burger": 25.00}
    rows, unpriced = build_tenant_grid(_BOM, _SALES, _PRICES, menu_prices)
    assert len(rows) == 1
    burger = rows[0]
    # 6oz beef / 0.9 yield * $3.00/oz = $20.00
    assert burger.cost == pytest.approx(20.00)
    assert burger.margin == pytest.approx(5.00)  # 25.00 - 20.00
    assert burger.covers == 100


def test_build_tenant_grid_excludes_dish_with_no_menu_price():
    """Burger is fully costable but has no menu price set — must be excluded from the grid and
    named in unpriced, never silently dropped or shown with a fabricated price."""
    rows, unpriced = build_tenant_grid(_BOM, _SALES, _PRICES, {})
    assert rows == []
    reasons = {u.dish_name: u.reason for u in unpriced}
    assert reasons["Burger"] == "No menu price set yet."
    assert reasons["Salad"] == "Ingredient cost not yet available (a price or a convertible unit is missing)."


def test_build_tenant_grid_excludes_dish_with_missing_ingredient_price():
    """Salad has a menu price but romaine has no price observation -- still excluded, not costed
    at $0."""
    rows, unpriced = build_tenant_grid(_BOM, _SALES, _PRICES, {"burger": 25.00, "salad": 9.00})
    assert {r.name for r in rows} == {"Burger"}
    assert [u.dish_name for u in unpriced] == ["Salad"]


def test_build_tenant_grid_empty_bom_returns_nothing():
    rows, unpriced = build_tenant_grid(pd.DataFrame(), _SALES, _PRICES, {"burger": 25.00})
    assert rows == [] and unpriced == []


def test_build_tenant_grid_handles_no_sales_yet():
    """A dish can be fully priced/costed before any sales history exists -- covers just reads 0,
    not an error."""
    rows, _ = build_tenant_grid(_BOM, pd.DataFrame(), _PRICES, {"burger": 25.00})
    assert rows[0].covers == 0


def test_build_food_cost_rows_independent_of_menu_price():
    """Co is pure ingredient cost -- Burger gets a FoodCostRow even though no menu price was ever
    set anywhere in this test."""
    rows = build_food_cost_rows(_BOM, _PRICES, as_of=date(2026, 7, 14))
    assert len(rows) == 1
    assert rows[0].dish_id == "burger"
    assert rows[0].food_cost == pytest.approx(20.00)
    assert rows[0].computed_at == date(2026, 7, 14)


def test_build_food_cost_rows_excludes_uncostable_dishes():
    rows = build_food_cost_rows(_BOM, _PRICES, as_of=date(2026, 7, 14))
    assert "salad" not in {r.dish_id for r in rows}


def test_build_food_cost_rows_empty_bom_returns_nothing():
    assert build_food_cost_rows(pd.DataFrame(), _PRICES, as_of=date(2026, 7, 14)) == []


_MULTI_INGREDIENT_BOM = pd.DataFrame([
    {"dish_id": "fries", "dish_name": "Fries", "ingredient_id": "garlic", "ingredient_name": "garlic",
     "qty": 0.5, "recipe_unit": "oz", "canonical_unit": "oz", "yield_factor": 1.0},
    {"dish_id": "fries", "dish_name": "Fries", "ingredient_id": "butter", "ingredient_name": "butter",
     "qty": 0.5, "recipe_unit": "oz", "canonical_unit": "oz", "yield_factor": 1.0},
    {"dish_id": "fries", "dish_name": "Fries", "ingredient_id": "salt", "ingredient_name": "salt",
     "qty": 0.5, "recipe_unit": "oz", "canonical_unit": "oz", "yield_factor": 1.0},
])
_MULTI_INGREDIENT_PRICES = pd.DataFrame([
    {"ingredient_id": "garlic", "ingredient_name": "garlic", "unit_price": 0.20,
     "source_invoice": "inv-1", "observed_date": "2026-06-01"},
    {"ingredient_id": "butter", "ingredient_name": "butter", "unit_price": 0.24,
     "source_invoice": "inv-1", "observed_date": "2026-06-01"},
    {"ingredient_id": "salt", "ingredient_name": "salt", "unit_price": 0.20,
     "source_invoice": "inv-1", "observed_date": "2026-06-01"},
])


def test_build_dish_line_items_reconciles_with_grid_for_a_multi_ingredient_dish():
    """Regression for W6_review.md BLOCKER-1: garlic ($0.10), butter ($0.12), and salt ($0.10)
    each round to $0.00 individually (round_to_quarter(0.10) == round_to_quarter(0.12) == 0.0)
    but sum to a real $0.32 -- rounding ONCE on that aggregate gives $0.25, not $0.00.
    build_dish_line_items's total must equal the grid's own rounded cost for the identical BOM,
    not a separately-rounded-then-summed total."""
    lines, cost_display = build_dish_line_items(_MULTI_INGREDIENT_BOM, _MULTI_INGREDIENT_PRICES, "fries")
    assert len(lines) == 3
    assert cost_display == pytest.approx(0.25)

    rows, _ = build_tenant_grid(
        _MULTI_INGREDIENT_BOM, pd.DataFrame(), _MULTI_INGREDIENT_PRICES, {"fries": 9.00},
    )
    assert rows[0].cost == pytest.approx(0.32)  # the grid's precise cost, rounded only at display
    assert round_to_quarter(rows[0].cost) == cost_display


def test_build_dish_line_items_per_line_costs_are_not_rounded():
    """Per-line costs are the audit trail (rule 06 "provenance is reachable") -- shown at real
    cents, never individually snapped to the $0.25 grid (that would be the BLOCKER-1 bug)."""
    lines, _ = build_dish_line_items(_MULTI_INGREDIENT_BOM, _MULTI_INGREDIENT_PRICES, "fries")
    costs = {line.ingredient_name: line.as_used_cost for line in lines}
    assert costs["garlic"] == pytest.approx(0.10)
    assert costs["butter"] == pytest.approx(0.12)
    assert costs["salt"] == pytest.approx(0.10)


def test_build_dish_line_items_uncosted_when_a_price_is_missing():
    rows_missing_salt = _MULTI_INGREDIENT_PRICES[
        _MULTI_INGREDIENT_PRICES["ingredient_id"] != "salt"
    ]
    lines, cost_display = build_dish_line_items(_MULTI_INGREDIENT_BOM, rows_missing_salt, "fries")
    assert cost_display is None
    salt_line = next(line for line in lines if line.ingredient_name == "salt")
    assert salt_line.as_used_cost is None


def test_write_food_cost_atomic_is_a_full_replace(tmp_path):
    """Unlike price_observations (accumulates), food_cost is a current snapshot -- writing again
    must REPLACE the prior contents, not append to them."""
    rows_v1 = build_food_cost_rows(_BOM, _PRICES, as_of=date(2026, 7, 14))
    write_food_cost_atomic(rows_v1, tmp_path)

    # A price move changes the cost; a second write must overwrite, not accumulate two rows.
    prices_v2 = pd.DataFrame([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.50,
         "source_invoice": "inv-2", "observed_date": "2026-06-08"},
    ])
    rows_v2 = build_food_cost_rows(_BOM, prices_v2, as_of=date(2026, 7, 21))
    write_food_cost_atomic(rows_v2, tmp_path)

    on_disk = pd.read_parquet(tmp_path / "food_cost.parquet")
    assert len(on_disk) == 1
    assert on_disk["food_cost"].iloc[0] == pytest.approx(6.0 / 0.9 * 3.50)


def test_write_food_cost_atomic_rejects_empty_rows(tmp_path):
    with pytest.raises(ValueError):
        write_food_cost_atomic([], tmp_path)


def test_clear_food_cost_removes_an_existing_file(tmp_path):
    rows = build_food_cost_rows(_BOM, _PRICES, as_of=date(2026, 7, 14))
    write_food_cost_atomic(rows, tmp_path)
    assert (tmp_path / "food_cost.parquet").exists()

    clear_food_cost(tmp_path)
    assert not (tmp_path / "food_cost.parquet").exists()


def test_clear_food_cost_is_a_noop_when_no_file_exists(tmp_path):
    clear_food_cost(tmp_path)  # must not raise
