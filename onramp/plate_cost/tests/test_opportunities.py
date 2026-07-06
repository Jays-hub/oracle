"""Tests for src/insights/opportunities.py — the W3 "opportunities" surface.

Covers: dish_ingredient_cost's hand-computed correctness and its missing-price exclusion,
build_opportunities' end-to-end dollar-quantified findings (ranked by total impact), that an
ingredient move which touches no captured recipe is silently skipped (not an error), and that no
margin/tier claim ever appears (the seam carries no menu_price yet).
"""
import pandas as pd
import pytest

from src.insights import opportunities

_BOM = pd.DataFrame([
    {"dish_id": "short-rib", "dish_name": "Short Rib", "ingredient_id": "beef",
     "ingredient_name": "beef", "qty": 8.0, "recipe_unit": "oz", "canonical_unit": "oz",
     "yield_factor": 1.0},
    {"dish_id": "burger", "dish_name": "Burger", "ingredient_id": "beef",
     "ingredient_name": "beef", "qty": 4.0, "recipe_unit": "oz", "canonical_unit": "oz",
     "yield_factor": 1.0},
    {"dish_id": "salad", "dish_name": "Salad", "ingredient_id": "romaine",
     "ingredient_name": "romaine", "qty": 4.0, "recipe_unit": "oz", "canonical_unit": "oz",
     "yield_factor": 1.0},
])

_PRICES = pd.DataFrame([
    {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00,
     "source_invoice": "INV-1", "observed_date": "2026-06-01"},
    {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.48,
     "source_invoice": "INV-2", "observed_date": "2026-06-08"},
    {"ingredient_id": "romaine", "ingredient_name": "romaine", "unit_price": 1.00,
     "source_invoice": "INV-1", "observed_date": "2026-06-01"},
])


def test_dish_ingredient_cost_hand_computed():
    prices = {"beef": 3.00, "romaine": 1.00}
    costs = opportunities.dish_ingredient_cost(_BOM, prices)
    assert costs["short-rib"] == pytest.approx(24.00)  # 8oz * $3.00
    assert costs["burger"] == pytest.approx(12.00)     # 4oz * $3.00
    assert costs["salad"] == pytest.approx(4.00)        # 4oz * $1.00


def test_dish_ingredient_cost_applies_yield_factor():
    bom = pd.DataFrame([
        {"dish_id": "d", "dish_name": "D", "ingredient_id": "beef", "ingredient_name": "beef",
         "qty": 8.0, "recipe_unit": "oz", "canonical_unit": "oz", "yield_factor": 0.5},
    ])
    costs = opportunities.dish_ingredient_cost(bom, {"beef": 2.00})
    assert costs["d"] == pytest.approx(32.00)  # (8 / 0.5) * 2.00


def test_dish_ingredient_cost_excludes_dish_with_missing_price():
    """A dish referencing an unpriced ingredient must be dropped entirely, not partially costed."""
    costs = opportunities.dish_ingredient_cost(_BOM, {"beef": 3.00})  # no romaine price
    assert "salad" not in costs
    assert "short-rib" in costs and "burger" in costs


def test_dish_ingredient_cost_excludes_dish_with_unconvertible_units():
    """A recipe line whose recipe_unit/canonical_unit don't share a measurement family (e.g.
    each -> g) must degrade to "not costed", not raise and take down the whole surface
    (W3_review.md MAJOR-1: this ValueError used to propagate all the way to a bare 500)."""
    bom = pd.DataFrame([
        {"dish_id": "weird", "dish_name": "Weird Dish", "ingredient_id": "beef",
         "ingredient_name": "beef", "qty": 1.0, "recipe_unit": "each", "canonical_unit": "g",
         "yield_factor": 1.0},
    ])
    costs = opportunities.dish_ingredient_cost(bom, {"beef": 3.00})
    assert "weird" not in costs


def test_build_opportunities_end_to_end_dollar_quantified():
    result = opportunities.build_opportunities(_BOM, _PRICES, threshold=0.10)
    assert len(result) == 1
    opp = result[0]
    assert opp.ingredient_name == "beef"
    assert opp.direction == "up"
    assert opp.pct_change == pytest.approx(0.16, abs=1e-6)

    by_dish = {d.dish_name: d for d in opp.affected_dishes}
    assert set(by_dish) == {"Short Rib", "Burger"}
    # Short Rib uses 8oz beef: 8*3.00=24.00 -> 8*3.48=27.84, delta +3.84
    assert by_dish["Short Rib"].prior_cost == pytest.approx(24.00)
    assert by_dish["Short Rib"].new_cost == pytest.approx(27.84)
    assert by_dish["Short Rib"].delta == pytest.approx(3.84)
    # Ranked by |delta| descending: Short Rib (3.84) before Burger (1.92)
    assert opp.affected_dishes[0].dish_name == "Short Rib"


def test_build_opportunities_never_reports_margin_or_tier_fields():
    """The seam carries no menu_price — asserting the Opportunity/AffectedDish shape has no
    margin/tier attribute at all guards against ever fabricating one (rule 06)."""
    result = opportunities.build_opportunities(_BOM, _PRICES, threshold=0.10)
    opp = result[0]
    assert not hasattr(opp, "margin")
    assert not hasattr(opp, "food_cost_tier")
    for d in opp.affected_dishes:
        assert not hasattr(d, "margin")
        assert not hasattr(d, "food_cost_tier")


def test_build_opportunities_skips_ingredient_not_used_in_any_recipe():
    bom = pd.DataFrame([
        {"dish_id": "salad", "dish_name": "Salad", "ingredient_id": "romaine",
         "ingredient_name": "romaine", "qty": 4.0, "recipe_unit": "oz", "canonical_unit": "oz",
         "yield_factor": 1.0},
    ])
    result = opportunities.build_opportunities(bom, _PRICES, threshold=0.10)
    # beef moved 16% but no captured recipe uses it -> no opportunity for it
    assert all(o.ingredient_name != "beef" for o in result)


def test_build_opportunities_below_threshold_yields_nothing():
    flat_prices = pd.DataFrame([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00,
         "source_invoice": "INV-1", "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.05,
         "source_invoice": "INV-2", "observed_date": "2026-06-08"},
    ])
    result = opportunities.build_opportunities(_BOM, flat_prices, threshold=0.10)
    assert result == []


def test_opportunity_headline_format():
    """The exact plain-language shape website_vision.md §3 describes: "Beef +16% this week -> 3
    dishes affected" (here 2, since the fixture BOM has two beef dishes). The fixture's two price
    observations are exactly 7 days apart, so "this week" is not just hardcoded — it reflects the
    real days_span (W3_review.md MINOR-2)."""
    result = opportunities.build_opportunities(_BOM, _PRICES, threshold=0.10)
    assert result[0].days_span == 7
    assert result[0].headline == "Beef +16% this week — 2 dishes affected"


def test_opportunity_headline_shows_real_span_when_older_than_a_week():
    """A prior observation can be arbitrarily older than lookback_days (price_trend only requires
    AT LEAST 7 days earlier) — the headline must say so honestly instead of always claiming "this
    week" (W3_review.md MINOR-2: a 46-day-old prior was mislabeled "this week")."""
    prices = pd.DataFrame([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00,
         "source_invoice": "INV-1", "observed_date": "2026-04-23"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 4.20,
         "source_invoice": "INV-2", "observed_date": "2026-06-08"},
    ])
    result = opportunities.build_opportunities(_BOM, prices, threshold=0.10)
    assert result[0].days_span == 46
    assert "this week" not in result[0].headline
    assert "over the last 46 days" in result[0].headline


def test_opportunity_headline_notes_uncosted_dishes():
    """"N dishes affected" must count every dish the BOM says uses the moving ingredient, not just
    the subset we could fully cost — and must say so when the two counts differ (W3_review.md
    MINOR-4: a dish with an unpriced sibling ingredient used to vanish from the count silently)."""
    bom = pd.DataFrame([
        {"dish_id": "short-rib", "dish_name": "Short Rib", "ingredient_id": "beef",
         "ingredient_name": "beef", "qty": 8.0, "recipe_unit": "oz", "canonical_unit": "oz",
         "yield_factor": 1.0},
        {"dish_id": "stew", "dish_name": "Stew", "ingredient_id": "beef",
         "ingredient_name": "beef", "qty": 6.0, "recipe_unit": "oz", "canonical_unit": "oz",
         "yield_factor": 1.0},
        {"dish_id": "stew", "dish_name": "Stew", "ingredient_id": "carrot",
         "ingredient_name": "carrot", "qty": 2.0, "recipe_unit": "oz", "canonical_unit": "oz",
         "yield_factor": 1.0},
    ])
    prices = pd.DataFrame([
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00,
         "source_invoice": "INV-1", "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.48,
         "source_invoice": "INV-2", "observed_date": "2026-06-08"},
        # no observation for carrot -> Stew can't be fully costed
    ])
    result = opportunities.build_opportunities(bom, prices, threshold=0.10)
    assert len(result) == 1
    opp = result[0]
    assert opp.uncosted_dish_count == 1
    assert {d.dish_name for d in opp.affected_dishes} == {"Short Rib"}
    assert opp.headline == "Beef +16% this week — 2 dishes affected (1 not yet fully priced)"


def test_build_opportunities_empty_inputs():
    assert opportunities.build_opportunities(pd.DataFrame(), _PRICES) == []
    assert opportunities.build_opportunities(_BOM, pd.DataFrame()) == []
