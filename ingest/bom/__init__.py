"""
bom — Bill of Materials
=======================
Owns the five core entities (Ingredient, VendorItem, Dish, RecipeLine, PriceObservation),
yield coefficients, and recipe-unit → canonical-unit conversion.

Phase 0 deliverables
--------------------
- Data structures / schema for all five entities
- Seed loader: read a recipe-confirmation spreadsheet into RecipeLine + Ingredient rows
- Unit conversion table: recipe_unit → canonical_unit multipliers
- Yield reference: per-ingredient yield_factor (approximate at Phase 0, refined at Phase 1)

Phase 1 additions
-----------------
- Curated yield coefficients from culinary tables + chef priors
- Pack → recipe-unit conversion chain (as-purchased → as-used)
- Validation: flag any RecipeLine where recipe_unit has no known conversion path
"""
