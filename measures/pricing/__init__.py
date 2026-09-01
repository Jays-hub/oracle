"""
pricing — Plate-Cost Compute, Price History, and Alerts
========================================================
Owns PriceObservation writes/reads, the plate-cost computation, the margin grid,
and (Phase 3) price-trend detection and re-cost propagation.

Phase 0 deliverables
--------------------
- Seed price loader: write initial PriceObservation rows from a one-time snapshot
- latest_price(ingredient_id): return most recent unit_price by observed_date
- plate_cost(dish_id): Σ BOM qty × latest_price / yield_factor
- margin(dish_id) and margin_pct(dish_id)
- Menu-engineering grid: join to POS sales counts → popularity × margin quadrant labels
  (star / plowhorse / puzzle / dog)

Phase 3 additions
-----------------
- Trend detection: week-over-week and vs. rolling N-week average per ingredient
- Re-cost propagation: on new PriceObservation, recompute all affected dishes
- Alert logic: surface dishes where margin crosses a threshold or ingredient cost spikes
- Precision discipline: all outputs rounded to nearest $0.25 or expressed as ranges

Precision rule (non-negotiable): never output raw float costs. Round or bin before display.
See plate_cost/docs/plate_cost_overview.md § "Precision discipline".
"""
