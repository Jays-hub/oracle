# Plate-Cost: Purpose, Position, and Phase Map

**Part of the plate-cost docs.** Index: [plate_cost_overview.md](plate_cost_overview.md). Data model:
[data_model.md](data_model.md). The seam + precision discipline: [seam_and_precision.md](seam_and_precision.md).

> **Authoritative phase detail.** This doc is the home of the full per-phase build walkthrough. The
> always-on `../CLAUDE.md` carries only the condensed phase map + governance; it points here for detail.

---

## Purpose and position in the product stack

The plate-cost tool is the **current implementation of the on-ramp service** — the first concrete
bet on a *durable* company function (instant value + data capture in one act), governed by
`../../README.md`. It delivers instant value — a real margin map, live in the chef sitdown — in
exchange for two things the forecasting engine needs: a sales export and a confirmed BOM. The tool
is a capture mechanism first, a product second; the on-ramp *function* outlives whatever product
implements it, so build this product thin and replaceable.

Its strategic logic rests on a single insight: the BOM that powers plate-cost computation is the
same BOM `../../../forecasting/src/decision/ingredients.py` consumes for ingredient-level demand. One
recipe-confirmation session, zero duplicated asks.

---

## Phase map and data legs captured

| Phase | What it builds | Data leg captured for the forecasting engine |
|-------|---------------|----------------------------------------------|
| 0 | Static margin map from seed prices | BOM + POS sales export |
| 1 | Yield + unit conversion hardening | (refines BOM quality, no new leg) |
| GATE | POS-absorption competitive check | — |
| 2 | Invoice ingestion + entity resolution | Invoice / purchase history |
| 3 | Price monitoring + alerts | (real-time updates, no new leg) |
| 4 | Handoff | Forecasting engine switches on |

The one data leg NOT captured here: the 86 / stockout log. That is a separate, deliberately minimal
habit (tap a dish when it runs out → lost-sales dollar figure).

---

## Full per-phase build detail

### Phase 0 — Static margin map *(the onboarding reveal)*
**Goal.** Walk into the chef sitdown and walk out having shown them real plate costs and a
menu-engineering grid, live in the room.

**Inputs.** One item-level POS sales export + recipe confirmation for ~15–25 items + seed prices
(chef's rough sense or a one-time invoice snapshot). No invoice pipeline yet.

**Build.** The BOM data structure; unit/yield reference seeded with approximate coefficients;
seed unit-price table; the plate-cost compute; join to POS sales counts for the
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
`../../../forecasting/src/decision/waste.py` uses to close the inventory identity
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
