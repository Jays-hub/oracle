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

## PRIME DIRECTIVE — comprehension is paired with construction (NON-NEGOTIABLE)
The Comprehension Contract is the platform gate, and it sits on the **review's exit, not the build's
start**. It is defined once — verbatim and always-on — in `../.claude/rules/00-process.md` (full
reasoning in `docs/overview_and_method.md`), so it is **not re-listed here**. What's engine-specific:
it **binds engine work hardest** (this is where most code is written), so `forecasting/src/**` is built
freely, but no engine phase is *done* until Jay can fully explain the finished, reviewed work in his own
words (restate it + the "say it to a chef" line) — the agent never self-certifies it.

## What "done" means at every step
**Beat the prior baseline in DOLLARS, not accuracy.** The objective is realized cost
`Σ (Co·overage + Cu·underage)` vs. the gut/naive baseline — never MAPE or RMSE. If a new layer
doesn't reduce dollar cost over the simpler version, it does not ship. Validate before deepening
applies *inside* the model, not just to strategy.

## ANTI-DRIFT STANDING ORDER
Jay's known failure mode is a pull toward intellectually rich modeling over the highest-value,
least-contested work. The two highest-leverage things here are barely "ML": the **newsvendor
reframe** (Phase 4) and the **data-access/exogenous grind** (Phases 5–7). If a session drifts
toward deep sequence models / elaborate causal inference before the per-dish critical-ratio
quantile model exists and beats baseline, the agent must name the drift and redirect. (This applies
across the company — including drift *into* the on-ramp peer; see `../CLAUDE.md`.)

## This is a simulation — the data must be built first
Phase 1 generates synthetic data that mirrors a real first data dump. The discipline:
- `data/raw/` = "what the restaurant hands you" — messy, polluted, censored. **Models read ONLY here.**
- `data/_truth/` = ground truth from the generator (true demand, stockouts, real recipes, injected
  spoilage). **For scoring ONLY — never a model input.** This is what lets you verify the models work.
The shared store is platform infrastructure (owned by neither code peer); the seam contract is
`data/CONTRACT.md`. Full schemas + generative process + realism checklist: `forecasting/docs/simulated_data.md`.

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

## Docs index (the encyclopedia lives in two homes)
**Engine theory — `forecasting/docs/`:** `conceptual_spine` (the newsvendor keystone) ·
`simulated_data` (the dataset spec) · `construction_roadmap` (the phases in full) · `data_hard_truths`
(restaurant-data gotchas) · `mastery_and_customer_language` (curriculum + customer language).
**Platform method/strategy — `../docs/`:** `overview_and_method` (method + the comprehension
contract) · `strategic_context` (why this wedge, the closed lanes, the 5-part test) ·
`discovery_and_validation` (the "Marco" data source + the question set) · `common_base_reconciliation`
(the shared-store / common-DB decision log).

## Current status
**P0 complete + config-gated (2026-06-29).** `config/items.yaml` (Co/Cu/prep_type/lead_time for all
11 items) + `forecasting/src/evaluate/objective.py` (`dollar_loss`, `critical_ratio`,
`total_realized_cost`) + `forecasting/src/config.py` (the validated `load_items()` head-chef gate:
`PrepType` enum + `ItemEconomics` model — positive costs, known prep_type, no stray keys, no
duplicate ids/names, fails loud and named). 32 engine tests. The dollar measuring stick exists,
"done" is defined, and the economics can no longer drift silently.
**P1 is next:** simulated data generator + baselines + rolling-origin backtest harness.
Simulation pending real customer discovery — treat all "Marco" numbers as plausible placeholders, not validated facts.
