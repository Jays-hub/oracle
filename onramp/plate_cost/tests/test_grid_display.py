"""Regression test for the grid display fix (task #5): the printed margin must reconcile with the
printed (rounded) cost — Menu − ~Cost = Margin — instead of being computed from the unrounded cost."""
from src.bom.models import Dish
from src.report.grid import build_grid, print_grid


def test_row_margin_reconciles_with_rounded_cost(capsys):
    dish = Dish(name="Braised Short Rib", menu_price=42.0)
    dish_costs = {dish.id: (dish, 9.6765)}  # rounds to ~$9.75
    print_grid(build_grid(dish_costs, {"braised short rib": 85}))
    out = capsys.readouterr().out
    assert "~$9.75" in out      # cost rounded to nearest $0.25
    assert "$32.25" in out      # 42.00 - 9.75 -> reconciles by eye
    assert "$32.32" not in out  # the old unreconciled margin (42.00 - 9.6765)
