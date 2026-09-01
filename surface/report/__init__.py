"""
report — Operator-Facing Output
================================
Assembles the outputs a chef or operator actually sees:

Phase 0
-------
- Menu-engineering grid: popularity × margin quadrant for each dish
  Columns: dish_name, plate_cost (rounded), menu_price, margin (rounded),
           margin_pct (binned), weekly_covers, quadrant_label
- Output: CSV or simple HTML table written to data/raw/ for the onboarding session

Phase 3
-------
- Price-alert digest: dishes affected by a price move, with old vs. new margin
- Always-current margin grid (same schema as Phase 0, recomputed on each invoice event)

Output discipline: no raw floats. Costs → nearest $0.25. Margin % → labeled tiers.
Nothing is streamed; everything is computed on demand when a new invoice lands.
"""
