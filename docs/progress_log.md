# Progress Log — platform milestones & decisions

A dated, append-only record of what has been built and what has been *decided* (with the reasoning,
or a pointer to the decision record). Distinct from `../docs_archive/ARCHITECTURE_REVIEW.md` (a
point-in-time audit, superseded and archived) and `CLAUDE.md` "Current status" (a thin live
snapshot): this is the running history. Newest first.

Convention: each entry is dated, tagged `[built]` / `[decided]` / `[gated]` / `[docs]`, and names the
artifacts touched. Decisions link their record rather than restating it.

---

## 2026-07-02 — P3 review remediation: dollar gate's false failure was a measurement bug — corrected result PASSES `[built]`

`/review-phase P3` (`docs/phase_decisions/P3_review.md`) found the P3 dollar gate's reported
−$3,533.87 "regression" was a false negative, not a real result. Closed all 3 findings; full evidence
and reasoning: `docs/phase_decisions/P3.md` "Remediation" section (this entry is the log pointer).

- **BLOCKER-1 — `unconstrain_floor.py` scored its two arms against two different answer keys.** The
  clean arm was scored against `clean_demand()`'s capped actual; the unconstrained arm was scored against
  its own corrected actual. On the censored test days, that mechanically raised the bar for the
  unconstrained arm alone, fabricating a regression. Rewritten so both arms train on their own target
  (that's the point of the comparison) but are SCORED against one fixed ruler
  (`_oracle_actual`: `clean_demand()`'s observed series with observably-censored rows raised to their
  real `true_demand` from the oracle — sanctioned, `unconstrain_floor.py` lives in `evaluate/`).
  **Corrected result: popular-item dollar cost, clean $112,428.46 → unconstrained $110,928.54, a
  +$1,499.91 improvement — the dollar gate now PASSES.** Both halves of the phase's "done when" are
  legitimately met: recovered demand tracks truth on capped days (MAE 5.076 → 3.090) *and* popular-item
  dollar cost improves vs. Phase 2.
- **MINOR-1 — 2 of 66 observable censored rows fell outside every backtest fold.**
  `RollingOriginBacktest`'s week-granularity test windows left the last fold's end 2 days short of the
  series' true final date (2024-06-28 vs. 2024-06-30). Fixed surgically with
  `_splits_with_full_tail_coverage`, which extends only the LAST fold's test window to the series' true
  end, touching no other fold's boundaries. A first attempt instead trimmed days off the series' START so
  the fold math divided evenly — rejected after it shifted every fold's date boundaries and materially
  changed the dollar result along with the coverage (confirmed by reproducing the reviewer's own
  spot-check number, +$1,507.15, using the *old* fold placement — a fix for a 2-day tail gap should not
  perturb the other three folds, and the surgical version doesn't; the ~$7 gap between +$1,499.91 and
  +$1,507.15 is exactly the now-included tail days).
- **NIT-1 — stale MAE numbers.** `unconstrain.py`'s docstring and `P3.md` quoted "MAE 5.28 → 3.09,
  bias −5.08 → −1.70"; the real run shows 5.076 → 3.090, bias −5.076 → −1.699 (MAE must equal |bias| here
  since every capped error has the same sign — the original numbers were internally inconsistent).
  Refreshed in both places.
- **`forecasting/tests/test_unconstrain_floor.py` (new, +6 tests):** guards both fixes directly against
  regressing back — the ruler function takes no per-arm parameter (structurally can't diverge between
  arms again), a missing truth row raises loudly, and the tail-extension helper is asserted to leave
  every fold except the last byte-identical to `RollingOriginBacktest`'s own output.
- **Suite: 238 tests, 238 pass** (`make check`: lint clean, both import-linter contracts kept). Up from
  232 — net +6, all in `test_unconstrain_floor.py`.
- P3 is now done: build closed on `docs/progress_log.md` (2026-07-02 build entry below), review closed on
  this entry — per `00-process.md`, no comprehension step required.

---

## 2026-07-02 — P3: censored-demand unconstraining built — truth-check passes, dollar gate fails honestly `[built]`

`/build-phase P3` — recovers true demand on sold-out (censored) day-items so the point model's training
target stops silently understating popular dishes. Full reasoning, evidence, and the two open judgment
calls a reviewer should weigh in on: **`docs/phase_decisions/P3.md`**. Not marked done here — per
`00-process.md`, that happens when `/review-phase P3` closes on the code.

- **`forecasting/src/models/unconstrain.py` (new) — `unconstrain_demand(demand_df, min_history=8)`.**
  Fits a Negative Binomial (falling back to Poisson when the sample isn't overdispersed) via method of
  moments to each item's own uncensored history — expanding-window, strictly-prior-only, same
  shift-then-roll discipline `FeaturePipeline`'s lag features already use — then takes the **conditional
  expectation above the observed cap**, `E[D | D > cap]`, not the unconditional mean. That distinction is
  the whole result: a first version using the plain historical mean corrected essentially nothing (avg
  lift +0.00 across 66 real censoring events, because a censored day is by definition an above-average
  day, and averaging it with ordinary days regresses back toward typical). The tail-expectation version
  lifted the same 66 rows by an average of +3.38 and cut MAE against the hidden truth stockout log from
  **5.28 → 3.09** (bias −5.08 → −1.70). `max(observed, estimate)` enforces the one hard constraint
  structurally: a censored observation is a lower bound, recovery can only raise the target.
- **`forecasting/src/evaluate/unconstrain_check.py` (new)** — the phase's own literal checkpoint ("does
  recovered demand match truth_demand on truth_stockouts days?"), the second sanctioned oracle reader
  alongside `cleaning_check.py`. Scoped to the 66 of 713 true censoring events that were actually
  *observable* (go-forward window only — `eightysix_log.csv` isn't populated for historical dates, the
  "86-board reality" named in the roadmap's own Practices list) rather than diluting the check against
  the ~90% of censoring history no method can see. **PASS.**
- **`forecasting/src/evaluate/unconstrain_floor.py` (new)** — the dollar gate: point model trained (and
  scored) on the unconstrained target vs. Phase 2's clean target, on the items that actually sold out.
  **FAILS, honestly reported, not hidden:** popular-item cost $102,050.21 (clean) → $105,584.08
  (unconstrained), a $3,533.87 regression. The script's own fold-decomposition shows this is concentrated
  entirely in the (fold, item) windows that actually contain a censored test day — consistent with
  `GlobalLGBMModel` being a mean-seeking point forecast asked to hit a now-honestly-higher target on a
  right-skewed spike day, exactly the limitation Phase 4's quantile/newsvendor read-off exists to close
  ("a point forecast can't produce the right prep quantity," construction_roadmap.md Phase 4). Verified
  directly that scoring the same predictions against the old, still-capped actual makes the number look
  better but is the wrong comparison — it would charge overage for correctly predicting demand that was
  genuinely there. **Left as a flagged, unresolved tension for `/review-phase P3`, not papered over.**
- **Fold-placement bug caught mid-build, not shipped:** `RollingOriginBacktest.splits()` anchors every
  fold at the *first* date of whatever series it's given, not a sliding recent window. On this project's
  ~2.5-year data, `point_floor.py`-style default fold placement only ever scores 2022-03-26..2022-07-15 —
  nowhere near the observable censored window (2024-04-05..2024-06-30). Before catching this,
  `unconstrain_floor.py` silently reported a **0.00 "improvement"** (identical dollar cost to the cent —
  the two training targets never differed inside any scored fold). Fixed locally inside
  `unconstrain_floor.py` (`_min_train_weeks_reaching_tail`, a dynamic fold-placement helper) rather than
  touching the shared `backtest.py` harness, which `baseline_floor.py`/`point_floor.py`/`day_ahead_eval.py`
  already cite numbers against. Worth knowing: `point_floor.py`'s own "$133,121.17" is therefore scored
  entirely on 2022 data and never touches a single censored row, clean or corrected.
- **`.claude` firewall note:** the substring-scan boundary test (`test_module_boundaries.py`) flagged the
  literal string `_truth` inside `unconstrain.py`'s own docstring — written while *explaining* that the
  module never touches the hidden ground-truth store. Reworded to match `cleaner.py`'s existing
  "oracle"/"hidden ground-truth store" vocabulary. A real, if slightly ironic, catch.
- **`forecasting/tests/test_unconstrain.py` (new, +12 tests):** hand-computed correctness (fine-grain and
  coarse-fallback cases, each independently re-derived via scipy rather than calling the module's own
  helper), Poisson-fallback and extreme-cap edge cases, cold start, the `recovered >= observed` structural
  invariant across a randomized series, reproducibility, and `test_correction_is_prefix_stable` — proves
  a row's correction is a function of only its own past by construction, not just by inspection.
- **`requirements.txt`:** comment updated — scipy is now a *direct* dependency (the NegBin/Poisson fit),
  not just lightgbm's transitive one.
- **Suite: 232 tests, 232 pass** (`make check`: lint clean, both import-linter contracts kept). Up from
  220 — net +12, all in `test_unconstrain.py`.

---

## 2026-07-02 — P2 review remediation: dollar-gate evidence committed + comp-exclusion bug found & fixed `[built]`

Closed all 7 findings in `docs/phase_decisions/P2_review.md` (the phase-reviewer's adversarial pass on
P2). Full detail, evidence, and code pointers live in that file and in the module docstrings/rule
edits it references; this entry is the log pointer.

- **BLOCKER-1 — the dollar gate is now a committed, runnable artifact, not a review-time ad hoc
  check.** `forecasting/src/evaluate/point_floor.py` runs `GlobalLGBMModel` through the same
  `RollingOriginBacktest` as the three baselines and asserts the win; `forecasting/src/evaluate/
  cleaning_check.py` (the second sanctioned `_truth/` reader) verifies the cleaned demand series is
  closer to ground truth than raw. `forecasting/tests/test_point.py` (+5 tests) covers the fit/predict
  contract and a non-regression backtest guard.
- **Found while building the truth check, not part of the original review: `cleaner.py`'s
  comp-exclusion was actively wrong.** Comp-flagged rows tag real, fulfilled guest orders (comped on
  the bill after the kitchen prepped and served them) — not phantom demand like staff meals. Excluding
  them moved observed demand *further* from `_truth/truth_demand.csv` (MAE 0.522 vs. 0.472 raw) because
  observed demand is already censored at or below the true series, so removing any real-demand subset
  can only widen that gap. Fixed: `cleaner.py` now excludes only voids + staff meals; comps stay in
  (MAE 0.302). This also corrects the stale claim in the 2026-06-30 backfill entry below and in the old
  `CLAUDE.md` "Current status", which described `point.py` as the three baselines — it is
  `GlobalLGBMModel` (global LightGBM Poisson). `.claude/rules/01-data-ingestion.md`'s "Restaurant-
  Specific Signal Cleaning" section updated to match (previously said "tag and exclude comps").
  Dollar floor moved with the corrected cleaning: clean floor $147,584.42 (was $144,789, computed on
  the over-stripped series); point model still wins clean, $133,121.17 (a $14,463.25 margin).
- **MAJOR-3 — lag-feature skew in the block backtest documented, not silently left implicit.**
  `RollingOriginBacktest` scores a whole test window in one `predict()` call, so lag features deep in
  the window are mostly NaN (symmetric across baselines and the GBM, so the dollar comparison stays
  fair — see `point.py` docstring). Added `FeaturePipeline.extend_history()` (+2 tests) and
  `forecasting/src/evaluate/day_ahead_eval.py`, a non-gating diagnostic that replays the real
  day-ahead regime (reveal each day's actual before scoring the next): lag fill rate goes from ~4-25%
  to 100%. Restructuring the shared backtest harness itself was judged out of scope for a remediation
  pass (Anti-Drift).
- **MINOR-4 — censored tag now scoped to `service_period`.** Was keyed on `(date, item_id)` only, so a
  dinner 86 wrongly censored that day's lunch row too. Now derives `service_period` from `time_86d`
  the same way `loader.py` does for POS sales. +1 test (`test_dinner_86_leaves_lunch_uncensored`).
- **MINOR-5 — two rule-01 requirements added to `cleaner.py`:** a missingness report (null count/% per
  column, printed before any exclusion) and a qty==0-with-no-void/comp-flag quarantine (a data-quality
  anomaly, not censored demand — no numeric effect on demand values, since such a row already
  contributed 0 to the aggregate; this closes an observability gap). +3 tests.
- **MINOR-6 — `GlobalLGBMModel.fit()` now logs rule-03 diagnostics:** a per-item predicted-vs-actual
  mean table (`self.item_bias_`) and feature importances (`self.feature_importances_`), the check that
  would surface censored-row contamination as per-item bias. MLflow logging stays parked (premature
  infra). +1 test.
- **NIT — dtype convention (Python `date`/object-dtype ids vs. rule 01's `datetime64`/`Categorical`
  letter) recorded as deliberate in `.claude/rules/01-data-ingestion.md` rather than refactored — no
  measured correctness or perf cost, internally consistent across every consumer.**
- **Suite: 220 tests, 220 pass** (`make check`: lint clean, both import-linter contracts kept). Up
  from 209 — net +11 across `test_point.py`, `test_features.py` (`extend_history`), and `test_cleaner.py`
  (comp/censoring/data-quality cases).


## 2026-07-02 — Backfill: W0 (read-only reveal) was built but never logged or reviewed `[built]` `[backfilled]`

`/build-phase W0` was invoked to build the on-ramp's first web phase; exploration found it **already
built** — `onramp/plate_cost/web/` (FastAPI app, Jinja2 templates, static CSS) exists, matches the
`website_vision.md` §8 W0 spec, and its test suite passes. Like the 2026-06-30 P1/P2 backfill, this
landed in the squashed `a66f85a` initial commit (2026-06-30) from work actually done earlier — the
only prior trace is an oblique "2026-06-25 W0 hardening pass" mention in this log's 2026-06-29 entry.
No `docs/phase_decisions/W0.md` existed and `/review-web W0` has never run. Jay chose to backfill the
missing artifacts rather than rebuild working code.

- **What's built:** `web/app.py` — single `GET /` route, sync handler (blocking I/O runs in
  FastAPI's threadpool), calm 503 + correlation-id on failure (no stack trace to the client).
  `web/compute.py` — thin glue running the same chain as `src/run.py` (`src/bom/loader.py` →
  `src/pricing/compute.py` → `src/report/grid.py`) against local `onramp/plate_cost/data/sample_*.csv`
  — **not** the seam (`data/raw/`), because the seam carries only BOM+sales and can't reconstruct
  margins. `web/templates/{base,grid,error}.html` — server-rendered Jinja2, no JS framework, sample-data
  banner, quadrant grid, dollar figures rounded to the $0.25 grid with margin derived from the
  *rounded* cost (rule 06 reconciliation discipline). `web/__main__.py` — `python -m web`, binds
  `127.0.0.1:8000` only.
- **Tests: 10/10 pass** (`onramp/plate_cost/tests/test_web.py`) — 200 status, quadrant sections
  present, dollar figures, sample banner, margin-reconciles-with-rounded-cost, static file reachable,
  empty `skipped` on clean data, `DishRow` contract match, legible 503 on simulated failure,
  uncostable dish surfaced not dropped (not silently dropped). `ruff check` clean. Full-repo
  `make test`: 209 passed (unchanged — no code was added).
- **Boundary firewall holds:** `tests/test_module_boundaries.py` already `rglob`s all of `onramp/`,
  so `web/` is covered — no `forecasting/` import, no `_truth` path.
- **Gap flagged, not fixed:** no deployment/hosting artifact exists anywhere (no Dockerfile, no prod
  ASGI config) despite the spec calling W0 "a single hosted page" / "show a client in 60s." Not
  recorded as deferred to any later phase — an open question for `/review-web W0` to weigh in on.
  Full reasoning, design decisions, and load-bearing assumptions: **`docs/phase_decisions/W0.md`**
  (itself a reconstructed, not contemporaneous, decision log — flagged as such in its own Reviewer
  Focus Areas).
- Not marked done here — per `00-process.md`, that happens when `/review-web W0` closes on the code.

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
