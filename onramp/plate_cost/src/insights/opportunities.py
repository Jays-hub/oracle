"""Dollar-quantified findings from a price move (W3's "opportunities" surface).

Given the operator's own captured BOM (``store.read_bom()``) and price-observation history
(``store.read_price_observations()``), find every dish affected by a significant ingredient price
move and how much its ingredient cost has shifted. No FastAPI import (rule 05).

**Deliberately does not claim a margin or food-cost-tier change** ("now your thinnest-margin
entree"). The seam carries no ``menu_price`` today — ``data/CONTRACT.md``'s "Co provenance" forward
note records that the engine can't reconstruct a plate cost from the seam yet, the same constraint
that already keeps ``/`` and ``/your-data`` from showing a costed grid over real captured data
(``docs/phase_decisions/W2.md``'s Explicitly Deferred table). Reporting a tier/margin claim without
a menu price would be a false-precision fabrication (rule 06); this module reports only what the
seam actually supports today — the ingredient-cost delta itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..bom.units import convert
from ..pricing.trends import latest_price_per_ingredient, price_trend, significant_moves


@dataclass
class AffectedDish:
    dish_name: str
    prior_cost: float
    new_cost: float

    @property
    def delta(self) -> float:
        return self.new_cost - self.prior_cost


@dataclass
class Opportunity:
    ingredient_name: str
    pct_change: float
    direction: str
    current_price: float
    prior_price: float
    days_span: int
    affected_dishes: list[AffectedDish] = field(default_factory=list)
    # Dishes the BOM says use this ingredient but that couldn't be fully costed (a sibling
    # ingredient has no price observation yet, or a non-convertible unit — see
    # dish_ingredient_cost). Tracked separately so the headline can state the TRUE affected count
    # rather than silently under-reporting it as just the costed subset (W3_review.md MINOR-4).
    uncosted_dish_count: int = 0

    @property
    def headline(self) -> str:
        sign = "+" if self.direction == "up" else ("-" if self.direction == "down" else "")
        pct = abs(self.pct_change) * 100
        # prior_candidates only guarantees the prior is AT LEAST lookback_days earlier, so the
        # true gap can be much larger than a week — only say "this week" when it plausibly is one
        # (W3_review.md MINOR-2: a 45-day-old prior was mislabeled "this week").
        span = "this week" if self.days_span <= 10 else f"over the last {self.days_span} days"
        n_total = len(self.affected_dishes) + self.uncosted_dish_count
        tail = f"{n_total} dish{'es' if n_total != 1 else ''} affected"
        if self.uncosted_dish_count:
            tail += f" ({self.uncosted_dish_count} not yet fully priced)"
        return f"{self.ingredient_name.title()} {sign}{pct:.0f}% {span} — {tail}"


def dish_ingredient_cost(bom_df: pd.DataFrame, prices: dict[str, float]) -> dict[str, float]:
    """Sum each dish's ingredient cost from the BOM using the given per-ingredient prices.

    Mirrors ``src/pricing/compute.py::plate_cost``'s formula
    (``qty_canonical / yield_factor * price``) over the seam's denormalized BomRow shape instead
    of the CLI's normalized pydantic models. A dish with any ingredient missing from ``prices`` is
    excluded entirely — a partial cost would understate the dish, which is worse than omitting it
    (the same "never a fabricated number" discipline as ``plate_cost``'s own missing-price
    ``ValueError``, just non-fatal here since this scans many dishes at once).

    A dish with a recipe line whose ``recipe_unit``/``canonical_unit`` don't share a measurement
    family (e.g. ``each`` -> ``g``) is excluded the same way: ``BomRow`` doesn't restrict units to
    the convertible set, so a typo'd or cross-family pair can reach the seam, and ``convert()``
    raises ``ValueError`` on it. Rather than letting that propagate and take down the whole
    surface (W3_review.md MAJOR-1: a bare 500 on ``GET /insights``), the dish degrades to "not
    costed" — the identical treatment as a missing price.
    """
    costs: dict[str, float] = {}
    for dish_id, group in bom_df.groupby("dish_id"):
        total = 0.0
        priced = True
        for _, row in group.iterrows():
            price = prices.get(row["ingredient_id"])
            if price is None:
                priced = False
                break
            try:
                qty_canonical = convert(row["qty"], row["recipe_unit"], row["canonical_unit"])
            except ValueError:
                priced = False
                break
            total += (qty_canonical / row["yield_factor"]) * price
        if priced:
            costs[dish_id] = total
    return costs


def build_opportunities(
    bom_df: pd.DataFrame, price_obs_df: pd.DataFrame, threshold: float = 0.10
) -> list[Opportunity]:
    """The "opportunities" surface: one entry per significant ingredient price move, each carrying
    the dishes it affects and the resulting ingredient-cost delta — plain-language, dollar-
    quantified, an action rather than a chart (``website_vision.md`` §3, group C).

    Ranked by total dollar impact across affected dishes (descending) so the biggest real finding
    surfaces first, not just the biggest percentage move.
    """
    if bom_df.empty or price_obs_df.empty:
        return []

    moves = significant_moves(price_trend(price_obs_df), threshold=threshold)
    if moves.empty:
        return []

    dish_names = bom_df.drop_duplicates("dish_id").set_index("dish_id")["dish_name"].to_dict()
    latest = latest_price_per_ingredient(price_obs_df)
    latest_price_map = dict(zip(latest["ingredient_id"], latest["unit_price"]))

    opportunities: list[Opportunity] = []
    for _, move in moves.iterrows():
        ingredient_id = move["ingredient_id"]
        affected_bom = bom_df[bom_df["ingredient_id"] == ingredient_id]
        if affected_bom.empty:
            continue  # this ingredient isn't used in any captured recipe yet

        affected_dish_ids = affected_bom["dish_id"].unique().tolist()
        relevant_bom = bom_df[bom_df["dish_id"].isin(affected_dish_ids)]

        # Hold every OTHER ingredient those dishes need at its latest known price (ceteris
        # paribus) so the cost delta isolates the effect of THIS ingredient's move; only the
        # moving ingredient itself uses the prior-vs-current price pair from `move`.
        other_ids = set(relevant_bom["ingredient_id"]) - {ingredient_id}
        base_prices = {oid: latest_price_map[oid] for oid in other_ids if oid in latest_price_map}
        prior_prices = {**base_prices, ingredient_id: move["prior_price"]}
        current_prices = {**base_prices, ingredient_id: move["current_price"]}

        prior_costs = dish_ingredient_cost(relevant_bom, prior_prices)
        new_costs = dish_ingredient_cost(relevant_bom, current_prices)

        affected = [
            AffectedDish(
                dish_name=dish_names[dish_id],
                prior_cost=prior_costs[dish_id],
                new_cost=new_costs[dish_id],
            )
            for dish_id in affected_dish_ids
            if dish_id in prior_costs and dish_id in new_costs
        ]
        if not affected:
            continue

        # Total dishes the BOM says use this ingredient, vs. how many of those we could actually
        # cost — the gap is dishes with a sibling ingredient missing a price or a non-convertible
        # unit (see dish_ingredient_cost). Reported, not silently dropped (W3_review.md MINOR-4).
        uncosted_dish_count = len(affected_dish_ids) - len(affected)
        days_span = (move["current_observed_date"] - move["prior_observed_date"]).days

        opportunities.append(Opportunity(
            ingredient_name=move["ingredient_name"],
            pct_change=move["pct_change"],
            direction=move["direction"],
            current_price=move["current_price"],
            prior_price=move["prior_price"],
            days_span=days_span,
            affected_dishes=sorted(affected, key=lambda d: abs(d.delta), reverse=True),
            uncosted_dish_count=uncosted_dish_count,
        ))

    return sorted(opportunities, key=lambda o: sum(abs(d.delta) for d in o.affected_dishes), reverse=True)
