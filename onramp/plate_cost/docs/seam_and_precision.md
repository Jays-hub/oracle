# Plate-Cost: The Data Seam and Precision Discipline

**Part of the plate-cost docs.** Index: [plate_cost_overview.md](plate_cost_overview.md). Purpose +
phases: [purpose_and_phases.md](purpose_and_phases.md). Data model: [data_model.md](data_model.md).

---

## Data boundary with the forecasting engine

This module writes to `../../../data/raw/` as its output destination. Specifically:

- `../../../data/raw/bom.csv` (or `.parquet`) — the confirmed recipe-line table
- `../../../data/raw/sales_export.csv` — the POS sales history from the onboarding session
- `../../../data/raw/price_observations.csv` — the running invoice price log

The forecasting engine reads these files under the existing rule that models read only from
`data/raw/`. No special exception applies; this is the normal raw-data ingestion path.

This module must never read from `../../../data/_truth/` or import from `../../../forecasting/src/`.
The authoritative who-writes-what is `../../../data/CONTRACT.md`; the structural enforcement is the
cross-module boundary test at `../../../tests/test_module_boundaries.py`.

**Storage direction (decided 2026-06-25):** the shared store is **DuckDB-over-Parquet** — the
`data/raw/**` files are the durable, diffable, firewall-enforcing artifact; DuckDB is the query
layer over them. The decision record is `../../../docs/common_base_reconciliation.md`; standing up
the query layer is a gated build step (Comprehension Contract, `../../../.claude/rules/00-process.md`).

---

## Precision discipline

Plate costs are estimates bounded by yield assumptions and pack-size resolution. The tool must
never display false precision.

- Show costs rounded to the nearest $0.25 (or as a range: "$6.50–7.00") rather than "$6.83".
- On the margin grid, bin margin_pct into labeled tiers (e.g. "<20%", "20–35%", ">35%") rather
  than displaying raw percentages.
- A chef who knows their costs roughly and sees "$6.83" when it is closer to $7.00 will distrust
  every number on the sheet. Directional truth is robust to estimation error; false precision is not.

**Reconciliation rule (any surface that prints both cost and margin):** the displayed margin must be
computed from the *displayed (rounded) cost*, so `Menu − ~Cost = Margin` reconciles by eye. Showing a
rounded cost next to a margin derived from the unrounded cost is its own credibility leak — the chef
does the subtraction in their head and the numbers don't add up. (This discipline is enforced for the
on-ramp web surfaces in `../../../.claude/rules/06-frontend-ux.md`.)
