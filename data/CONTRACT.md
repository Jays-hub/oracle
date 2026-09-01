# data/ — The Common Store: Seam Contract

`data/` is the **common store**: the single interface between the layers of the code tree
(`../ingest/`, `../identity/`, `../measures/`, `../decide/`, `../surface/`). It is platform
infrastructure **owned by no layer**. This file is the *authoritative* statement of who writes what,
who reads what, and the law that keeps the firewall intact. Where any `CLAUDE.md` or doc describes
the boundary, it must defer to this file rather than restate it.

> **Layer restructure (2026-08-14).** The two-peer split (`forecasting/` + `onramp/`) is gone; code
> is organized by layer per `../docs/repo_architecture.md` §5.3/§6, and the store gained the
> `resolved/` layer the pivot needs. The paths below are the new ones; the *law* is unchanged. The
> old peer names survive only in the historical record (`../docs/phase_decisions/`,
> `../docs/progress_log.md`), which is deliberately not rewritten.

> For the *evolution* of this store toward a queryable common database (DuckDB over Parquet) and what
> that does to the firewall, see `../docs/common_base_reconciliation.md`. This file describes the
> store **as it is contracted today**; that file is the **forward plan**.

## The layers

| Layer | Owner (writer) | Allowed readers | Purpose |
|---|---|---|---|
| `data/raw/<restaurant_id>/` | `ingest/capture/` (the captured legs) + `ingest/simulate/` (synthetic dump) | `ingest/demand/` (and anything downstream of it) | The messy "restaurant export," as received, one subdirectory per tenant (W9). **The only thing models may read.** |
| `data/canonical/` | `ingest/demand/` | any layer | Adapter output: schema-conformed, pollution stripped, eras tagged. (Was `data/interim/`.) |
| `data/resolved/` | `identity/` | any layer | **New with the pivot.** Post-ER rows with entity ids assigned. Nothing produces this yet — it lands with R2. |
| `data/marts/` | `decide/features/`, `measures/` | any layer | Features and derived measures. (Was `data/processed/`.) |
| `data/runs/` | any layer, through the run recorder | any layer | One immutable directory per execution: manifest (code version, input snapshot, config hash, timestamp) + outputs. **Not built yet — M2.** |
| `data/_truth/` | **only** `ingest/simulate/` | **only** `evaluate/` | Hidden ground truth. **Scoring only. Never a model input. Never read by any layer in the dependency chain.** |

`raw → canonical → resolved → marts` is the flow. `resolved/` is the one layer the 2026-08-13 pivot
adds, and the reason the store needed reshaping at all (`../docs/repo_architecture.md` §6).

**Deferred on purpose (M4, `../docs/repo_architecture.md` §7):** Hive-style partition directories
(`restaurant_id=<id>/source=<vendor>/dt=<date>/`) are *not* built. The trigger is a **second real
tenant**, and at n=0 real tenants the rename buys nothing. `tenant_raw_dir()` keeps writing
`data/raw/<restaurant_id>/`, which is the same information one rename away.

## The law (non-negotiable — mirrors `.claude/rules/01-data-ingestion.md`)

1. **Models read only `data/raw/`.** Enforced by a runtime path assertion at the top of every
   data-loading module, and by the import contracts in CI.
2. **Single funnel for the oracle.** Exactly one package *reads* `data/_truth/` — `evaluate/` — and
   only `ingest/simulate/` *writes* it. No other module opens a `_truth/` path or imports the truth
   loader. Enforced two ways: `.importlinter`'s `truth-firewall` contract (import graph) and
   `tests/platform/test_module_boundaries.py` (text scan for the literal path).
3. **One-way data flow.** Capture writes the store; decision layers read it. `ingest/capture/` →
   `data/raw/` → `ingest/demand/` → `decide/`. The store is the coupling; the layer contract in
   `.importlinter` is what keeps the code arrows pointing the same way.
4. **No layer in the dependency chain touches `data/_truth/`** — not `ingest/` (outside
   `simulate/`), not `identity/`, `measures/`, `decide/`, or `surface/`.

## What the on-ramp writes to `data/raw/` (its captured data legs)

The current on-ramp implementation (`surface/` + `measures/` (the former on-ramp)) writes four of the engine's data legs,
plus one derived leg, into its own tenant's subdirectory (`data/raw/<restaurant_id>/`, W9). Files
(`.csv` or `.parquet`), paths below relative to that subdirectory:

| File | Leg | Written when |
|---|---|---|
| `sales_export.csv` (a.k.a. `pos_sales.*`) | **sales history** | onboarding (POS export) → later POS feed |
| `bom.csv` (RecipeLine rows) | **BOM** | the one-time recipe sitdown |
| `price_observations.csv` | **invoice / price history** | **built (W3, 2026-07-05)** — a digital-feed CSV upload (`ingest/capture/invoice_upload.py`); each confirmed invoice APPENDS rows (never a full replace, unlike the other two legs), so history accumulates |
| `food_cost.csv` | **derived per-dish ingredient cost (`Co`)** | **built (W6, 2026-07-14)** — recomputed from the BOM + latest prices and written full-replace (a current snapshot, not a history) whenever the operator saves a menu price or confirms a new invoice (`measures/costing/tenant_grid.py`); see "Co provenance" below |

The **fifth** leg — `eightysix_log.csv` (the 86/stockout log, the censored-demand signal) — is
**not** captured by the on-ramp. It is a separate, deliberately tiny habit (tap a dish when it 86s).
It still lands in `data/raw/` for the engine to read; it just has a different capture surface.

A future on-ramp product that replaces plate-cost inherits this contract: whatever it is, it writes
its captured legs to `data/raw/` in the agreed schema and touches nothing else.

> ### ⚠ The seam is contracted but not connected (recorded 2026-08-13)
>
> The one-way flow above is the *contract*. It is not what the code does today, and two gaps must be
> closed in **R1** (`../docs/real_data_readiness.md` §4) before real data can cross:
>
> 1. **The reader never reads what the writer writes.** The on-ramp writes `sales_export.parquet`,
>    `bom.parquet`, `price_observations.parquet`, `food_cost.parquet`. The engine's loader opens
>    `pos_sales.csv` — the **simulator's** file (`../ingest/demand/loader.py:82`). `grep -rn
>    "sales_export\|price_observations\|food_cost" decide/ ingest/demand/` returns nothing. Two writers, two
>    shapes, one reader that understands only the synthetic one.
> 2. **The sales leg is at the wrong grain, and no wiring fixes that.** `SalesExportRow`
>    (`../schemas/seam.py`) is one aggregate `count` over a `period_start`→`period_end` range. The
>    engine needs demand **per item per day** (`build_observed_demand`). The BOM leg is genuinely
>    shared between the two peers; the sales leg is not, and never has been.
>
> Until R1 lands, treat "the on-ramp captures the data the engine needs" as true of the **BOM leg
> only**.

## Schemas

The column-level schemas for these files are specified in `../docs/engine/simulated_data.md` (the
generator's view) and enforced in code by the shared definitions in `../schemas/`. When a real
export replaces the simulated one, the `../schemas/` definitions are the validation gate at ingestion.

## Forward notes (deferred design — gated when built)

Recorded decisions about future seam evolution, not yet built. Each clears the Comprehension
Contract (`.claude/rules/00-process.md`) when it lands.

- **Co provenance — a derived food-cost leg (review issue #3). Built (W6, 2026-07-14).**
  `food_cost.csv` (above) is now written: `schemas/seam.py::FoodCostRow` (`dish_id`, `dish_name`,
  `food_cost`, `computed_at`), recomputed from `bom.parquet` + the latest `price_observations.parquet`
  price per ingredient (`measures/costing/tenant_grid.py::build_food_cost_rows`) and written full-replace
  whenever the operator saves a menu price (`measures/costing/menu_prices.py` — "one recipe-confirmation
  act feeds two products," now also true of "one menu-price save") **or confirms a new invoice**
  (`surface/web/app.py::invoice_confirm_submit`, added post-review — a price-only invoice upload changes
  `Co` too, and the leg must not go stale until the next unrelated menu-price save;
  `surface/web/menu_prices.py::recompute_and_write_food_cost` is the one recompute path both actions share).
  It deliberately carries no `menu_price` itself — that stays app-DB-only catalog data
  (`docs/onramp/website_production_overview.md` §3's two-store laws) — and the cost math
  never needed `menu_price` in the first place. **Not yet wired into the engine**:
  `config/items.yaml` `Co` is still a hand-typed placeholder until a `decide/` phase reads this
  leg instead — that consuming change is out of this on-ramp phase's scope and remains open.

- **Stable `item_id` across the seam (review issue #4, durable fix).** The only key shared by
  `config/items.yaml` and `data/raw/` today is the display name (`name` ↔ `dish_name`) — a
  name-based join, the fragile pattern `identity/canonicalize.py::normalize_name()` exists to defend. The
  near-term guard lives in the engine's P2 ingestion (see `../docs/engine/construction_roadmap.md`
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
  `evaluate/`, not part of the seam this file governs, and today there is never more than one
  simulated dataset's truth in existence at a time. If a second tenant is ever actually simulated for
  a real dollar-floor comparison, `_truth/` will need the same treatment; flagged here, not built.
  - **`restaurant_id` is always the app-DB's `Restaurant.id`** (`db/models.py`,
    a `uuid.uuid4().hex` string) reused as the directory name — no second id scheme invented (mirrors
    the `dish_id`/`ingredient_id` `normalize_name()` precedent).
  - **Path-safety:** `store/__init__.py::tenant_raw_dir()` validates any caller-supplied
    `restaurant_id` against a path-safe-slug pattern (`^[A-Za-z0-9_-]{1,64}$` — alphanumerics, `-`,
    `_` only; rejects `.`, `/`, `\`, null bytes, empty string) before it ever reaches a filesystem
    path, since it is the one place across both peers where a variable, request-derived string
    becomes a path segment. the engine layers have no equivalent caller-supplied path today — the only
    tenant id it ever resolves is the fixed sentinel below — so it carries no matching validator;
    noted as a deliberate, scoped omission, not an oversight, in `docs/phase_decisions/W9.md`.
  - **The shared pre-tenancy sentinel:** the literal 32-character nil-UUID hex string
    `"00000000000000000000000000000000"` (`uuid.UUID(int=0).hex`) names the one demo/simulation
    bucket neither the on-ramp's static CLI (`surface/run.py`) nor the engine's
    dollar-floor scripts (`evaluate/*.py`, via `ingest/demand/loader.py::SIMULATED_RESTAURANT_ID`
    and `ingest/simulate/generator.py`'s own copy) have
    a real signup-issued tenant id for. Both sides hardcode this identical literal independently — no
    shared import crosses a layer boundary for it — so this file is the place to diff each copy
    against.
  - **The runtime whitelist guard moved one level deeper.** `ingest/demand/{loader,cleaner}
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
  (`store/__init__.py`) that opens only `data/raw/**` — structurally incapable of
  opening any other layer. `docs/common_base_reconciliation.md` Option 3 is live.
- The **runtime path assertion** and **import-boundary test** are specified in
  `.claude/rules/01-data-ingestion.md` and land when the first ingestion / simulate code is written
  (Phase 1).
- **The switch to import-linter is done (2026-08-14).** The old hand-rolled AST scan asserted two
  peer arrows; `.importlinter` now carries four contracts over the import graph itself —
  `layer-direction` (the whole L0–L4 chain), `truth-firewall` (this file's law #2),
  `plays-are-terminal`, and `shared-modules-are-leaves`. `tests/platform/test_import_boundaries.py`
  plants a real violation each run and confirms lint-imports goes red, so the guard is never one
  nobody has watched fail.
- **The text scan remains, narrowed to what an import graph cannot see:**
  `tests/platform/test_module_boundaries.py` looks for the literal `_truth` string in `.py`, `.html`,
  `.css`, and `.js` across every unsanctioned package — a hardcoded path in a template is invisible
  to import analysis.
