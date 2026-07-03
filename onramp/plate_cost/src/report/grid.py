from dataclasses import dataclass
from uuid import UUID


def normalize_name(name: str) -> str:
    """Canonical key for joining a menu item to its sales rows: trim surrounding whitespace and
    casefold, so 'Braised Short Rib ' and 'braised short rib' match instead of silently scoring 0
    covers — which would drop a popular dish into the 'Dog' quadrant by mislabel alone."""
    return name.strip().casefold()


# Tiers based on food cost % (cost / menu_price) — the language chefs use.
# Low food cost % = strong margin. <25% strong, 25-35% acceptable, >35% thin.
_FOOD_COST_TIERS = [
    (0.0,  0.25, "strong"),
    (0.25, 0.35, "ok"),
    (0.35, 1.0,  "thin"),
]

_QUADRANT_ORDER = ["Star", "Plowhorse", "Puzzle", "Dog"]

QUADRANT_ACTIONS = {
    "Star":      "Protect & promote",
    "Plowhorse": "Reprice or renegotiate",
    "Puzzle":    "Reposition or rename",
    "Dog":       "Review — consider removing",
}


@dataclass
class DishResult:
    dish_id: UUID
    name: str
    menu_price: float
    cost: float
    margin: float
    food_cost_pct: float   # cost / menu_price — the chef-legible metric
    covers: int
    quadrant: str
    food_cost_tier: str


def food_cost_tier(food_cost_pct: float) -> str:
    for lo, hi, label in _FOOD_COST_TIERS:
        if lo <= food_cost_pct < hi:
            return label
    return "thin"


def round_to_quarter(value: float) -> float:
    return round(value * 4) / 4


def build_grid(
    dish_costs: dict[UUID, tuple],  # {dish_id: (Dish, cost_float)}
    covers: dict[str, int],         # {dish_name: total covers over period}
) -> list[DishResult]:
    # Match on a canonical key so a stray space / case difference doesn't silently score 0 covers.
    covers = {normalize_name(k): v for k, v in covers.items()}
    rows: list[DishResult] = []
    for dish_id, (dish, cost) in dish_costs.items():
        m = dish.menu_price - cost
        fcp = cost / dish.menu_price
        rows.append(DishResult(
            dish_id=dish_id,
            name=dish.name,
            menu_price=dish.menu_price,
            cost=cost,
            margin=m,
            food_cost_pct=fcp,
            covers=covers.get(normalize_name(dish.name), 0),
            quadrant="",
            food_cost_tier=food_cost_tier(fcp),
        ))

    if not rows:
        return rows

    mean_covers = sum(r.covers for r in rows) / len(rows)
    mean_margin = sum(r.margin for r in rows) / len(rows)

    for r in rows:
        pop_high = r.covers >= mean_covers
        margin_high = r.margin >= mean_margin
        if pop_high and margin_high:
            r.quadrant = "Star"
        elif pop_high and not margin_high:
            r.quadrant = "Plowhorse"
        elif not pop_high and margin_high:
            r.quadrant = "Puzzle"
        else:
            r.quadrant = "Dog"

    return sorted(
        rows,
        key=lambda r: (_QUADRANT_ORDER.index(r.quadrant), -r.margin),
    )


def covers_join_report(
    dish_costs: dict,                                  # {dish_id: (Dish, cost_float)}
    dishes: dict,                                       # {dish_id: Dish}
    covers_by_key: dict[str, tuple[str, int]],          # {normalized_name: (display_name, count)}
) -> tuple[list[str], list[str]]:
    """Surface mislabels loudly: a costed dish that matched no sales row (scores 0 covers, so it
    would land in 'Dog' by mislabel, not truth), and a sales row that matched no menu item (silently
    excluded). Shared by the CLI (`run.py`) and the web reveal so both fail the same honest way.

    Returns (unmatched_dishes, orphaned_sales), both sorted display names.
    """
    graded = {normalize_name(dish.name): dish.name for dish, _ in dish_costs.values()}
    unmatched_dishes = sorted(name for key, name in graded.items() if key not in covers_by_key)

    menu_keys = {normalize_name(d.name) for d in dishes.values()}
    orphaned_sales = sorted(
        display for key, (display, _) in covers_by_key.items() if key not in menu_keys
    )
    return unmatched_dishes, orphaned_sales


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
