---
paths:
  - "onramp/**/*.py"
  - "onramp/**/*.ts"
  - "onramp/**/*.tsx"
  - "onramp/**/*.js"
  - "onramp/**/*.jsx"
  - "onramp/**/*.sql"
---
# Full-Stack Architecture Rules (the on-ramp web stack)

**Scope.** These rules govern the on-ramp's web stack (`onramp/**`) — the client-facing website and
its backend. They are the full-stack peers of the engine rules (`02`–`04`, scoped to
`forecasting/src/**`). The Comprehension Contract (`00-process.md`) governs them all; full vision in
`onramp/plate_cost/docs/website_vision.md`.

## The Seam Law for Web Code (Highest Priority — mirrors the engine's leakage canary)
- **The web stack is an `onramp/` peer and obeys the one-way seam.** It **writes** captured data legs
  to `data/raw/` and reads its own working data from there. It **never** reads `data/_truth/`, never
  reads the engine's `data/interim/` or `data/processed/`, and **never imports from `forecasting/`**.
  The authority is `data/CONTRACT.md`; the law is `.claude/rules/01-data-ingestion.md`.
- **All seam writes pass through `schemas/`.** Every row written to `data/raw/` is validated against
  the shared definitions in `schemas/seam.py` (`BomRow`, `SalesExportRow`, …) *before* it touches the
  store — the same head-chef gate the CLI export already uses. No hand-rolled CSV/Parquet writes that
  bypass the schema.
- **Structural enforcement.** The cross-module boundary test (`tests/test_module_boundaries.py`)
  already asserts `onramp/` never imports `forecasting/` and never references a `_truth` path; it must
  keep passing as web code lands. When boundary rules proliferate, migrate it to import-linter (the
  switch-trigger note in `data/CONTRACT.md`).

## Storage — DuckDB-over-Parquet (the decided shared store)
- **The store is DuckDB-over-Parquet** (`docs/common_base_reconciliation.md`, decided 2026-06-25). The
  `data/raw/**` files are the durable, diffable, firewall-enforcing artifact; DuckDB is the query
  layer the app opens over them. The website's persistence and the engine's input are the **same
  artifact**, not two stores.
- **The on-ramp owns its own store helper.** Because no peer may import the other, the on-ramp gets
  its own thin DuckDB access module (write Parquet to `data/raw/`, read its own files back). It does
  **not** import the engine's future `forecasting/src/data/store.py`. The shared thing is the files +
  `schemas/`, never the helper code. A little duplicated glue is the price the no-coupling rule charges.
- **The store helper refuses non-`raw` globs.** The on-ramp's helper opens only `data/raw/**`. It
  must be structurally incapable of registering a `_truth/**`, `interim/**`, or `processed/**` path.
- **No premature server-class DB.** DuckDB is embedded/in-process — correct for a thin, essentially
  single-tenant tool. A hosted, many-tenants-writing-concurrently service is the explicitly-deferred
  "server-class DB" decision (`common_base_reconciliation.md` §6.6); do not stand one up without a
  recorded, gated decision. Prefer Parquet over CSV for anything but tiny seed tables (types survive).

## Layering — Compute Stays Pure
- **Three layers, one direction:** pure compute (`onramp/plate_cost/src/`) ← thin API/glue ←
  presentation (front end). Dependencies point inward; presentation never reaches past the API into
  the store, and the API never embeds business math the compute should own.
- **The compute must remain runnable and unit-testable without the web layer.** No web framework
  import inside `src/bom`, `src/pricing`, `src/report`. A web layer must never become the *only* way
  to run a plate-cost — the engine handoff and the test suite both depend on the pure path.
- **Typed contracts at every layer boundary.** Reuse the `schemas/` pydantic models as the wire
  contract where possible rather than inventing parallel DTOs that drift.

## Thin Product, Durable Slot (web edition)
- **Separate the durable chrome from the provisional product.** The onboarding/capture funnel, auth,
  the storage layer, and the transparency story are **durable** (they survive a product swap). The
  plate-cost-specific views are **provisional**. Do not weld the chrome to plate-cost specifics —
  structure components so a different on-ramp product could be dropped into the same shell.
- **Build the smallest dollar-legible slice first.** Per `website_vision.md` §8, W0 (a read-only
  reveal over existing `data/raw/`) is the honest next slice. Resist building the multi-tenant
  platform before discovery validates the product.

## Config, Secrets, and Environments
- **Secrets live in env/config, never in the repo.** Connection strings, API keys, OCR credentials →
  environment variables or an untracked config file. Never commit them; never ship them to the browser.
- **Deterministic where it matters.** Seed any stochastic component (`random_state=42` convention);
  pin dependency versions. Reproducibility is part of the trust story.

## The Gate Still Applies
- A new view that introduces a **data transform or decision logic** (a new derived metric, a new
  capture leg, a re-cost rule) is a new *step* and clears Gates 1–4 (`00-process.md`). Pure
  presentation wiring of an already-gated computation is mechanical and does not re-trigger the gate.
