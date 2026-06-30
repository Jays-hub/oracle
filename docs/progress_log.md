# Progress Log — platform milestones & decisions

A dated, append-only record of what has been built and what has been *decided* (with the reasoning,
or a pointer to the decision record). Distinct from `ARCHITECTURE_REVIEW.md` (a point-in-time audit)
and `CLAUDE.md` "Current status" (a thin live snapshot): this is the running history. Newest first.

Convention: each entry is dated, tagged `[built]` / `[decided]` / `[gated]` / `[docs]`, and names the
artifacts touched. Decisions link their record rather than restating it.

---

## 2026-06-29 — Forward notes: Co provenance (#3) + cross-seam join key (#4) `[decided]`

The two conceptual items from the post-P0 review are about the engine↔seam boundary, which the
engine hasn't built yet (P1/P2 work). Building them now would mean standing up engine ingestion
ahead of its phase (Anti-Drift). Decision: **record both as forward design notes and defer the build
to its proper phase**, rather than gate them out-of-phase.

- **#3 — Co should derive from the on-ramp's computed plate cost, not be hand-typed.** Blocked today:
  the seam carries no prices, so the engine can't reconstruct a plate cost from `data/raw/`. Decided
  approach: a **derived food-cost seam leg** the on-ramp writes (one source of truth); deferred to the
  on-ramp's invoice/handoff phase; a gated step touching `data/CONTRACT.md` + `schemas/`. Recorded in
  **`data/CONTRACT.md` → Forward notes**.
- **#4 — config `name` ↔ seam `dish_name` is the only cross-artifact join key, and nothing enforces
  it.** Belongs in **P2 engine ingestion**, where `clean.py` already plans "reconcile item-name
  drift." Recorded as a note in **`forecasting/docs/construction_roadmap.md` Phase 2**: reconcile
  config names against the seam and fail loud on drift (reuse the local trim+casefold in
  `forecasting/src/config.py`; no on-ramp import). Durable fix (a stable `item_id` across the seam)
  also recorded in `data/CONTRACT.md`.

No code changed; docs only. This closes the post-P0 review: #1 built (config gate), #2/#5/#6/#7 built
(mechanical hardening), #3/#4 recorded and deferred to phase.

---

## 2026-06-29 — Review hardening: 4 mechanical fixes (#2, #5, #6, #7) `[built]`

The remaining mechanical items from the post-P0 review, fixed in one pass. Reuse of already-gated
disciplines — no new step, so the Comprehension Contract gate did not re-trigger (`00-process.md`
carve-out), same as the 2026-06-25 W0 hardening pass.

- **#2 — Co/Cu guard centralized (`forecasting/src/evaluate/objective.py`).** `critical_ratio`
  rejected non-positive costs but `dollar_loss` did not — so `dollar_loss(co=-14, …)` silently
  returned a negative "cost" straight into the ship/no-ship verdict. Extracted
  `_require_positive_costs(co, cu)` and call it from both `dollar_loss` and `critical_ratio`
  (`total_realized_cost` inherits it via `dollar_loss`). One gate, applied consistently.
- **#7 — scalar return type (`objective.py`).** A scalar `dollar_loss(...)` call returned
  `np.float64` (a 0-d result) despite the `float` annotation. Now returns a plain `float` for scalar
  inputs, `ndarray` for array inputs — `float(loss) if np.ndim(loss) == 0 else loss`.
- **#5 — store helper hardened (`onramp/plate_cost/src/store.py`).** Replaced the f-string SQL
  (`read_parquet('{path}')`) with a parameterized bind (`read_parquet(?)`); a missing seam file now
  raises a legible `FileNotFoundError` with a "run the export" hint instead of a raw DuckDB IO error
  (rule 07); the connection is context-managed (closed on error). Shared `_read_raw_parquet(filename)`
  takes a bare filename (+ a traversal assert) so the helper stays structurally confined to data/raw/.
- **#6 — deterministic price tie-break (`onramp/plate_cost/src/pricing/compute.py`).** `latest_prices`
  used a strict `>` (silent first-wins on equal dates); now `>=` with a documented rule — on an equal
  `observed_date`, the last observation in input order supersedes (a same-day re-entry wins).
- Tests added: scalar-`float` return, `dollar_loss`/`total_realized_cost` reject non-positive costs,
  store missing-file legible error, same-date tie-break.
- Verified: **84 tests pass (full-repo); ruff clean.** (+5 tests; no regressions.)

---

## 2026-06-29 — Forecasting P0 hardening: the config gate `[built]`

A post-P0 review found `config/items.yaml` — the engine's load-bearing economics — had **no
loader, no schema, and no test**: a typo (`prep_type: Batch`), a sign error (`co: -14`), or a
stray key would pass silently and quietly corrupt the dollar verdict (`q* = Cu/(Co+Cu)`). The seam
already had its head-chef gate (`schemas/seam.py`); the engine's own config did not. This closes
that gap — finishing P0 properly before P1 consumes the economics.

Gate 4 cleared (Jay): "By preventing silent failures, we are creating a PrepType enum and a pydantic
model that fail loudly when an unseen instance appears. In chef's terms, we are creating guards in
the kitchen that prevent taste and flavor from drifting even if the dish looks exactly the same."
(Failure mode: a config that *looks* fine but carries a wrong value, silently mis-routing an item or
producing a wrong dollar number.)

- **`forecasting/src/config.py`** — the validated load path. `PrepType` enum (`batch` /
  `made_to_order`); `ItemEconomics` pydantic model (`co>0`, `cu>0`, `lead_time_days>=1`,
  enum-constrained `prep_type`, `extra="forbid"` to catch typo'd keys); `load_items()` keyed by
  `id`, rejecting duplicate ids/names and structurally-wrong files with a **named** `ValueError`
  (which item, which field). Lives at `src/` top level on purpose — NOT `src/data/`, whose contract
  is "reads ONLY data/raw/"; this reads `config/`. Engine-only (not a seam artifact) so it does NOT
  go in the shared `schemas/`.
- **`forecasting/tests/test_items_config.py`** — 19 tests (accept/reject pattern from
  `test_seam_schemas.py`): shipped config loads all 11 items with the batch/made-to-order fork
  preserved; wrong-case/unknown `prep_type`, non-positive `co`/`cu`, `lead_time<1`, empty
  `id`/`name`, and typo'd keys rejected; duplicate id and normalized-duplicate name rejected;
  missing-file and structurally-wrong YAML rejected.
- **`requirements.txt`** — declared `PyYAML` (the loader) and `numpy` (already imported by
  `objective.py` since P0) as direct deps; both were transitive-only. Already pinned in the lock
  (PyYAML 6.0.3, numpy 2.5.0) — no install, lock unchanged.
- **Scope held:** the seam name-reconciliation (config `name` ↔ `data/raw` `dish_name`) is a
  separate finding (#4) and was deliberately NOT bundled here.
- Verified: **79 tests pass (full-repo); ruff clean.** (+19 engine tests; no regressions.)

---

## 2026-06-29 — Forecasting P0: decision frame `[built]`

Gate 4 cleared (Jay): "P0 builds metrics that are more important and interpretable than MAPE or RMSE
— using the right garnishes for the right meals so everything actually has meaning and fits together."
(Failure mode: optimizing accuracy on a target whose errors don't cost what was assumed.)

- **`config/items.yaml`** — per-item economic parameters (Co/Cu/prep_type/lead_time) for all 11
  items from the Marco menu. Batch items (7): Braised Short Rib, Pan-Seared Salmon, Half Roast
  Chicken, House Burger, Ribeye Steak 12oz, Duck Confit, Butter Poached Cod. Made-to-order (4):
  Wild Mushroom Risotto, Classic Caesar Salad, Pappardelle Bolognese, Tuna Tartare. Config carries
  the chef-set economic reality (food-cost-based Co; contribution-margin-based Cu); marked PLACEHOLDER
  pending real discovery. `q*` and `prep_qty` are derived downstream, never stored here.
- **`forecasting/src/evaluate/objective.py`** — three pure functions:
  - `dollar_loss(prep, demand, co, cu)` — scalar or vectorized; the verdict for every evaluation
  - `critical_ratio(co, cu)` → q* = Cu/(Co+Cu); the service level that minimises expected dollar_loss
  - `total_realized_cost(preps, demands, co, cu)` — sum across a backtest window; the bottom line
- **`forecasting/tests/test_objective.py`** — 13 tests: exact prep costs nothing; asymmetry
  (underage costlier than overage when Cu>Co); vectorized array output; q* math for real items;
  symmetric case → 0.5; rejects zero/negative Co or Cu; total cost sums correctly.
- **Done-when met**: objective runs on a dummy forecast and returns a dollar number; all 13 pass.
- Verified: **60 tests pass (full-repo); ruff clean.** (+13 new engine tests; no regressions.)

---

## 2026-06-25 — W0 review hardening: 8 fixes from the last-line-of-safety pass `[built]`

A review of the W0 web layer surfaced 8 items (3 moderate, 5 minor); all fixed one by one. Mechanical
reuse of already-gated disciplines — no new step, so the Comprehension Contract gate did not re-trigger.

- **Stop the silent dish-drop (moderate).** `web/compute.py` no longer swallows costing `ValueError`s
  with `pass` — it collects skipped dishes (name + reason), logs each, and surfaces them in a named
  on-page notice. Mirrors the CLI skip-collection in `src/run.py` (rule 01 missingness, rule 07
  name-the-failure).
- **One source of truth for rounding + quadrants (moderate).** `round_to_quarter` and
  `QUADRANT_ACTIONS` promoted to public in `src/report/grid.py` and imported by `web/compute.py`
  (was a verbatim duplicate that could drift the reconciliation discipline — rule 05).
- **W0 scope corrected in the docs (moderate).** W0 reads the on-ramp's *source* inputs, not the seam:
  the seam carries only BOM + sales and cannot reconstruct margins. Fixed `website_vision.md` §8, the
  `web/app.py` docstring, and added a `web/compute.py` comment; `src/store.py` is correctly unused by
  W0 (it stays the engine-handoff read path).
- **Route is sync, not async.** `web/app.py` `def grid` (not `async def`) so the blocking file I/O runs
  in a threadpool instead of stalling the event loop.
- **Legible error fallback.** The route catches failures and renders a calm `error.html` with a
  correlation id at HTTP 503 — no stack trace or internal path reaches the client; detail stays in the
  log (rules 06/07).
- **Pruned redundant `httpx`.** Both `httpx` and `httpx2` were installed; `httpx2` is the one
  Starlette 1.x's TestClient prefers. Uninstalled `httpx`, regenerated `requirements.lock.txt`.
- **Typed compute→template contract.** Added `DishRow` / `SkippedDish` / `GridData` TypedDicts in
  `web/compute.py` (rules 05/07 typed boundaries); `build_grid_data() -> GridData`.
- **Reconciled this log's test counts.** The earlier "30" and "35" were full-repo counts; the W0
  entry's "27" was plate-cost-only — the apparent 30 → 35 → 27 dip was a scope switch, now annotated.
- **Boundary law now enforced in the plate_cost suite too.** Added
  `onramp/plate_cost/tests/test_seam_boundary_local.py`, which loads the repo-root
  `tests/test_module_boundaries.py` by path and re-runs its onramp-side checks — so a developer
  running `pytest` inside `onramp/plate_cost/` catches a seam violation the local suite previously
  missed (the repo-root test runs only in the full-repo suite). The checks are discovered by name so
  the file never spells out the hidden-oracle path token, which the text scan would otherwise flag —
  a real false-positive the rewrite surfaced and dodged.
- Verified: **33 plate-cost tests pass (47 full-repo); `ruff` clean.** (+4 web tests: skipped-empty,
  uncostable-surfaced, legible-error, typed-contract; +2 local boundary checks. Negative-probe
  confirmed both boundary checks fail on a planted violation.)

## 2026-06-25 — W0: on-ramp website (read-only plate-cost reveal) `[built]`

Gate 4 cleared (Jay): "If we build it wrong, we will be left with improper readings and unbounded rules.
To a chef, we're adding garnish on the top of the dish to make everything more appetizing, not
necessarily more flavorful." (Failure mode: display drift that shows wrong numbers + a web layer that
makes seam constraints conventional rather than structural. Chef one-liner: garnish — visible, not new
flavor.)

- **`onramp/plate_cost/web/` — new web layer.** FastAPI + Jinja2, server-rendered HTML. No JS
  framework, no client-side data fetching; fast first paint.
- **`web/compute.py`** — thin glue: runs the same `src/` chain as `run.py`, returns template-ready
  dict. No business math in the handler (rule 05). Margin derives from the rounded cost so
  Menu − ~Cost = Margin reconciles by eye (rule 06 precision discipline).
- **`web/app.py`** — FastAPI app, one route: `GET /` renders the popularity × margin grid.
  Sample-data banner prominent. Quadrant sections color-coded (Stars/Plowhorses/Puzzles/Dogs).
  Dollar margin is the primary figure — large, in the money accent, above the fold.
- **`web/templates/`** — `base.html` (wordmark, sample banner, footer) + `grid.html` (quadrant
  sections, dish cards with margin/cost/food-cost-tier/covers).
- **`web/static/style.css`** — system fonts, warm off-white palette, one amber accent reserved for
  money, responsive card grid, WCAG AA contrast on dollar figures.
- **`web/__main__.py`** — `python -m web` entry (uvicorn, 127.0.0.1:8000).
- **`tests/test_web.py` — 6 new tests:** GET / returns 200; quadrant sections render; dollar figure
  present; sample banner present; margin reconciles with rounded cost (the precision regression test);
  static file reachable.
- **`requirements.txt`** updated: `fastapi`, `jinja2`, `uvicorn[standard]`, `httpx2`.
- Seam law holds: `web/` never imports `forecasting/`, never touches `_truth/`; boundary test passes.
- Verified: **27 plate-cost tests pass — 41 full-repo (incl. the repo-root seam-schema + boundary
  tests), consistent with the 30 → 35 → 41 full-repo progression; ruff clean.**

## 2026-06-25 — DuckDB-over-Parquet query layer: seam migration `[built]`

Gate 4 cleared (Jay): "a better storage system that prevents seam drift and can still utilize the
rules we have set to be enforced — tearing down the old walk-in for a new one with as little work
as possible."

- **Installed `duckdb` + `pyarrow`** (uncommented from `requirements.txt`; lock updated).
- **`onramp/plate_cost/src/store.py` — new on-ramp DuckDB access module.** Opens only
  `data/raw/**`; path is hard-coded and structurally incapable of being parameterized to any other
  layer. Module-load assertion fires if the path invariant breaks. Exposes `read_bom()` and
  `read_sales()`, zero-argument (no path parameter = no way to point at the wrong layer).
- **`run.py` `_export_to_raw()` migrated CSV → Parquet.** `bom.parquet` and `sales_export.parquet`
  now live in `data/raw/`; types survive the round-trip (dates arrive as dates, not strings). The
  schema-validate-on-write gate (`BomRow`, `SalesExportRow`) is unchanged — Parquet just enforces
  what the schema already checked. Removed unused `shutil` import.
- **`data/raw/bom.csv` and `sales_export.csv` deleted** — replaced by Parquet.
- **`tests/test_store.py` — new.** Structural tests: `_RAW_DIR` invariant, `data/raw/` exists,
  public API has no path parameters, round-trip write→read for both seam legs.
- **`data/CONTRACT.md`** — Enforcement Status updated: DuckDB-over-Parquet marked BUILT.
- Verified: **35 tests pass (full-repo suite), `ruff` clean.**

## 2026-06-25 — On-ramp website vision + full-stack governance `[docs]`

- **Split the plate-cost overview into focused docs.** `onramp/plate_cost/docs/plate_cost_overview.md`
  is now a slim **index** over: `purpose_and_phases.md`, `data_model.md`, `seam_and_precision.md`, and
  the new `website_vision.md`. Existing references to `plate_cost_overview.md` still resolve.
- **Authored the on-ramp website vision** (`onramp/plate_cost/docs/website_vision.md`) — the
  above-and-beyond north star for a clean, client-facing website that shows operators what we do with
  their data and what we find. Explicitly bounded by two disciplines: north-star-vs-phased-build, and
  provisional-product-vs-durable-slot. W0 (a read-only reveal over existing `data/raw/`) is the honest
  next slice.
- **Created full-stack development rules** in `.claude/rules/` (globs → `onramp/**`):
  `05-fullstack-architecture.md` (seam law for web code, DuckDB-over-Parquet storage, layering,
  thin-product/durable-slot), `06-frontend-ux.md` (dollar-legible value, precision/reconciliation
  discipline, transparency, tenant isolation, accessibility), `07-backend-api.md` (validation at the
  boundary via `schemas/`, the seam-write discipline, thin-over-pure-compute, friendly errors,
  security, testing). These are the full-stack peers of the engine rules `02`–`04`.
- **Updated governance:** root `CLAUDE.md` (Current status + `.claude/rules` index) and
  `onramp/plate_cost/CLAUDE.md` (Stack → DuckDB-over-Parquet + planned web stack; docs tree).

## 2026-06-25 — Storage decision: DuckDB-over-Parquet `[decided] [gated]`

- Considered Neon (serverless Postgres) for the on-ramp app's storage; **chose DuckDB-over-Parquet**
  instead, because the on-ramp's data is pulled by the engine and therefore belongs in the seam's own
  form rather than a separate operational DB that has to project into it. This is Option 3 in
  `docs/common_base_reconciliation.md` (already the *chosen* option there) — the `data/raw/**` files
  stay the firewall-enforcing artifact; DuckDB is the query layer over them.
- **Caveat recorded:** DuckDB is embedded/single-process — right for a thin, essentially single-tenant
  tool. A hosted, many-tenants-writing-concurrently service is the deferred "server-class DB" decision
  (`common_base_reconciliation.md` §6.6), where Neon would re-enter; revisit then, recorded and gated.
- **Open gate:** standing up the DuckDB-over-Parquet query layer (and migrating the on-ramp's seam
  write from CSV to Parquet) is a new build step. Gates 1–3 have been presented; **Gate 4 (Jay's
  restatement + chef one-liner) is not yet cleared** — no code written for it. (`.claude/rules/00-process.md`.)

## 2026-06-25 — Audit fix queue (8 items) `[built]`

Executed the prioritized fix queue from the repo audit, most→least important. All verified: 30 tests
passing (full-repo suite — plate-cost + the repo-root seam-schema & boundary tests), `ruff` clean,
seam intact.

1. **`run.py` export-path bug (critical).** `_REPO_ROOT` resolved one level too high, writing the
   seam export to `~/Documents/data/` instead of the repo's `data/raw/`. Fixed; regenerated the export
   into the correct seam; removed the leaked stray files (user-authorized).
2. **Shared seam schemas** (`schemas/seam.py`: `BomRow`, `SalesExportRow`) + validate-on-write. *(gated)*
3. **Test harness** + static cross-module boundary test (`tests/test_module_boundaries.py`). *(gated)*
4. **Covers-join fix:** normalize dish names on both sides + loud unmatched/orphan warnings. *(gated)*
5. **Grid display reconciliation:** printed margin now derives from the rounded cost (`Menu − ~Cost`).
6. **Dangling-ingredient hardening:** friendly `ValueError`, not a bare `KeyError`.
7. **`units.py` refactor:** base-factor model — symmetric, complete in-family conversions.
8. **Stale-status doc refresh** (`CLAUDE.md`, `ARCHITECTURE_REVIEW.md` dated note).

Three of the eight (#2–#4) touched real design and cleared the Comprehension Contract gate with Jay's
restatement + chef one-liner (captured in the code/docs); the five mechanical fixes did not re-trigger
the gate (per `00-process.md`'s carve-out).

## (earlier) — Phase-0 on-ramp built `[built]`

Plate-cost compute (BOM + `plate_cost = Σ qty_canonical / yield_factor × latest_price`), the
popularity × margin grid (Stars/Plowhorses/Puzzles/Dogs), and the schema-validated export of the sales
+ BOM legs into `data/raw/`. The forecasting engine (`forecasting/`) remains package skeleton only.
