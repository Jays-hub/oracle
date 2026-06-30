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

## Build phases

### Phase 0 — Static margin map *(the onboarding reveal)*
**Goal.** Walk into the chef sitdown and walk out having shown them real plate costs and a
menu-engineering grid, live in the room.

**Inputs.** One item-level POS sales export + recipe confirmation for ~15–25 items + seed prices
(chef's rough sense or a one-time invoice snapshot). No invoice pipeline yet.

**Build.** The BOM data structure; unit/yield reference seeded with approximate coefficients;
seed unit-price table; the plate-cost compute above; join to POS sales counts for the
**popularity × margin grid** (stars / plowhorses / puzzles / dogs). Lives in `src/bom/` and
`src/pricing/`.

**Hardest part.** Almost nothing technical — no OCR, no integration, no live anything. The work
is entering the BOM and getting approximate yields not-wrong. This is a weekend, not a quarter.

**Data captured for the engine.** The BOM + the sales export. Two of the four data legs the
forecasting engine needs, from one sitdown, zero ongoing burden.

> Phase 0 alone is a complete, demo-able tool. Everything after makes it *current* instead of
> *snapshot*.

---

### Phase 1 — Trustworthy conversion layer *(yield + units)*
**Goal.** Move from "roughly right" to "directionally trustworthy and defensible per dish."

**Build.** Real per-ingredient yield coefficients (raw → cooked/trimmed) from published culinary
tables + chef priors; proper pack → recipe-unit conversion; the as-purchased vs. as-used
distinction made explicit. Lives in `src/bom/` (yield coefficients) and `src/pricing/` (unit
conversion).

**Hardest part.** A data problem, not a code problem — curating yields and pack sizes. Culinary
domain knowledge is literally a model input here.

**Discipline — directional truth, never penny-accuracy.** Show rounded figures or ranges. False
precision ("$6.83" when the chef knows it's closer to seven) burns credibility on day one.

*(Phase 1 can be folded into Phase 0 if approximate yields are baked in from the start.)*

---

### ⛔ GATE — before building the invoice layer
Run the narrow competitive check: **is Toast / Square about to bundle plate-costing + price-
tracking natively, for free?** Square + MarketMan shipped recipe/inventory management in April
2026; the POS-absorption question is live. A few targeted product-name searches. If the value
about to be built is becoming a free POS default, *this implementation* of the on-ramp loses its
reason to be chosen — which is a signal to reshape the on-ramp, not to abandon the on-ramp function.
**This is the one place research earns its keep on this provisional tool, because Phase 2 is where
the cost is.**

---

### Phase 2 — Invoice ingestion *(the engineering wall)*
**Goal.** Turn the static snapshot into the always-current tool: prices update as invoices arrive.

**Build.** Invoice capture (photo + OCR, or digital vendor feed); price extraction; writing new
`PriceObservation`s while retaining history; **entity resolution** — matching messy vendor SKU
strings to recipe ingredients, with a confirmation queue and learned mappings. Lives in
`src/ingestion/`.

**Hardest part.** OCR is solvable; entity resolution across changing vendors / SKUs / pack-sizes
is where these tools feel janky. Budget for it. The confirmation queue (human-in-the-loop that
shrinks over time) is how you make the jank tolerable instead of trust-destroying.

**Data captured for the engine.** Ingredient purchase data — the invoice leg
`../../forecasting/src/decision/waste.py` uses to close the inventory identity
(`Purchased + StartInv − EndInv = TheoreticalDepletion + Loss`). Now three of the four data legs
captured.

---

### Phase 3 — Price monitoring and alerts *(the second hook)*
**Goal.** The tool tells the operator things without being asked.

**Build.** Per-ingredient trend detection (week-over-week vs. rolling N-week average); re-cost
propagation (a price change ripples to every dish containing that ingredient); alert logic
(*"beef +16% this week, 3 dishes affected, short rib now your thinnest-margin entrée"*); always-
current margin grid. Lives in `src/pricing/` and `src/report/`.

**Hardest part.** Trivial once Phase 2 works — mostly thresholds and presentation.

---

### Phase 4 — The handoff *(not a build — the strategic payoff)*
By Phase 3, the forecasting engine has silently received: months of item-level sales, the BOM for
the big items, and a flowing invoice/price history. The prep sheet becomes the next thing to *turn
on*, not a thing the operator *waits for*.

The one data leg this on-ramp does NOT capture: the 86 / stockout log (censored demand). That
stays a separate, deliberately tiny habit — the "tap the dish when it runs out → here's the
lost-sales dollar figure" tracker. Self-justifying for the same reason this tool is.

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
(globs → `onramp/**`). Build thin and phased; the durable parts (capture funnel, storage,
transparency) outlast the provisional plate-cost views. The compute in `src/` stays
framework-agnostic — a web layer must never become the only way to run a plate-cost.
