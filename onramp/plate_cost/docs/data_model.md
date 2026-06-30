# Plate-Cost: Data Model and Core Computation

**Part of the plate-cost docs.** Index: [plate_cost_overview.md](plate_cost_overview.md). Purpose +
phases: [purpose_and_phases.md](purpose_and_phases.md). The seam + precision discipline:
[seam_and_precision.md](seam_and_precision.md).

---

## The data model

Five entities. Everything else is derived.

```
Ingredient
  id              UUID
  name            str           canonical name (e.g. "beef short rib, bone-in")
  canonical_unit  str           the unit all recipe quantities and prices resolve to (e.g. "oz")
  yield_factor    float         raw-to-usable ratio (e.g. 0.70 for a 30% trim loss)
  notes           str | None    culinary notes (e.g. "bone-in; trim to ~70%; braise reduces ~25%")

VendorItem
  id              UUID
  raw_string      str           the messy vendor SKU as it appears on the invoice
  ingredient_id   UUID → Ingredient
  pack_size       float         e.g. 40.0
  pack_unit       str           e.g. "lb"
  vendor_name     str | None

PriceObservation
  id              UUID
  ingredient_id   UUID → Ingredient
  unit_price      float         price per canonical_unit, post-yield-factor
  source_invoice  str | None    invoice identifier or filename
  observed_date   date
  -- history is retained; latest_price(ingredient_id) = most recent by observed_date

Dish
  id              UUID
  name            str
  menu_price      float
  service_period  str | None    "lunch" | "dinner" | "brunch"
  is_active       bool

RecipeLine  (the BOM)
  dish_id         UUID → Dish
  ingredient_id   UUID → Ingredient
  qty             float         quantity in recipe_unit
  recipe_unit     str           unit as written in the recipe (e.g. "oz", "each", "cup")
```

> On-disk vs. in-memory: the seam file `data/raw/bom.csv` is a **denormalized** flattening of
> `RecipeLine` joined to `Dish` and `Ingredient` (so each row carries `dish_name`, `ingredient_name`,
> `canonical_unit`, `yield_factor`). The shapes that validate the seam writes live in
> `../../../schemas/seam.py` (`BomRow`, `SalesExportRow`).

---

## The core computation

```
plate_cost(dish) =
    Σ over RecipeLine where dish_id = dish.id:
        convert(qty, recipe_unit → canonical_unit) × latest_price(ingredient_id)

margin(dish)     = dish.menu_price − plate_cost(dish)
margin_pct(dish) = margin(dish) / dish.menu_price
```

Unit conversion (`recipe_unit → canonical_unit`) lives in `../src/bom/units.py`. Yield is baked into
`unit_price` at write time — `PriceObservation.unit_price` is already the as-used (post-trim) cost
per canonical unit, not the as-purchased cost.
