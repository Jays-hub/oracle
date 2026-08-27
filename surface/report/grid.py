"""Terminal rendering of the popularity x margin grid (L4).

Presentation only. The classification math — quadrants, food-cost tiers, the covers join — is L2
and lives in `measures/grid.py`; this module formats what that returns. The split is the layer
boundary made structural: `measures/costing/tenant_grid.py` and the web views consume the same
`build_grid()` without dragging a terminal printer along.
"""
from measures.grid import QUADRANT_ACTIONS, _QUADRANT_ORDER, DishResult, round_to_quarter


def print_grid(rows: list[DishResult], period_label: str = "covers on record") -> None:
    W = 74
    print("\n" + "=" * W)
    print("  MENU ENGINEERING GRID — Popularity x Margin")
    print(f"  {period_label}")
    print("=" * W)

    for quadrant in _QUADRANT_ORDER:
        items = [r for r in rows if r.quadrant == quadrant]
        if not items:
            continue
        print(f"\n  [{quadrant.upper()}S — {QUADRANT_ACTIONS[quadrant]}]")
        print(f"  {'Dish':<26}  {'Menu':>7}  {'~Cost':>7}  {'Margin':>8}  {'Food Cost%':<14}  {'Covers':>6}")
        print(f"  {'-'*26}  {'-'*7}  {'-'*7}  {'-'*8}  {'-'*14}  {'-'*6}")
        for r in items:
            # Round cost to the nearest $0.25, and derive the displayed margin from that SAME
            # rounded cost so the row reconciles by eye: Menu − ~Cost = Margin. (Directional truth,
            # never penny-accuracy — the module discipline. Quadrant classification still uses the
            # precise margin in build_grid; only the printed arithmetic is reconciled here.)
            cost_q = round_to_quarter(r.cost)
            cost_display = f"~${cost_q:.2f}"
            margin_display = r.menu_price - cost_q
            fc_display = f"{r.food_cost_pct:.0%} ({r.food_cost_tier})"
            print(
                f"  {r.name:<26}  "
                f"${r.menu_price:>6.2f}  "
                f"{cost_display:>7}  "
                f"${margin_display:>7.2f}  "
                f"{fc_display:<14}  "
                f"{r.covers:>6}"
            )

    total_covers = sum(r.covers for r in rows)
    # Use the same rounded-cost margin the rows display, so the footer reconciles with the grid.
    total_margin = sum((r.menu_price - round_to_quarter(r.cost)) * r.covers for r in rows)
    avg_margin_per_cover = total_margin / total_covers if total_covers else 0.0

    print("\n" + "-" * W)
    print(f"  {total_covers} covers  |  avg margin/cover: ${avg_margin_per_cover:.2f}")
    print("  Food Cost% = ingredient cost / menu price  |  Cost rounded to nearest $0.25")
    print("=" * W + "\n")
