# CLAUDE.md — The On-Ramp (surface + measures + capture)

> **Scope after the 2026-08-14 layer restructure.** The on-ramp is no longer one directory. It is
> **`surface/` (L4, this directory) + `measures/` (L2) + `ingest/capture/` and `ingest/bom/` (L0)**,
> plus the layer-neutral `store/` and `db/`. This file governs all of it. The durable mandate for
> the on-ramp *function* is `../docs/onramp_service.md`; platform governance is `../CLAUDE.md`.

## What this module is
Plate-cost is the **current implementation** of the **on-ramp service** — a *durable, first-class*
part of the company governed by `../docs/onramp_service.md`. The on-ramp function (deliver instant, dollar-legible
value fast, and in the same act capture the data the forecasting engine needs) is **not disposable**;
it is the permanent acquisition + data-capture rail every operator must cross to reach the prep
engine. *Plate-cost is one bet on how to deliver that function.* It may be replaced, reshaped, or
renamed after customer discovery — so build **this product** thin and replaceable, while treating the
on-ramp role it serves as load-bearing and permanent.

Its job: deliver enough instant value (a real margin map) that an operator connects their POS and
sits for a one-time recipe confirmation — the single act that hands the forecasting engine its sales
history and BOM at once. The plate-cost product is the *means*; the prep-demand engine is the *end*;
the on-ramp *function* is the durable bridge between them.

Why plate-cost is the on-ramp's first implementation: the BOM it builds (`../ingest/bom/`) is the
same BOM the engine's ingredient close consumes. One recipe-confirmation act feeds two products.
That is the whole strategic reason this implementation was chosen first.

Durable on-ramp mandate: `../docs/onramp_service.md`. Full strategic context:
`../docs/strategic_context.md`. The common store both sides depend on: `../data/CONTRACT.md`.

## Scope boundary (non-negotiable)
- This file governs `surface/`, `measures/`, and `ingest/{capture,bom}/`. The durable on-ramp
  mandate lives in `../docs/onramp_service.md`; platform governance in `../CLAUDE.md`; engine rules
  in `../decide/CLAUDE.md` and `../.claude/rules/`. Do not duplicate those here.
- **The old "never import the engine" rule is now the general layer rule, machine-checked.**
  `../.importlinter` forbids these layers from importing `evaluate/` at all (`truth-firewall`) and
  forbids every upward import (`layer-direction`). `surface/` may import `measures/`, `ingest/`, and
  `identity/`; none of them may import it back.
- Data flows one way: `ingest/capture/` **writes** `../data/raw/`; `ingest/demand/` **reads** it for
  the engine. See `../data/CONTRACT.md`.
- Docs live in `../docs/onramp/`. Engine docs (`../docs/engine/`) are reference, not scope.
- These layers must never read the hidden oracle. That is `evaluate/`'s alone.

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

## Build phases (condensed — full detail in `../docs/onramp/purpose_and_phases.md`)
The per-phase walkthrough (goals, "hardest part," data legs, the pre-Phase-2 competitive gate) is
authoritative in `../docs/onramp/purpose_and_phases.md`. The standing summary:

| Phase | Builds | Data leg for the engine |
|------|--------|--------------------------|
| 0 | Static margin map from seed prices (`ingest/bom/`, `measures/pricing/`) — a complete, demo-able tool | BOM + POS sales export |
| 1 | Yield + unit-conversion hardening (directional truth, never penny-accuracy) | refines BOM, no new leg |
| ~~GATE~~ | **ANSWERED 2026-08-13, not pending.** The POS-absorption check is closed: Toast IQ shipped to all US Toast customers late 2025; MarginEdge sells this substrate at ~$350/mo to 11,000+ operators; ClearCOGS does item-level prep forecasting. See `../identity/__init__.py` and `../docs/consulting_framework.md` §7.8.1/§7.8.3. The answer reshapes the on-ramp (as the gate intended) rather than abandoning it. | — |
| 2 | Invoice ingestion + entity resolution (`../identity/`) — the engineering wall. **Re-scoped as the platform's L1 layer, phases R2–R6** (`../docs/real_data_readiness.md` §4); the spec lives in `../identity/__init__.py`. Blocked on R0/R1, not on the old gate. | invoice / purchase history |
| 3 | Price monitoring + alerts (`../measures/pricing/`, `report/`) | real-time updates, no new leg |
| 4 | Handoff — engine switches on (not a build) | — |

The one leg this on-ramp does **not** capture: the 86 / stockout log (censored demand) — a separate,
deliberately tiny habit.

## Discipline and drift callouts

1. **Thin, replaceable implementation — durable function.** Build *plate-cost* as thin as it can be
   while still delivering the hook and capturing its data leg; the product is a provisional bet and
   should never accrue weight the discovery process might throw away. What is *not* provisional is the
   on-ramp role it serves (`../docs/onramp_service.md`). Don't over-invest in this product; don't under-invest in
   the function.

2. **Directional truth, never penny-accuracy.** Rounded figures and ranges. A confidently-wrong
   plate cost loses the chef on day one.

3. **One sharp on-ramp at a time, not a Swiss-army scatter.** The on-ramp function is durable and
   first-class, but the *way to win it* is a single, sharp tool — not a fleet of half-built thin
   features. This implementation already captures three of the four data legs (sales, BOM, invoices)
   in one act. The chef's-knife principle applies to the ramp too.

4. ~~**The gate before Phase 2 is real.**~~ **Answered 2026-08-13 — see the phase table.** The
   research was done and it earned its keep: the substrate *is* being bundled and productized, which
   settles the question the gate asked. What replaces this callout: **identity (L1) is now the
   platform's critical path, not a deferred phase**, and the live open question is buy-vs-build for
   the matching stack — deferred to R0 on purpose, when real data makes the variance measurable
   (`../docs/real_data_readiness.md` §3).

7. **The sales leg this module captures cannot feed the engine, and never could.** `SalesExportRow`
   is one aggregate count over a date range (`../schemas/seam.py`) — right for the popularity axis
   of a margin grid, structurally unusable for a daily demand model. The "one recipe-confirmation act
   feeds two products" claim above holds for the **BOM leg only**. Fixing the grain is R1
   (`../docs/real_data_readiness.md` §2, blocker B2). Do not repeat the two-products claim without
   this qualifier.

5. **The drift trap, in its nastiest form.** This tool is more buildable and more gratifying than
   the forecasting moat and the data-access grind — which makes it a comfortable place to hide.
   If you find yourself three weeks deep in invoice-OCR edge cases before a single critical ratio
   is running on a gradient-boosted quantile model, you have quietly relocated yourself into the
   contested menu-analytics lane. The on-ramp is the means; the prep engine is the end.

6. **Standard caveat.** None of this validates the wedge. Discovery still has to prove that
   prep-level forecasting is unsaturated and wanted — and which on-ramp implementation operators
   actually cross. Build the on-ramp; let operators tell you whether to build the company.

## Module structure (the on-ramp's slice of the layer tree)
```
../docs/onramp_service.md   # the DURABLE on-ramp mandate (governs the function, not the product)
../docs/onramp/             # plate_cost_overview (index) -> purpose_and_phases · data_model
                            #   · seam_and_precision · website_vision (client-site north star)
../ingest/bom/              # L0.5  BOM data model, yield coefficients, loaders
../ingest/capture/          # L0    invoice capture, staging, the store write
../identity/                # L1    canonicalize.py · units.py (+ the R2-R6 ER spec)
../measures/                # L2    grid.py · pricing/ · costing/ · insights/
surface/CLAUDE.md           # this file - on-ramp governance
surface/web/                # L4    the operator site (FastAPI + templates)
surface/report/             # L4    terminal rendering of the popularity x margin grid
surface/{auth,email}/       # L4    app-facing identity + mail
surface/run.py              # L4    the Phase-0 CLI
../store/  ../db/           #       store paths (tenant isolation) · the app database
```
**Provisional vs. durable, made structural.** The plate-cost *views* are provisional and live in
`surface/`. The durable parts — capture, storage, identity, the transparency story — live in
`ingest/`, `store/`, `db/`, and `identity/`, **below** the layer that may be replaced. Replacing the
product means rewriting L4, not the capture rail. That was the intent all along; the layer split is
what makes it true of the directory tree rather than only of the prose.

## Stack
Python. pandas, pydantic (schema enforcement on BOM + price records — validate against the shared
schemas in `../schemas/`). **Storage: DuckDB-over-Parquet** — the decided shared store
(`../docs/common_base_reconciliation.md`); the `data/raw/**` files are the firewall, DuckDB is the
query layer over them. `store/` is layer-neutral and imports no layer (`.importlinter`'s `shared-modules-are-leaves`). Optional:
pytesseract / cloud OCR for Phase 2 invoice capture. No ML frameworks — this module has no models.

**Web stack (built W0–W3; production map approved).** A clean, simple website + a thin backend
over the pure `measures/` + `ingest/` compute, writing the store through `../schemas/`. Vision:
`../docs/onramp/website_vision.md`. **PoC → production execution map (W5–W10: designated app database, real
identity, hosting, the public face, seam tenancy): `../docs/onramp/website_production_overview.md`** (approved 2026-07-13 —
sanctioned on-ramp-function investment, not drift). Governance: the full-stack rules
`../.claude/rules/05–07` (paths → `surface/**`, `measures/**`). Build thin and phased; the durable parts
(capture funnel, storage, identity, transparency) outlast the provisional plate-cost views. The
compute in `measures/` and `ingest/` stays framework-agnostic — `.importlinter` guarantees it,
since neither may import `surface/`, so a web layer can never become the only way to run a
plate-cost. The application database is on-ramp-private (SQLite → Postgres via
`ONRAMP_DATABASE_URL`) and separate from the seam: user data never crosses into `data/raw/`.
