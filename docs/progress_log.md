# Progress Log — platform milestones & decisions

A dated, append-only record of what has been built and what has been *decided* (with the reasoning,
or a pointer to the decision record). Distinct from `../docs_archive/ARCHITECTURE_REVIEW.md` (a
point-in-time audit, superseded and archived) and `CLAUDE.md` "Current status" (a thin live
snapshot): this is the running history. Newest first.

Convention: each entry is dated, tagged `[built]` / `[decided]` / `[gated]` / `[docs]`, and names the
artifacts touched. Decisions link their record rather than restating it.

---

## 2026-06-30 — Documentation-relevance review: `docs_archive/` created `[docs]`

Read every authored doc in the repo (~31 files across `docs/`, `forecasting/docs/`,
`onramp/plate_cost/docs/`, and the root/module `CLAUDE.md`/`README.md`s — `.claude/rules|agents|commands`
excluded as live config, not historical record) and assessed each for whether it still governs current
work or has already been absorbed elsewhere. Result: only 2 of ~31 had actually served their purpose;
this repo's non-redundant-by-design doc discipline means almost everything found is either an active
governance file, an open backlog/spec, or a directly cross-referenced authoritative source.

- **`ARCHITECTURE_REVIEW.md` → `docs_archive/ARCHITECTURE_REVIEW.md`.** A 2026-06-22 audit whose own
  header already marks its core recommendation superseded; the adopted decision is now fully captured
  in `CLAUDE.md`, `../onramp/README.md`, `../data/CONTRACT.md`, and `common_base_reconciliation.md`.
- **`progress_log_archive.md` → `docs_archive/progress_log_archive.md`.** Already-archived entries
  (2026-06-25 and earlier); relocated so there's one archive location instead of two.
- **`docs_archive/README.md` (new)** — explains why each archived file was retired and points back to
  its current authority, same convention as every other folder's index doc.
- Repointed this file's two references to the new paths (the intro line and the "older history"
  pointer below).

No code or governance content changed — a pure documentation-hygiene pass, so the Comprehension
Contract gate did not trigger (mechanical, per `00-process.md`'s carve-out).

---

## 2026-06-30 — Project-state snapshot from a workflow audit `[audit]`

A full audit of the agentic workflow (recorded in `docs/agentic_workflow/current_state.md`) also
exercised the actual codebase along the way. Project-state facts it surfaced, captured here since
they're product status, not workflow status:

- **Suite: 164 tests, 163 pass / 1 FAIL** in the `restaurant-dev` conda env.
- **Known failing test:** `forecasting/tests/test_features.py::test_lag_7_equals_same_weekday_last_week`
  — a leakage-adjacent lag-7 test, currently red. Flagged as an open issue in
  `forecasting/docs/construction_roadmap.md` (Phase 2). Not yet fixed.
- **Seam firewall verified holding in code:** no `_truth` reference under
  `forecasting/src/{data,features,models,decision,report}`; no real `forecasting` import in
  `onramp/` (doc/comment mentions only). `tests/test_module_boundaries.py` passes.
- **Dollar-metric discipline verified reproducible:** raw-only baseline floor of $144,789 (clean) /
  $148,882 (dirty) via `python -m forecasting.src.evaluate.baseline_floor`.

---

## 2026-06-30 — Backfill: P1 + P2 were built but never logged `[built]` `[backfilled]`

Git/file-state inspection (prompted by the workflow audit above) found `forecasting/` is **not**
"package skeleton, nothing built" as `CLAUDE.md`/`forecasting/CLAUDE.md` claimed — P1 and P2 are
both substantially built and committed. They were built across the squashed `a66f85a` ("Initial
commit") and `2698401` ("Add P2 feature pipeline...") commits without a progress-log entry at the
time. Backfilling now; `CLAUDE.md` and `forecasting/CLAUDE.md` Current status updated to match.

- **P1 — simulated data + honest baselines + backtest harness** (in `a66f85a`, mislabeled in its own
  commit message as "P0 (decision frame)" only):
  - `forecasting/src/simulate/generator.py` — the synthetic-restaurant generator writing
    `data/raw/` (messy export) + `data/_truth/` (ground truth) per `forecasting/docs/simulated_data.md`.
  - `forecasting/src/models/baselines.py` — seasonal-naive, same-weekday rolling mean, Croston
    (intermittent demand).
  - `forecasting/src/evaluate/backtest.py` — rolling-origin CV harness.
  - `forecasting/src/evaluate/baseline_floor.py` + `forecasting/src/data/loader.py`.
  - Reproducible raw-only baseline floor: **$144,789 clean / $148,882 dirty**.
  - Tests: `test_simulator.py`, `test_baselines.py`, `test_backtest.py`, `test_loader.py`,
    `test_cleaner.py` (an earlier cleaner version also landed in this commit).
- **P2 — clean the polluted signal + per-item point model** (in `2698401`):
  - `forecasting/src/data/cleaner.py` (extended) — pollution stripping, menu-era tagging.
  - `forecasting/src/features/pipeline.py` — calendar/lag/rolling-stat features, walk-forward CV,
    a leakage canary.
  - `forecasting/src/models/point.py` — point-forecast baselines (lag-7, rolling-28, gut-proxy).
  - Tests: `test_features.py` (288 lines) — **one test is currently red**,
    `test_lag_7_equals_same_weekday_last_week` (see the audit entry above and
    `forecasting/docs/construction_roadmap.md` Phase 2). P2 is not clean until this is resolved.
- **No Comprehension Contract exit was exercised for either phase** — both were built and committed
  under the old pre-code gate model (before the 2026-06-30 gate inversion, also same day) without a
  `docs/phase_decisions/Pn.md` artifact. This is the same gap `efficiency_backlog.md` already tracks
  ("no gate artifacts produced"); noted here so the backfill doesn't imply the gate was cleared.

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

> **Older history archived.** Entries dated 2026-06-25 and earlier live in
> [`../docs_archive/progress_log_archive.md`](../docs_archive/progress_log_archive.md) so this active
> log stays small for per-build reads. Move an entry there once it is no longer current-era context.
