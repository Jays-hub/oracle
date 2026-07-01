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
**P0–P2 built** (P0 2026-06-29; P1+P2 committed 2026-06-30 but not logged at the time — backfilled
here and in `docs/progress_log.md`).
- **P0 — config-gated.** `config/items.yaml` (Co/Cu/prep_type/lead_time for all 11 items) +
  `forecasting/src/evaluate/objective.py` (`dollar_loss`, `critical_ratio`, `total_realized_cost`) +
  `forecasting/src/config.py` (validated `load_items()` head-chef gate). The dollar measuring stick
  exists, "done" is defined, and the economics can no longer drift silently.
- **P1 — simulated data + baselines + backtest.** `forecasting/src/simulate/generator.py` (the
  synthetic restaurant → `data/raw/` + `data/_truth/`); `forecasting/src/models/baselines.py`
  (seasonal-naive / same-weekday rolling mean / Croston); `forecasting/src/evaluate/backtest.py`
  (rolling-origin CV) + `baseline_floor.py`; `forecasting/src/data/loader.py`. Reproducible raw-only
  baseline floor: $144,789 (clean) / $148,882 (dirty) via
  `python -m forecasting.src.evaluate.baseline_floor`.
- **P2 — cleaning + point model.** `forecasting/src/data/cleaner.py` (pollution stripping, menu-era
  tagging); `forecasting/src/features/pipeline.py` (calendar, lags, rolling stats, walk-forward CV,
  leakage canary); `forecasting/src/models/point.py` (point forecast baselines: lag-7, rolling-28,
  gut-proxy).
- **Suite: 175 tests, 175 pass** (full repo via `make test`; 164 engine+seam tests as of the P2
  backfill, +11 from the 2026-07-01 workflow-efficiency pass — CI/import-linter/hook tests under
  `tests/`, none of them engine-specific. The 6 gate-artifact tests from that pass were removed
  2026-07-01 when the comprehension gate was retired). The former red test
  (`test_features.py::test_lag_7_equals_same_weekday_last_week`) was a test-arithmetic bug, not an
  implementation bug — fixed 2026-06-30, see `forecasting/docs/construction_roadmap.md` Phase 2
  callout. P2 is now clean.
**P3 is next:** censored-demand unconstraining.
Simulation pending real customer discovery — treat all "Marco" numbers as plausible placeholders, not validated facts.
