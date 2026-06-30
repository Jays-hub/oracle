# CLAUDE.md — Plate-Cost (current implementation of the on-ramp service)

## What this module is
Plate-cost is the **current implementation** of the **on-ramp service** — a *durable, first-class*
part of the company governed by `../README.md`. The on-ramp function (deliver instant, dollar-legible
value fast, and in the same act capture the data the forecasting engine needs) is **not disposable**;
it is the permanent acquisition + data-capture rail every operator must cross to reach the prep
engine. *Plate-cost is one bet on how to deliver that function.* It may be replaced, reshaped, or
renamed after customer discovery — so build **this product** thin and replaceable, while treating the
on-ramp role it serves as load-bearing and permanent.

Its job: deliver enough instant value (a real margin map) that an operator connects their POS and
sits for a one-time recipe confirmation — the single act that hands the forecasting engine its sales
history and BOM at once. The plate-cost product is the *means*; the prep-demand engine is the *end*;
the on-ramp *function* is the durable bridge between them.

Why plate-cost is the on-ramp's first implementation: the BOM it builds is the same BOM
`../../forecasting/src/decision/ingredients.py` consumes. One recipe-confirmation act feeds two
products. That is the whole strategic reason this implementation was chosen first.

Durable on-ramp mandate: `../README.md`. Full strategic context: `../../docs/strategic_context.md`.
The shared data seam both products depend on: `../../data/CONTRACT.md`.

## Scope boundary (non-negotiable)
- This module governs `onramp/plate_cost/` only. The durable on-ramp mandate lives in `../README.md`;
  platform-level governance in `../../CLAUDE.md`; forecasting-engine rules in
  `../../forecasting/CLAUDE.md` and `../../.claude/rules/`. Do not import or duplicate those here.
- Source code lives in `onramp/plate_cost/src/`. It must **never** import from
  `../../forecasting/src/` (the engine). Data flows one way, through the shared seam: this module
  **writes** to `../../data/raw/`; the forecasting engine **reads** from there. See
  `../../data/CONTRACT.md`.
- Docs live in `onramp/plate_cost/docs/`. Forecasting docs (`../../docs/`) are reference, not scope.
- This module must never read from `../../data/_truth/`.

## The core mechanic
A plate cost has two inputs: the **recipe** (static — confirmed once, drifts only on
reformulation) and the **ingredient unit prices** (dynamic — move when an invoice arrives, ~weekly).
The tool is **event-driven on invoices**: a new price silently re-costs every affected dish and
recomputes every margin, with zero manual recalculation. Always current, never streaming.

```
Ingredient:        id, name, canonical_unit, yield_factor
VendorItem:        raw_invoice_string, ingredient_id (resolved), pack_size, pack_unit
PriceObservation:  ingredient_id, unit_price, source_invoice, date    -- history retained
Dish:              id, name, menu_price
Recipe (BOM):      dish_id -> [ (ingredient_id, qty, recipe_unit), ... ]

plate_cost(dish) = Σ over BOM[dish] of
                     qty_in_canonical_units × latest_price(ingredient) / yield_factor
margin(dish)     = menu_price − plate_cost(dish)
margin_pct(dish) = margin(dish) / menu_price
```

## Build phases (condensed — full detail in `docs/purpose_and_phases.md`)
The per-phase walkthrough (goals, "hardest part," data legs, the pre-Phase-2 competitive gate) is
authoritative in `docs/purpose_and_phases.md`. The standing summary:

| Phase | Builds | Data leg for the engine |
|------|--------|--------------------------|
| 0 | Static margin map from seed prices (`src/bom/`, `src/pricing/`) — a complete, demo-able tool | BOM + POS sales export |
| 1 | Yield + unit-conversion hardening (directional truth, never penny-accuracy) | refines BOM, no new leg |
| **GATE** | **POS-absorption check before the invoice spend** — is Toast/Square about to bundle this for free? Reshape the on-ramp, don't abandon the function. | — |
| 2 | Invoice ingestion + entity resolution (`src/ingestion/`) — the engineering wall | invoice / purchase history |
| 3 | Price monitoring + alerts (`src/pricing/`, `src/report/`) | real-time updates, no new leg |
| 4 | Handoff — engine switches on (not a build) | — |

The one leg this on-ramp does **not** capture: the 86 / stockout log (censored demand) — a separate,
deliberately tiny habit.

## Discipline and drift callouts

1. **Thin, replaceable implementation — durable function.** Build *plate-cost* as thin as it can be
   while still delivering the hook and capturing its data leg; the product is a provisional bet and
   should never accrue weight the discovery process might throw away. What is *not* provisional is the
   on-ramp role it serves (`../README.md`). Don't over-invest in this product; don't under-invest in
   the function.

2. **Directional truth, never penny-accuracy.** Rounded figures and ranges. A confidently-wrong
   plate cost loses the chef on day one.

3. **One sharp on-ramp at a time, not a Swiss-army scatter.** The on-ramp function is durable and
   first-class, but the *way to win it* is a single, sharp tool — not a fleet of half-built thin
   features. This implementation already captures three of the four data legs (sales, BOM, invoices)
   in one act. The chef's-knife principle applies to the ramp too.

4. **The gate before Phase 2 is real.** Do the POS-absorption check before spending the
   engineering. It is the one piece of research that earns its keep here.

5. **The drift trap, in its nastiest form.** This tool is more buildable and more gratifying than
   the forecasting moat and the data-access grind — which makes it a comfortable place to hide.
   If you find yourself three weeks deep in invoice-OCR edge cases before a single critical ratio
   is running on a gradient-boosted quantile model, you have quietly relocated yourself into the
   contested menu-analytics lane. The on-ramp is the means; the prep engine is the end.

6. **Standard caveat.** None of this validates the wedge. Discovery still has to prove that
   prep-level forecasting is unsaturated and wanted — and which on-ramp implementation operators
   actually cross. Build the on-ramp; let operators tell you whether to build the company.

## Module structure
```
onramp/
├── README.md                  # the DURABLE on-ramp mandate (governs the function, not the product)
└── plate_cost/                # this implementation (provisional — may change after discovery)
    ├── CLAUDE.md              # this file — all plate-cost governance lives here
    ├── docs/                  # plate_cost_overview (index) → purpose_and_phases · data_model
    │                          #   · seam_and_precision · website_vision (client-site north star)
    └── src/
        ├── bom/               # BOM data model, yield coefficients, unit conversion
        ├── pricing/           # PriceObservation, plate-cost compute, margin grid, alerts
        ├── ingestion/         # invoice capture, OCR, entity resolution, confirmation queue
        └── report/            # popularity × margin grid output, operator-facing views
```

## Stack
Python. pandas, pydantic (schema enforcement on BOM + price records — validate against the shared
schemas in `../../schemas/`). **Storage: DuckDB-over-Parquet** — the decided shared store
(`../../docs/common_base_reconciliation.md`); the `data/raw/**` files are the firewall, DuckDB is the
query layer over them. The on-ramp owns its own store helper (no import of the engine). Optional:
pytesseract / cloud OCR for Phase 2 invoice capture. No ML frameworks — this module has no models.

**Web stack (planned — the on-ramp's client-facing face).** A clean, simple website + a thin backend
over the pure `src/` compute, writing the seam through `../../schemas/`. Vision:
`docs/website_vision.md`. Governance: the full-stack rules `../../.claude/rules/05–07`
(paths → `onramp/**`). Build thin and phased; the durable parts (capture funnel, storage,
transparency) outlast the provisional plate-cost views. The compute in `src/` stays
framework-agnostic — a web layer must never become the only way to run a plate-cost.
