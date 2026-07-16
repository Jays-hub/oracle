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
| `data/raw/<restaurant_id>/` | `onramp/` (its data legs) + `forecasting/src/simulate/` (synthetic dump) | `forecasting/src/data/` (and anything downstream of it) | The messy "restaurant export," one subdirectory per tenant (W9). **The only thing models may read.** |
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

The current on-ramp implementation (`onramp/plate_cost/`) writes four of the engine's data legs,
plus one derived leg, into its own tenant's subdirectory (`data/raw/<restaurant_id>/`, W9). Files
(`.csv` or `.parquet`), paths below relative to that subdirectory:

| File | Leg | Written when |
|---|---|---|
| `sales_export.csv` (a.k.a. `pos_sales.*`) | **sales history** | onboarding (POS export) → later POS feed |
| `bom.csv` (RecipeLine rows) | **BOM** | the one-time recipe sitdown |
| `price_observations.csv` | **invoice / price history** | **built (W3, 2026-07-05)** — a digital-feed CSV upload (`src/capture/invoice_upload.py`); each confirmed invoice APPENDS rows (never a full replace, unlike the other two legs), so history accumulates |
| `food_cost.csv` | **derived per-dish ingredient cost (`Co`)** | **built (W6, 2026-07-14)** — recomputed from the BOM + latest prices and written full-replace (a current snapshot, not a history) whenever the operator saves a menu price or confirms a new invoice (`src/costing/tenant_grid.py`); see "Co provenance" below |

The **fifth** leg — `eightysix_log.csv` (the 86/stockout log, the censored-demand signal) — is
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

- **Co provenance — a derived food-cost leg (review issue #3). Built (W6, 2026-07-14).**
  `food_cost.csv` (above) is now written: `schemas/seam.py::FoodCostRow` (`dish_id`, `dish_name`,
  `food_cost`, `computed_at`), recomputed from `bom.parquet` + the latest `price_observations.parquet`
  price per ingredient (`src/costing/tenant_grid.py::build_food_cost_rows`) and written full-replace
  whenever the operator saves a menu price (`src/costing/menu_prices.py` — "one recipe-confirmation
  act feeds two products," now also true of "one menu-price save") **or confirms a new invoice**
  (`web/app.py::invoice_confirm_submit`, added post-review — a price-only invoice upload changes
  `Co` too, and the leg must not go stale until the next unrelated menu-price save;
  `web/menu_prices.py::recompute_and_write_food_cost` is the one recompute path both actions share).
  It deliberately carries no `menu_price` itself — that stays app-DB-only catalog data
  (`onramp/plate_cost/docs/website_production_overview.md` §3's two-store laws) — and the cost math
  never needed `menu_price` in the first place. **Not yet wired into the engine**:
  `config/items.yaml` `Co` is still a hand-typed placeholder until a `forecasting/` phase reads this
  leg instead — that consuming change is out of this on-ramp phase's scope and remains open.

- **Stable `item_id` across the seam (review issue #4, durable fix).** The only key shared by
  `config/items.yaml` and `data/raw/` today is the display name (`name` ↔ `dish_name`) — a
  name-based join, the fragile pattern `onramp/`'s `normalize_name()` exists to defend. The
  near-term guard lives in the engine's P2 ingestion (see `../forecasting/docs/construction_roadmap.md`
  Phase 2: reconcile config names against the seam, fail loud on drift). The durable fix is to carry
  a stable `item_id` across the seam so the join is never name-based; that is a seam-contract change
  recorded here for when it's built.

- **Physical multi-tenant partitioning of `data/raw/` — BUILT (W9, 2026-07-16), speculatively.**
  `data/raw/` is no longer a flat file store; it is a container of one subdirectory per tenant:
  `data/raw/<restaurant_id>/{bom,sales_export,price_observations,food_cost}.parquet` (the on-ramp's
  legs) and `data/raw/<restaurant_id>/{pos_sales,reservations,invoices,recipes_stated,
  weather_actuals,weather_forecast,events,eightysix_log}.csv` (the simulator's synthetic dump) —
  chosen over a `restaurant_id` column (W2's other weighed option, `docs/phase_decisions/W2.md`)
  because every existing writer already has full-replace or lock-guarded-accumulate semantics keyed
  to "this file is my tenant's snapshot"; a column would have silently broken that (a full-replace
  write would delete every OTHER tenant's rows from the same file) and required re-architecting
  every writer's concurrency story, where a subdirectory needs only one more path segment. `data/
  _truth/` is explicitly **not** partitioned by this decision — it is scoring-internal to
  `forecasting/`, not part of the seam this file governs, and today there is never more than one
  simulated dataset's truth in existence at a time. If a second tenant is ever actually simulated for
  a real dollar-floor comparison, `_truth/` will need the same treatment; flagged here, not built.
  - **`restaurant_id` is always the app-DB's `Restaurant.id`** (`onramp/plate_cost/src/db/models.py`,
    a `uuid.uuid4().hex` string) reused as the directory name — no second id scheme invented (mirrors
    the `dish_id`/`ingredient_id` `normalize_name()` precedent).
  - **Path-safety:** `onramp/plate_cost/src/store.py::tenant_raw_dir()` validates any caller-supplied
    `restaurant_id` against a path-safe-slug pattern (`^[A-Za-z0-9_-]{1,64}$` — alphanumerics, `-`,
    `_` only; rejects `.`, `/`, `\`, null bytes, empty string) before it ever reaches a filesystem
    path, since it is the one place across both peers where a variable, request-derived string
    becomes a path segment. `forecasting/` has no equivalent caller-supplied path today — the only
    tenant id it ever resolves is the fixed sentinel below — so it carries no matching validator;
    noted as a deliberate, scoped omission, not an oversight, in `docs/phase_decisions/W9.md`.
  - **The shared pre-tenancy sentinel:** the literal 32-character nil-UUID hex string
    `"00000000000000000000000000000000"` (`uuid.UUID(int=0).hex`) names the one demo/simulation
    bucket neither the on-ramp's static CLI (`onramp/plate_cost/src/run.py`) nor the forecasting
    engine's dollar-floor scripts (`forecasting/src/evaluate/*.py`, via `forecasting/src/data/
    loader.py::SIMULATED_RESTAURANT_ID` and `forecasting/src/simulate/generator.py`'s own copy) have
    a real signup-issued tenant id for. Both peers hardcode this identical literal independently —
    no shared import crosses the peer boundary for it — so this file is the place to diff each
    peer's copy against.
  - **The runtime whitelist guard moved one level deeper.** `forecasting/src/data/{loader,cleaner}
    .py::_assert_raw_only` now requires the path's *parent* (not the path itself) to be literally
    named `raw` — the same whitelist-beats-blacklist posture as before, just one path segment lower,
    since callers now pass a specific tenant's subdirectory, not the flat store.
  - **Speculative, not trigger-fired.** No second real tenant exists yet (`website_production_
    overview.md` §4 names that trigger); this was built ahead of it, at Jay's explicit direction, as
    forward infrastructure. The subdirectory shape is a considered guess, not a validated one —
    revisit if a real second tenant's actual needs contradict it. Full reasoning: `docs/
    phase_decisions/W9.md`.

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
