"""Thin glue between the store/pricing-trends/opportunities compute and the /insights page.

Mirrors web/your_data.py's role for "your data": no business logic here (rule 05) — the only work
done here is rounding for display (rule 06: costs round to the nearest $0.25 grid), which stays a
presentation concern and is deliberately kept out of src/insights/opportunities.py's dollar math.
"""
from typing import TypedDict

from src import store
from src.insights.opportunities import Opportunity, build_opportunities
from src.pricing.trends import price_trend, significant_moves
from src.report.grid import round_to_quarter

_SIGNIFICANCE_THRESHOLD = 0.10


class AffectedDishDisplay(TypedDict):
    dish_name: str
    prior_cost: float
    new_cost: float
    delta: float


class OpportunityDisplay(TypedDict):
    headline: str
    ingredient_name: str
    pct_change: float
    direction: str
    affected_dishes: list[AffectedDishDisplay]


class InsightsSummary(TypedDict):
    has_data: bool
    opportunities: list[OpportunityDisplay]
    trend_count: int
    significant_count: int


def _display_opportunity(o: Opportunity) -> OpportunityDisplay:
    """Round every dollar figure to the nearest $0.25 grid, deriving delta from the SAME rounded
    prior/new costs so the row reconciles by eye (rule 06 — the same discipline report/grid.py's
    print_grid already applies to the popularity×margin grid)."""
    dishes: list[AffectedDishDisplay] = []
    for d in o.affected_dishes:
        prior_q = round_to_quarter(d.prior_cost)
        new_q = round_to_quarter(d.new_cost)
        dishes.append({
            "dish_name": d.dish_name, "prior_cost": prior_q, "new_cost": new_q,
            "delta": new_q - prior_q,
        })
    return {
        "headline": o.headline,
        "ingredient_name": o.ingredient_name,
        "pct_change": o.pct_change,
        "direction": o.direction,
        "affected_dishes": dishes,
    }


def build_insights_summary() -> InsightsSummary:
    """Read the operator's own BOM + price history back and compute this week's findings.

    Mirrors ``your_data.build_your_data_summary``'s FileNotFoundError handling: no capture yet on
    either leg (BOM not uploaded, or no invoice uploaded yet) reports a calm "nothing to show yet"
    state instead of an error page.
    """
    empty: InsightsSummary = {
        "has_data": False, "opportunities": [], "trend_count": 0, "significant_count": 0,
    }
    try:
        bom_df = store.read_bom()
        price_df = store.read_price_observations()
    except FileNotFoundError:
        return empty

    trend_df = price_trend(price_df)
    moves_df = significant_moves(trend_df, threshold=_SIGNIFICANCE_THRESHOLD)
    opportunities = build_opportunities(bom_df, price_df, threshold=_SIGNIFICANCE_THRESHOLD)

    return {
        "has_data": True,
        "opportunities": [_display_opportunity(o) for o in opportunities],
        "trend_count": len(trend_df),
        "significant_count": len(moves_df),
    }
