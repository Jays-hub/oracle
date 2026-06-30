# schemas/ — Shared schemas (the seam's teeth)

The **one place** a data shape shared across the two peers is defined, so both validate against the
same definition instead of two hand-kept copies. This is the structural enforcement behind the prose
in `../data/CONTRACT.md`.

## What lives here (when code lands)

- The schemas for the files crossing the seam (`../data/raw/`): `bom` / RecipeLine,
  `price_observations` / PriceObservation, `sales_export`, `eightysix_log`. As **pydantic** models or
  **pandera** schemas.
- Used by **both** peers: `onramp/` validates on **write** (don't emit a malformed export); the
  engine validates on **read** (fail loudly at ingestion, per `.claude/rules/01-data-ingestion.md`).

## What does NOT live here

- Engine-internal feature/model types (those stay in `forecasting/`).
- On-ramp-internal types (those stay in `onramp/plate_cost/`).
- Anything from `data/_truth/` — the truth schema is the simulator's private business
  (`forecasting/src/simulate/`), never a shared contract.

## Status (Phase 0)

`seam.py` now defines the **on-disk** shapes for the two files the on-ramp already writes across the
seam — `bom.csv` (`BomRow`) and `sales_export.csv` (`SalesExportRow`) — and `onramp/plate_cost`
validates against them **on write** (`onramp/plate_cost/src/run.py`). These were added when the first
file actually crossed the seam (the plate-cost BOM/sales export), per the trigger below — built thin.

Still deferred (Anti-Drift — added when they first cross the seam, not before):
`price_observations.csv` (on-ramp Phase 2 invoice ingestion) and `eightysix_log.csv` (the separate
86-tap habit). The column-level intent for all four is specified in
`../forecasting/docs/simulated_data.md`; the engine will validate **on read** against these same
definitions when its ingestion lands (Phase 1) — one definition, both peers.
