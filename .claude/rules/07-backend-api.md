---
paths:
  - "onramp/**/*.py"
  - "onramp/**/api/**"
  - "onramp/**/server/**"
  - "onramp/**/routes/**"
---
# Backend & API Rules (the on-ramp service layer)

**Scope.** The on-ramp's backend/API — the thin service layer between the front end and the pure
compute + store. Architecture law is `05-fullstack-architecture.md`; the seam contract is
`data/CONTRACT.md`; shared schemas are `schemas/`.

## Validation at the Boundary (the head-chef gate)
- **Every inbound write is validated against `schemas/` before it is persisted or written to the
  seam.** Reuse `schemas/seam.py` (`BomRow`, `SalesExportRow`, …) — do not hand-roll parallel
  validation that drifts from the seam contract. Malformed data is rejected at the door, named
  (which dish, which field), never silently coerced.
- **Validate at the edges, trust the interior.** Once data is past the schema gate it is typed and
  trusted inside the service; re-validation belongs at boundaries (HTTP in, store write out), not
  scattered through business logic.

## The Seam-Write Discipline
- **The API is the on-ramp's writer to `data/raw/`.** It writes the captured legs (sales export, BOM,
  price observations) through the schema gate and **touches nothing else** in `data/`: never
  `_truth/`, never `interim/`/`processed/`, never another peer's paths. (`data/CONTRACT.md`,
  `01-data-ingestion.md`.)
- **Never import `forecasting/`.** The backend is an `onramp/` peer; coupling to the engine is a build
  failure (`tests/test_module_boundaries.py`). Data flows one way, through the seam.
- **Writes are atomic and idempotent where possible.** A re-submitted onboarding upload must not
  corrupt or duplicate the seam; prefer write-to-temp-then-rename or a versioned write over in-place
  mutation.

## API Design — Thin Over Pure Compute
- **Controllers stay thin.** Route handlers parse/validate input, call the pure compute in
  `onramp/plate_cost/src/`, and shape the response. Business math (plate cost, margins, the grid)
  lives in `src/`, never inlined in a handler — so it stays unit-testable and reusable by the engine
  handoff.
- **Typed, explicit contracts.** Request/response models are explicit (pydantic or equivalent),
  versioned where it matters, and reuse `schemas/` types rather than re-declaring them.
- **Stateless handlers.** Per-request state only; shared state lives in the store, not in process
  memory, so the service can be restarted or scaled without surprise.

## Error Handling
- **Friendly, typed failures — never a bare crash.** A bad reference (e.g. a recipe line pointing at
  an unknown `ingredient_id`) raises a named `ValueError`-class error the API turns into a clear 4xx,
  not a `KeyError` that 500s. (This is the exact hardening already applied in `src/pricing/compute.py`.)
- **Never leak internals to the client.** Error responses carry an operator-legible message and a
  correlation id; stack traces, file paths, SQL, and secrets stay server-side in logs.
- **Log the operationally meaningful events.** Seam writes, validation rejections, and fallbacks are
  logged with reason + timestamp (the same spirit as the engine's fallback logging in `04`).

## Security & Tenant Isolation
- **Secrets in env, never in code or the repo.** `DATABASE_URL`, keys, OCR credentials → environment.
- **AuthN/AuthZ on every data path.** Every request is authenticated and scoped to its tenant at the
  server; isolation is enforced in the backend, never delegated to the front end.
- **Input is hostile until validated.** Size-limit uploads, validate file types (POS exports,
  invoice images), and parse defensively. The capture funnel is the most-exposed surface.

## Testing
- **API and integration tests live beside the existing unit tests** (`onramp/plate_cost/tests/`).
  Cover: the schema gate rejects malformed writes; a seam write produces a `schemas/`-valid
  `data/raw/` artifact; the dangling-reference path returns a clean 4xx; tenant isolation holds.
- **The boundary test extends to backend code.** `tests/test_module_boundaries.py` must keep passing:
  no `forecasting/` import, no `_truth` path anywhere in `onramp/`.
- **Determinism.** Seed stochastic components (`random_state=42`); tests must not depend on wall-clock
  or network. Fixtures use the sample data already in `onramp/plate_cost/data/`.
