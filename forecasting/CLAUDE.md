# CLAUDE.md — Forecasting Engine (the core)

> Platform-level governance (the two-product company, the shared data seam, the cross-cutting
> standing orders) lives in `../CLAUDE.md`. This file governs the **forecasting engine** peer. Paths
> below are repo-root-relative.

## What this is
A forecasting engine that outputs a **daily prep sheet**: how many of each high-volume item the
kitchen should make tomorrow, tuned per dish to whether running out or throwing out costs more.
At its core it is a **newsvendor decision engine** sitting on top of a **probabilistic demand
forecast**. Waste prediction is not a separate feature — it falls out of the same demand
distribution as a residual. The product is sold under a waste/spoilage *framing*; the engine
underneath is prep-demand. Full context: `docs/overview_and_method.md`.

This is the **core business** — the moat and the *end*. The `../onramp/` peer is the durable
acquisition + data-capture bridge that feeds this engine its history; it is the *means*. Keep them
distinct: defensibility lives here (prep forecast, exogenous fusion, cross-restaurant pool).

**This is a simulated, end-to-end learning build.** It is NOT yet a validated product. It runs on
synthetic data engineered to look like a real restaurant's first data dump. Whether prep-level
forecasting is actually unsaturated and wanted is an empirical question only real customer discovery
answers. Build the skill here; let operators decide the company.

## Comprehension is paired with construction — but on a parallel track, not a gate
Understanding is grown alongside the code, but it **does not gate engine work**: `forecasting/src/**` is
built freely and a phase's review closes on the **code** (findings, fixes, log entry). Comprehension
runs on its own spaced-repetition track — the `/learn` command + `comprehension-tutor` maintaining
`docs/mastery.md` — defined once in `../.claude/rules/00-process.md` (reasoning in
`docs/overview_and_method.md`), so it is **not re-listed here**. What's engine-specific: this is where
most code is written, so most `docs/mastery.md` topics originate here — running `/learn` after an engine
phase is the natural way to lock in the newsvendor / feature-hygiene techniques, but it is a practice
cadence, never a precondition for "done." (The old review-exit gate was retired 2026-07-01.)

## What "done" means at every step
Dollars, not accuracy — the platform standing order (`../CLAUDE.md`) and its full metric definition
(`.claude/rules/03-model-training.md`) are canonical; not re-derived here. Engine-specific: if a new
layer doesn't reduce dollar cost over the simpler version, it does not ship — validate before
deepening applies *inside* the model, not just to strategy.

## ANTI-DRIFT STANDING ORDER
Canonical statement: `../CLAUDE.md`. Engine-specific: the two highest-leverage things here are barely
"ML" — the **newsvendor reframe** (Phase 4) and the **data-access/exogenous grind** (Phases 5–7). If a
session drifts toward deep sequence models / elaborate causal inference before the per-dish
critical-ratio quantile model exists and beats baseline, name the drift and redirect.

## This is a simulation — the data must be built first
Phase 1 generates synthetic data that mirrors a real first data dump — a ground-truth generator (true
demand, stockouts, real recipes, injected spoilage) is what lets you verify the models actually work,
which a real customer's data never lets you do. The raw/truth split itself and who reads/writes each
side is the platform firewall, stated once below ("Shared store & the on-ramp") — not re-derived here.
Full schemas + generative process + realism checklist: `forecasting/docs/simulated_data.md`.

## The build path (phases → see forecasting/docs/construction_roadmap)
- **P0** Repo + config + the decision frame (Co/Cu per item, the dollar objective).
- **P1** Simulated data generator + honest baselines + rolling-origin backtest harness + stockout capture.
- **P2** Clean the polluted signal (comps/voids/staff, menu eras) + per-item point model (GBM, Poisson/Tweedie).
- **P3** Censored-demand unconstraining (recover true demand from sold-out caps). Validate vs `_truth/`.
- **P4** Distribution + the newsvendor turn (quantile + conformal → prep qty; waste/stockout as integrals). **The product in miniature.**
- **P5** Exogenous fusion (weather forecast-at-decision-time, events, reservation depth).
- **P6** Hierarchy & pooling (across items; across restaurants when multi-sim) + reconciliation.
- **P7** Recipe → ingredient → waste close (BOM, inventory identity, residual vs injected spoilage).
- **P8** The prep sheet + MLOps (one output surface, dollar reporting, drift/calibration monitoring, feedback loop).

## Module structure (the forecasting peer)
```
forecasting/
├── CLAUDE.md              # this file — engine governance
├── docs/                  # engine theory chapters; platform method/strategy is in ../docs/
├── src/
│   ├── simulate/          # the data generator (Phase 1) — writes data/raw/ AND data/_truth/
│   ├── data/              # loading, cleaning, menu-era tagging — reads ONLY data/raw/
│   ├── features/          # calendar, lags, exogenous joins
│   ├── models/            # baselines, point, quantile, hierarchical
│   ├── decision/          # newsvendor: critical ratio → prep qty; waste/stockout integrals
│   ├── evaluate/          # backtest harness, dollar metric, calibration — ONLY reader of data/_truth/
│   └── report/            # the prep sheet
├── notebooks/             # exploration + the written "why" for each phase
└── tests/
```
Engine rules (data ingestion, feature-eng, model-training, deployment) live in `../.claude/rules/`
and their `paths:` already target `forecasting/src/**`.

## Shared store & the on-ramp
- **Reads** model inputs only from `data/raw/`; **scores** only via `forecasting/src/evaluate/`
  against `data/_truth/`. Never import truth into a model path. (`../.claude/rules/01-data-ingestion.md`.)
- The `../onramp/` peer **writes** sales/BOM/invoice legs to `data/raw/`; the engine reads them as a
  normal "restaurant export." No special exception. The full who-writes-what contract: `data/CONTRACT.md`.
- The engine **must never** import from `../onramp/` (or vice versa). The only coupling is the data seam.

## Stack
Python. pandas/polars, numpy, scipy. **LightGBM/XGBoost** (Poisson/Tweedie + quantile objectives).
statsmodels/sktime (classical baselines, time-series CV). **MAPIE** (conformal). PyMC/NumPyro
(hierarchical, Phase 6+). pytest for the validation harness. YAML config (`config/`). DuckDB over the
`data/` Parquet/CSV store as the shared query layer (see `docs/common_base_reconciliation.md`).
pytest/ruff live only in the `restaurant-dev` conda env — always invoke via `make test` / `make lint`
(repo-root `Makefile`), never bare.

## Docs index (the encyclopedia lives in two homes)
**Engine theory — `forecasting/docs/`:** `conceptual_spine` (the newsvendor keystone) ·
`simulated_data` (the dataset spec) · `construction_roadmap` (the phases in full) · `data_hard_truths`
(restaurant-data gotchas) · `mastery_and_customer_language` (curriculum + customer language).
**Platform method/strategy — `../docs/`:** `overview_and_method` (method + the comprehension
contract) · `strategic_context` (why this wedge, the closed lanes, the 5-part test) ·
`discovery_and_validation` (the "Marco" data source + the question set) · `common_base_reconciliation`
(the shared-store / common-DB decision log).

## Current status
**P0–P4 built** (P0 2026-06-29; P1+P2 committed 2026-06-30 but not logged at the time — backfilled
here and in `docs/progress_log.md`; P3 2026-07-02; P4 2026-07-04). This section had gone stale after
P3 (still read "P3 is next" after P3 shipped) — corrected here alongside the P4 entry; the running,
authoritative history is always `docs/progress_log.md`, not this snapshot.
- **P0 — config-gated.** `config/items.yaml` (Co/Cu/prep_type/lead_time for all 11 items) +
  `forecasting/src/evaluate/objective.py` (`dollar_loss`, `critical_ratio`, `total_realized_cost`) +
  `forecasting/src/config.py` (validated `load_items()` head-chef gate). The dollar measuring stick
  exists, "done" is defined, and the economics can no longer drift silently.
- **P1 — simulated data + baselines + backtest.** `forecasting/src/simulate/generator.py` (the
  synthetic restaurant → `data/raw/` + `data/_truth/`); `forecasting/src/models/baselines.py`
  (seasonal-naive / same-weekday rolling mean / Croston); `forecasting/src/evaluate/backtest.py`
  (rolling-origin CV) + `baseline_floor.py`; `forecasting/src/data/loader.py`. Reproducible baseline
  floor (best baseline both cases: `rolling28`): $148,881.58 (dirty) / $147,584.42 (clean) via
  `python -m forecasting.src.evaluate.baseline_floor`.
- **P2 — cleaning + point model.** `forecasting/src/data/cleaner.py` (pollution stripping — voids +
  staff meals only; comp-flagged rows are kept as genuine demand, not stripped — see below; menu-era
  tagging); `forecasting/src/features/pipeline.py` (calendar, lags, rolling stats, walk-forward CV,
  leakage canary); `forecasting/src/models/point.py` — `GlobalLGBMModel`, a global LightGBM Poisson
  model (`item_id` a native categorical, trained across all items). P2's dollar-gated "done when" is
  now committed: `forecasting/src/evaluate/point_floor.py` runs the point model through the same
  backtest as the baselines — **$133,121.17 vs. the $147,584.42 clean floor, a $14,463.25 win** — and
  `forecasting/src/evaluate/cleaning_check.py` verifies the cleaned series against the hidden ground
  truth (MAE 0.302 vs. 0.472 raw). That check is *why* comps are kept: excluding comp-flagged rows
  (an earlier P2 choice) moved observed demand further from truth, not closer, because a comp tags a
  real fulfilled order — the kitchen still made and served the dish. See
  `docs/phase_decisions/P2_review.md` for the full remediation record.
- **P3 — censored-demand unconstraining.** `forecasting/src/models/unconstrain.py` recovers true demand
  on sold-out item-days (Tobit-flavored: tail-conditional expectation `E[D | D > cap]` via a NegBin/
  Poisson method-of-moments fit, not a plain historical mean). Dollar-gated "done when" committed via
  `forecasting/src/evaluate/unconstrain_floor.py`: on popular (ever-censored) items, scored on one common
  oracle-anchored ruler, unconstrained-target training beats clean-target training by **+$1,499.91**.
  `forecasting/src/evaluate/unconstrain_check.py` verifies recovered demand tracks the hidden ground
  truth on observably-censored days (MAE 5.076 → 3.090). See `docs/phase_decisions/P3.md` +
  `P3_review.md` for the full remediation record.
- **P4 — distribution + the newsvendor turn (the product in miniature).**
  `forecasting/src/models/quantile.py` (`QuantileGBMModel` — one LightGBM quantile regressor per level,
  global across items, non-crossing enforced by post-hoc rearrangement);
  `forecasting/src/decision/newsvendor.py` (`critical_ratio`, `prep_quantity` = `F⁻¹(q*)`,
  `expected_waste`/`expected_stockout` as CDF integrals, `route_batch_items` for rule 04 prep-type
  routing); `forecasting/src/evaluate/calibration.py` (empirical coverage + PIT vs. the hidden ground
  truth over end-anchored rolling-origin folds, a per-item underage breakdown, plus an independent MAPIE
  conformalized-quantile-regression cross-check); `forecasting/src/evaluate/newsvendor_floor.py` (the
  dollar gate, batch items only). `/review-phase P4` (`docs/phase_decisions/P4_review.md`) found the
  original dollar gate never scored the go-forward/censored window (MAJOR-1, the same root cause as
  P3's own BLOCKER-1) and applied the dish-count read-off to made_to_order items (MINOR-3); both fixed —
  full remediation record in `docs/phase_decisions/P4.md` "Remediation." Both "done when" conditions
  hold on the corrected, real-data run: calibration PASS (worst pooled deviation ~0.105, inside
  tolerance; MAPIE CQR coverage 0.748 at a 0.80 target) and the dollar gate PASS — quantile+newsvendor
  **$85,312.82** vs. point-model-as-mean **$85,923.40**, a **$610.58** improvement (~0.7%), scored on
  the 7 batch items over folds now reaching the series' true end (2024-06-30). This is a materially
  thinner and less consistent win than the phase's original (mis-scoped) $15,585.09/11.7% headline —
  the newsvendor arm wins 2 of 4 folds and loses 2 — read honestly, not oversold going into Phase 5.
- **Suite: 353 tests, 353 pass** (full repo via `make test`; lint clean, both import-linter contracts
  kept). Up from 316 post-P4-review (+37, see `docs/phase_decisions/P4.md` "Remediation"). The former
  red test (`test_features.py::test_lag_7_equals_same_weekday_last_week`) was a test-arithmetic bug, not
  an implementation bug — fixed 2026-06-30, see `forecasting/docs/construction_roadmap.md` Phase 2
  callout.
**P5 is next:** exogenous signal fusion (weather, events, forward reservation depth).
Simulation pending real customer discovery — treat all "Marco" numbers as plausible placeholders, not validated facts.
