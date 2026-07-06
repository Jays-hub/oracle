# data/ — The Common Store: Seam Contract

`data/` is the **single interface between the two code peers** (`../forecasting/` and `../onramp/`).
It is platform infrastructure **owned by neither peer**. This file is the *authoritative* statement
of who writes what, who reads what, and the law that keeps the firewall intact. Where any
`CLAUDE.md` or doc describes the boundary, it must defer to this file rather than restate it.

> For the *evolution* of this store toward a queryable common database (DuckDB over Parquet) and what
> that does to the firewall, see `../docs/common_base_reconciliation.md`. This file describes the
> store **as it is contracted today**; that file is the **forward plan**.

## The layers

| Layer | Owner (writer) | Allowed readers | Purpose |
|---|---|---|---|
| `data/raw/` | `onramp/` (its data legs) + `forecasting/src/simulate/` (synthetic dump) | `forecasting/src/data/` (and anything downstream of it) | The messy "restaurant export." **The only thing models may read.** |
| `data/interim/` | `forecasting/src/data/` | engine only | Cleaned signal (pollution stripped, eras tagged). |
| `data/processed/` | `forecasting/src/features/` | engine only | Model-ready feature matrices. |
| `data/_truth/` | **only** `forecasting/src/simulate/` | **only** `forecasting/src/evaluate/` | Hidden ground truth. **Scoring only. Never a model input. Never touched by `onramp/`.** |

## The law (non-negotiable — mirrors `.claude/rules/01-data-ingestion.md`)

1. **Models read only `data/raw/`.** Enforced by a runtime path assertion at the top of every
   data-loading module, and by an import-boundary test in CI.
2. **Single funnel for the oracle.** Exactly one module *reads* `data/_truth/` —
   `forecasting/src/evaluate/` — and only `forecasting/src/simulate/` *writes* it. No other module
   opens a `_truth/` path or imports the truth loader.
3. **One-way data flow, no code coupling.** `onramp/` → `data/raw/` → `forecasting/`. Neither peer
   imports the other. The seam is the *only* coupling.
4. **`onramp/` never reads `data/_truth/`** and never reads the engine's `interim/`/`processed/`.

## What the on-ramp writes to `data/raw/` (its captured data legs)

The current on-ramp implementation (`onramp/plate_cost/`) writes three of the engine's four data
legs. Files (`.csv` or `.parquet`):

| File | Leg | Written when |
|---|---|---|
| `sales_export.csv` (a.k.a. `pos_sales.*`) | **sales history** | onboarding (POS export) → later POS feed |
| `bom.csv` (RecipeLine rows) | **BOM** | the one-time recipe sitdown |
| `price_observations.csv` | **invoice / price history** | **built (W3, 2026-07-05)** — a digital-feed CSV upload (`src/capture/invoice_upload.py`); each confirmed invoice APPENDS rows (never a full replace, unlike the other two legs), so history accumulates |

The **fourth** leg — `eightysix_log.csv` (the 86/stockout log, the censored-demand signal) — is
**not** captured by the on-ramp. It is a separate, deliberately tiny habit (tap a dish when it 86s).
It still lands in `data/raw/` for the engine to read; it just has a different capture surface.

A future on-ramp product that replaces plate-cost inherits this contract: whatever it is, it writes
its captured legs to `data/raw/` in the agreed schema and touches nothing else.

## Schemas

The column-level schemas for these files are specified in `../forecasting/docs/simulated_data.md` (the
generator's view) and enforced in code by the shared definitions in `../schemas/`. When a real
export replaces the simulated one, the `../schemas/` definitions are the validation gate at ingestion.

## Forward notes (deferred design — gated when built)

Recorded decisions about future seam evolution, not yet built. Each clears the Comprehension
Contract (`.claude/rules/00-process.md`) when it lands.

- **Co provenance — a derived food-cost leg (review issue #3). Still NOT built, even after W3.**
  Today the engine's overage cost `Co` (the food cost of a wasted portion) is hand-entered in
  `config/items.yaml` as a simulation placeholder. `Co` *is* the plate cost the on-ramp already
  computes — but the seam still carries **no menu prices**: W3 (2026-07-05) added ingredient unit
  prices (`price_observations.csv`, above), yet `bom.parquet` still has only quantities/yields/units
  and `sales_export.parquet` only counts — no dish's *menu price* crosses the seam anywhere, so the
  engine **still cannot reconstruct a plate cost (let alone a margin) from `data/raw/` today**. This
  is why W3's own `/insights` opportunities surface reports an ingredient-cost delta only, never a
  margin or food-cost-tier claim (`docs/phase_decisions/W3.md`). **Decision (unchanged):** when real
  tenant data flows, the on-ramp writes its computed per-dish food cost as a new **derived seam leg**
  (a `food_cost` column or file under `data/raw/`), so `Co` flows *from the on-ramp's computation*
  and is never re-typed — one source of truth, consistent with "one recipe-confirmation act feeds
  two products." This adds a `../schemas/` definition and a row to the legs table above; it is a
  gated step, still deferred to a later on-ramp phase (menu-price capture hasn't been built either).
  Until then, `config/items.yaml` `Co` is an honestly-labeled placeholder, not a second source of
  truth to reconcile.

- **Stable `item_id` across the seam (review issue #4, durable fix).** The only key shared by
  `config/items.yaml` and `data/raw/` today is the display name (`name` ↔ `dish_name`) — a
  name-based join, the fragile pattern `onramp/`'s `normalize_name()` exists to defend. The
  near-term guard lives in the engine's P2 ingestion (see `../forecasting/docs/construction_roadmap.md`
  Phase 2: reconcile config names against the seam, fail loud on drift). The durable fix is to carry
  a stable `item_id` across the seam so the join is never name-based; that is a seam-contract change
  recorded here for when it's built.

- **Physical multi-tenant partitioning of `data/raw/` (W2, not built).** `data/raw/` remains a flat,
  unpartitioned directory (one implicit tenant) after the on-ramp's W2 "account + persistence" phase.
  W2 added session-based login gating the web app's data-bearing routes, but the on-disk seam layout
  is unchanged — no `restaurant_id` column in `schemas/seam.py`, no per-tenant subdirectory. This
  matches `.claude/rules/05-fullstack-architecture.md`'s "essentially single-tenant tool" framing and
  `onramp/plate_cost/docs/website_vision.md` §9 ("not a mandate to build a multi-tenant platform
  now") — there is exactly one tenant's data in the store today, so isolation is enforced at the auth
  layer (every data route requires a valid session), not by partitioning files that would also
  require a coordinated change to `forecasting/src/data/loader.py` and `forecasting/src/simulate/
  generator.py` (both hard-code a flat `data/raw/`). **Decision, deferred:** when a second real
  tenant's data needs to coexist, add a `restaurant_id` to the seam (either a column on `BomRow`/
  `SalesExportRow` or a per-tenant subdirectory under `data/raw/`) as a gated seam-contract change
  touching both peers — not a unilateral on-ramp-side change. See `docs/phase_decisions/W2.md`.

## Enforcement status

- **DuckDB-over-Parquet query layer: BUILT (2026-06-25).** The `data/raw/` files are now Parquet
  (`bom.parquet`, `sales_export.parquet`). The on-ramp owns a thin store helper
  (`onramp/plate_cost/src/store.py`) that opens only `data/raw/**` — structurally incapable of
  opening any other layer. `docs/common_base_reconciliation.md` Option 3 is live.
- The **runtime path assertion** and **import-boundary test** are specified in
  `.claude/rules/01-data-ingestion.md` and land when the first ingestion / simulate code is written
  (Phase 1).
- The **cross-module boundary test** now exists at `tests/test_module_boundaries.py` (it asserts
  `onramp/` never imports `forecasting/`, `forecasting/` never imports `onramp/`, and `onramp/`
  never references a `_truth` path). It is a **static AST + text scan, deliberately dependency-free**
  for now.
  - **Switch trigger (for engine development):** when these boundary rules proliferate — notably once
    the engine lands and `.claude/rules/01-data-ingestion.md`'s engine-**internal** import-boundary
    (nothing under `forecasting/src/{data,features,models,decision,report}` imports the truth loader)
    also needs enforcing — migrate the hand-rolled static scan to **import-linter** (already named in
    rule `01`). Until that volume arrives, the static scan is the thinner, dependency-free choice.
