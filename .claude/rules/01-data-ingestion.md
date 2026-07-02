---
paths:
  - "forecasting/src/data/**/*.py"
  - "forecasting/src/simulate/**/*.py"
  - "forecasting/notebooks/*.ipynb"
---
# Data Ingestion & Integrity Rules

## Raw vs. Truth Separation (Non-Negotiable)
- Models may ONLY read from `data/raw/`. Ground truth in `data/_truth/` is for scoring only — never pass it to any pipeline that touches model inputs.
- Enforce this with a runtime path assertion at the top of every data-loading module.
- **Single funnel for the oracle.** Exactly one module may *read* `data/_truth/` — it lives in `forecasting/src/evaluate/` — and only `forecasting/src/simulate/` may *write* it. No other module opens a `_truth/` path or imports the truth loader.
- **Structural enforcement, not just convention.** An import-boundary / architectural test (e.g. import-linter) asserts that nothing under `forecasting/src/{data,features,models,decision,report}` imports the truth loader or references a `_truth` path; it runs in CI beside the leakage canary. The runtime path assertion is the last line of defense — the structural test is the first, so a leak fails the build before it can ever fire.

## Missingness & Data Quality
- Never drop missing values blindly; always print a missingness report (count + % per column) first.
- Distinguish structural missing (e.g., stockout-censored quantities) from random missing — handle them differently.
- Flag and quarantine rows where `quantity == 0` but no void/comp flag is set as a **data-quality anomaly** (likely a missing void/comp flag or export glitch) — **not** censored demand. True censoring appears as selling the *cap* (a positive `sold_qty == prep_qty`), never as a zero.

## Type Safety & Schema Enforcement
- Enforce strict data type casting on load: dates → `datetime64[ns]`, item/category columns → `pd.Categorical`, quantities → `int64`, prices → `float64`.
- Validate schema at ingestion time (pandera or a schema dict); fail loudly on type or range violations rather than silently coercing.
- **Recorded convention (2026-07-02, P2 review NIT):** `forecasting/src/data/{cleaner,loader}.py` and `features/pipeline.py` deviate from the letter of the rule above — `business_date` is a Python `date` object (not `datetime64[ns]`), and `item_id`/`service_period` stay plain-`object` strings, cast to `pd.Categorical` only at the LightGBM boundary in `models/point.py`. This is a deliberate, internally-consistent choice (every consumer agrees on it), not an oversight — a cross-file dtype migration was judged not worth doing for a style-only deviation with no measured correctness or perf cost. Revisit if that changes.

## Temporal Integrity
- Sort all data by `(date, service_period)` immediately after load and assert monotonicity before any downstream step.
- Never use random/shuffle-based splits on time-series data — use strict temporal cutoffs.
- Seed all deterministic operations (`random_state=42`) for reproducibility.

## Restaurant-Specific Signal Cleaning
- Tag and exclude structural pollution — voids and staff meals — from the demand signal before any model sees data. Log the exclusion count per run.
- **Comps are not automatically excluded.** A comp tags a real, fulfilled order (comped on the bill after the kitchen already prepped and served it) — it is not automatically phantom demand the way a staff meal is. Verify any comp-exclusion policy against `data/_truth/` (via the sanctioned reader in `forecasting/src/evaluate/`) before excluding a comp/discount category: in this project's simulated data, excluding comp-flagged rows moved observed demand *further* from ground truth, not closer (`forecasting/src/evaluate/cleaning_check.py`, `docs/phase_decisions/P2_review.md` BLOCKER-1), because observed demand is already censored at or below the true series, so removing any real-demand subset can only widen that gap.
- Detect and tag menu-era boundaries (item introductions, price changes, recipe reformulations) — all features and models must be era-aware.
- Stockout detection: if `sold_qty == prep_qty` on a given day, flag as potentially censored (true demand ≥ observed). Do not treat these as clean observations. This `sold == capacity` pattern — not a `qty == 0` row — is the censored-demand signal Phase 3 unconstrains.
- Censored tags must be scoped to the actual daypart affected (via a stockout-event timestamp, e.g. `time_86d`), not just `(date, item)` — a dinner-only stockout must not censor that day's lunch row.
