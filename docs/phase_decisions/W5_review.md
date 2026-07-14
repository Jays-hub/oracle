# W5 Adversarial Review — the designated app DB + real identity

**Reviewer:** web-reviewer (adversarial, read-only over code; Write scoped to this file only)
**Date:** 2026-07-14
**Branch:** `onramp/w4-transparency-and-bridge` (W5 = uncommitted working tree on top of `24ddabe`)
**Diff base used:** the working tree as it stands (all `git status --short` entries treated as W5's
content — there is no prior W5 commit to diff against). Cross-checked against
`docs/phase_decisions/W5.md` (builder's decision log) and the `docs/progress_log.md` `[built]` entry.

**Acceptance criteria:** `website_production_overview.md` §4 (W5 row) + §2/§5 invariants, read alongside
`onramp/README.md` and rules 05/06/07.

---

## Step 0 — What W5 had to deliver (restated)

- **Stand up an on-ramp-private application database** (SQLAlchemy + Alembic, SQLite via
  `ONRAMP_DATABASE_URL`), separate from the seam, never under `data/`.
- **Replace the placeholder identity:** retire W2's single env credential (`ONRAMP_AUTH_USERNAME` +
  SHA-256) and the `RESTAURANT_ID = "default"` constant with real `users`/`restaurants`/`memberships`,
  argon2 credentials, password reset, and revocable DB-backed sessions.
- **Move staged uploads server-side:** the W1–W4 hidden-base64-form-field round-trip becomes
  `staged_uploads` rows the confirm step references by opaque id.
- **Invite-only account creation** (a CLI, no public signup on localhost).
- **Invariants that must not move (§5):** the seam firewall stays intact, compute stays pure, thin
  controllers / validation at the boundary / secrets in env, and **single-tenant isolation is
  non-negotiable** (rule 06: "one restaurant must never see another's data").

**Conflict I have to surface first (Step 0 requires it).** `website_production_overview.md` §2.5 claims
the W5→W9 arc lets "**a second restaurant onboard without seeing or corrupting the first** (app-DB
tenancy from W5; physical seam partitioning … W9)." W5 *ships the ability to create multiple
restaurants* (the invite CLI takes `--restaurant`) but leaves every seam read and write global and
unscoped. So for the "seeing/corrupting" half, the code cannot honor §2.5 the moment a second account
exists — and W5's headline feature is what makes a second account exist. This is the review's central
finding (BLOCKER-1). The strict W5 *row* in §4 does not itself list seam isolation (that's W9), but rule
06 and §5.1 are non-negotiable invariants, and W5 **removed** the structural single-tenancy (one env
credential) that made W9's absence safe.

---

## Step 2 — Hunt list verdicts

**Seam firewall (highest priority)**
- onramp never imports forecasting / never references `_truth`: **PASS (verified by running)** —
  `make import-lint` → 2 contracts kept, 0 broken; `tests/test_module_boundaries.py` green; the AST/text
  scan covers the new `src/db`, `src/auth`, `web` files.
- All seam writes pass through `schemas/`: **PASS** — `/confirm` and `/invoice/confirm` re-parse and
  re-validate via `parse_*`/`BomRow`/`SalesExportRow`/`PriceObservationRow`; staging did not add a
  bypass.
- App DB is never the seam / never under `data/`: **PASS (verified)** — `engine.py` resolves under
  `onramp/plate_cost/instance/` (gitignored); `test_default_database_url_never_resolves_under_the_seam`
  passes.
- Store helper opens only `data/raw/**`: **PASS** — `src/store.py` hard-codes `RAW_DIR`, import-time
  assert, bare-filename-only reads.

**Architecture & layering (05)**
- Compute stays pure (no FastAPI in `src/bom|pricing|report`): **PASS**. `src/auth/service.py` and
  `src/capture/staging.py` are DB-aware but framework-agnostic — correct split; `web/auth.py` is the
  only HTTP/cookie layer.
- Dependencies point inward; no premature server-class DB: **PASS** (SQLite embedded, Postgres deferred
  to W7 and recorded).
- Durable chrome not welded to plate-cost: **PASS** (identity/storage are product-agnostic).

**Front-end / UX trust (06)**
- False precision / non-reconciling numbers / provenance: **N/A this phase** — W5 introduces **no new
  dollar figure, cost, or margin display** (counts only). Nothing to reconcile.
- Unlabeled sample data: **PASS** — confirm pages suppress the sample banner; the public grid keeps it
  (tested).
- **Tenant isolation: FAIL → BLOCKER-1 (verified by running).**
- Firewall/engine internals to browser: **PASS** (no `_truth`/engine leakage in markup).

**Backend / API (07)**
- Boundary validation bypassed: **PASS** (re-validation at confirm is intact and tested).
- Error handling leaks/crashes: **PASS** — calm `error.html` + correlation id; app runs non-debug so an
  unhandled DB error on `POST /login` degrades to a generic 500 with no stack trace to the client.
- Idempotent/atomic seam writes: **CONCERN (LOW-1)** — staged-upload consume has a check-then-set
  TOCTOU window; invoice append is not idempotent under a genuine concurrent double-submit.
- AuthN/AuthZ on every data path: **FAIL for the seam path (BLOCKER-1)**; staging AuthZ (user-scoped)
  is correct; login timing enables enumeration (MINOR-1).
- Secrets in env: **PASS** (argon2 defaults, random tokens, `ONRAMP_DATABASE_URL`); reset token logged
  (LOW-2).
- Hostile input: **PASS** (size caps re-applied at confirm, files re-parsed).
- Statefulness leaks: **PASS / improved** — staged payload and sessions now live in the store, not
  process memory.

**Software engineering**
- Tests meaningful: **mostly PASS**, with **MINOR-2** (suite builds schema via
  `Base.metadata.create_all`, not the migration — model/migration drift is largely uncaught) and a
  missing test for the DB-outage gate behavior.
- Typed contracts reuse `schemas/`: **PASS**.
- Anti-drift: **PASS** — the identity machinery is sanctioned durable-chrome per the recorded
  2026-07-13 map, not drift.

---

## Step 3 — Riskiest spots I looked at deliberately

1. **The seam read/write path under real multi-tenancy** (`web/app.py` `your_data`/`your_data_export`/
   `confirm_submit` + `src/store.py`). This is where W5's new "real restaurant_id" meets W2–W4's global
   seam. It is the source of BLOCKER-1 — verified by running two accounts against one store.
2. **The staged-upload single-use / AuthZ logic** (`src/capture/staging.py::take_staged_upload`).
   Correct on ownership + kind + expiry + single-use for the sequential-replay case (tested). The only
   residual is the concurrent-double-submit TOCTOU (LOW-1).
3. **The migration vs. ORM source of truth** (`migrations/versions/0001_initial_schema.py` vs.
   `src/db/models.py`). Columns match today (autogenerated), but the test guard is weaker than the
   decision log claims (MINOR-2).

---

## Step 4 — Findings

```
[BLOCKER] Cross-tenant data leak + exfiltration: a logged-in restaurant sees and downloads another restaurant's captured data
Location:       onramp/plate_cost/web/app.py — your_data() (L213–234) and your_data_export() (L237–267);
                confirm_submit()/invoice_confirm_submit() seam writes (L376, L482) to the global store.RAW_DIR;
                root cause: Identity.restaurant_id (src/auth/service.py L44) is carried but never used to scope
                any src/store.py read (read_bom/read_sales/read_price_observations are global, unparameterized).
What's wrong:   W5 replaces W2's single env credential (structurally ONE tenant) with real multi-account
                creation (the invite CLI's --restaurant, the restaurants/memberships tables), but the seam
                (data/raw/) and every read of it stay global. I created two accounts (Restaurant A, Restaurant
                B), seeded the shared store with A's captured data, logged in as B, and B's /your-data showed
                A's cover count (999); B's GET /your-data/export/bom downloaded A's full BOM CSV including A's
                dish name. Confirmed by running. The confirm writes are also global, so B's upload would
                overwrite A's bom.parquet/sales_export.parquet ("corrupting the first").
Why it matters: This is the exact thing rule 06 calls non-negotiable ("one restaurant must never see another's
                data"), and website_production_overview.md §2.5 claims the W5 arc delivers ("a second restaurant
                can onboard without seeing or corrupting the first"). The code cannot honor either once two
                accounts exist. The concept: tenant isolation must be enforced *server-side at the data layer*
                (scope every fetch by the authenticated tenant) — carrying restaurant_id on the session is not
                isolation until a query actually filters on it. Before W5 this leak was impossible (you could
                not create a second tenant); W5 opened the door (multi-account) without adding the lock (scoped
                reads / seam partitioning), so this is a phase-introduced regression, not merely "W9 isn't built
                yet." It is dormant only for as long as exactly one account is ever created — an unenforced
                convention, not a control — and it becomes unavoidable at W6 (per-tenant costed views over a
                still-global seam, since W9 lands after W6).
Fix:            Pick one for W5, before W6: (a) enforce single-tenant at the app-DB layer — create_account
                refuses a second restaurant (raise ValueError) until W9 lands, making the "one tenant" assumption
                a real constraint; or (b) bring the W9 scoping forward far enough to be safe — a per-tenant
                subdirectory under data/raw/ keyed by restaurant_id, wired through store.RAW_DIR and the capture
                writers (this is the cross-peer change §4 defers, so (a) is the thinner W5-appropriate choice).
                At minimum, the "one tenant until W9" assumption must stop being satisfiable-by-accident and the
                overview §2.5 wording must be corrected to not claim W5 delivers cross-tenant safety.
Confidence:     High (ran it: two accounts, one shared store, B read and exported A's data)
```

```
[MINOR] Login timing enables account enumeration despite the docstring's claim it cannot
Location:       onramp/plate_cost/src/auth/service.py::authenticate (L73–84)
What's wrong:   On an unknown email, authenticate() returns None before ever calling verify_password (argon2).
                On a known email with a wrong password, it runs argon2 (~tens of ms). The response/message is
                identical either way (good), but the *timing* is not — an attacker can distinguish "email exists"
                from "email does not" by latency. The docstring asserts it "never distinguishes why … so a login
                form can't be used to enumerate accounts," which the timing channel contradicts.
Why it matters: User-enumeration is a real pre-auth information leak once the app is reachable (W7). The concept:
                enumeration resistance requires *constant work* on both branches, not just an identical message —
                the classic fix is to verify against a dummy argon2 hash when the user is absent. Low today
                (localhost, invite-only), but the docstring overstates the guarantee, which is how a real gap
                survives to hosting.
Fix:            When the user/credential is absent, still run verify_password against a fixed dummy argon2 hash
                (discard the result) so both paths pay the same KDF cost; soften the docstring to "identical
                response" rather than "cannot enumerate." Note it as a W7 hardening item.
Confidence:     High (control-flow is unambiguous; argon2 vs. early-return timing gap is inherent)
```

```
[MINOR] Migration/ORM drift guard is weaker than the decision log claims
Location:       onramp/plate_cost/tests/conftest.py (L28, Base.metadata.create_all) vs.
                tests/test_db_engine.py::test_alembic_upgrade_head_creates_all_w5_tables (checks table NAMES only)
What's wrong:   The whole suite builds its schema from the ORM models via create_all, not from the Alembic
                migration. Only one test runs the real migration, and it asserts only that the six table *names*
                exist — not columns, indexes, or constraints. So if a future model gains a column without a
                matching migration (or vice versa), every test still passes (they use create_all) while
                production `make migrate` produces a schema missing the column → runtime failure. The decision
                log's claim that this setup "keeps schema and code from drifting silently" holds only for table
                existence.
Why it matters: The migration is the production schema of record; the tests validate a different (ORM-derived)
                schema. That is precisely the drift the ORM+migration split is supposed to prevent. Today there
                is no drift (0001 was autogenerated and matches models — I diffed them), so this is about the
                guard, not a present bug.
Fix:            Add one test that asserts the migrated schema equals Base.metadata — e.g. run `alembic revision
                --autogenerate` (or alembic.autogenerate.compare_metadata) against a migrated throwaway DB and
                assert it produces an empty diff. Cheap, and it makes the "no silent drift" claim true.
Confidence:     High (read both; ran the suite; confirmed conftest uses create_all)
```

```
[MINOR] The decision log's "Reviewer Focus Area #1" (DB-outage on the real gate) does not match the shipped code
Location:       onramp/plate_cost/web/auth.py::_identity (L36–49), used by is_authenticated, require_login,
                AND current_identity
What's wrong:   W5.md's Key Design Decision and Reviewer Focus Area #1 state that is_authenticated() swallows
                DB errors but require_login/current_identity "do not" (let SQLAlchemyError propagate to a generic
                500). The shipped code routes all three through _identity(), which catches SQLAlchemyError and
                returns None. So a DB outage on the real gate yields a calm redirect to /login, not a stack trace
                — the *safer* behavior, but the opposite of what the builder's own briefing (the durable record
                Jay reads) describes.
Why it matters: The briefing asks the reviewer to scrutinize a risk that the code has already eliminated, and it
                misdescribes a security-relevant failure mode. A future maintainer trusting the log might "fix"
                the non-existent propagation and reintroduce a crash path. Answer to the focus area: moot —
                behavior is fail-closed and legible everywhere. (Note the corollary: POST /login on a dead DB is
                still an unhandled 500, but non-debug FastAPI leaks no trace, so rule 06 holds.)
Fix:            Correct W5.md to match the code (both the Key Design Decision and Focus Area #1), and add one
                test that monkeypatches resolve_session to raise SQLAlchemyError and asserts a protected route
                303-redirects to /login rather than 500-ing.
Confidence:     High (read the code path; it is unambiguous)
```

```
[LOW] Staged-upload consume is a check-then-set TOCTOU; invoice re-write is not idempotent under it
Location:       onramp/plate_cost/src/capture/staging.py::take_staged_upload (L60–71)
What's wrong:   take_staged_upload reads the row, checks consumed_at is None, then sets it and commits — no
                atomic guard (no SELECT…FOR UPDATE / conditional UPDATE … WHERE consumed_at IS NULL). Two
                genuinely concurrent /confirm POSTs with the same id could both pass the check before either
                commits. bom_sales seam writes are full REPLACE (double-write = same result, harmless), but
                /invoice/confirm APPENDS (write_price_observations_atomic), so a raced double-consume would
                duplicate price rows in data/raw/price_observations.parquet.
Why it matters: The single-use property that stops a replayed confirm from re-writing the seam holds for the
                common *sequential* replay (tested), but not a true concurrent double-submit. Low today
                (single-process SQLite serializes writes; requires the same user double-firing simultaneously),
                but worth closing when hosting/concurrency arrives (W7).
Fix:            Make consumption atomic: an UPDATE staged_uploads SET consumed_at=… WHERE id=… AND consumed_at IS
                NULL and treat rowcount==0 as "already consumed," instead of read-check-write.
Confidence:     Medium (inferred from code; not raced live — single-process SQLite makes it hard to trigger)
```

```
[LOW] Password-reset token (a 1-hour bearer credential) is written to the server log at INFO
Location:       onramp/plate_cost/web/app.py::reset_password_request_submit (L184)
What's wrong:   With no email transport yet, the raw reset token is logged (`_log.info(... /reset-password/%s ...)`).
                Anyone who can read stdout/log files can take over the account within the 1-hour TTL. Documented
                as a W7 deferral, and correct that it never appears in the HTTP response.
Why it matters: A reset token is a bearer credential; a live one in logs is a smaller version of "secrets in
                logs." Acceptable for a single-operator localhost dev tool, but it must not survive to any
                shared/hosted environment — flagging so it is not forgotten when W7 flips on real logging.
Fix:            Keep for localhost; add a W7 checklist item to remove/redact this the moment email transport or
                remote logging exists. Consider logging only a truncated fingerprint plus "full link emailed."
Confidence:     High (read it; it is the intended stand-in, correctly response-safe)
```

```
[LOW] Declared SQLite foreign keys are not enforced at runtime
Location:       onramp/plate_cost/src/db/models.py (ForeignKey on memberships/credentials/sessions/staged_uploads);
                onramp/plate_cost/src/db/engine.py (no PRAGMA foreign_keys=ON listener)
What's wrong:   SQLite ignores FK constraints unless `PRAGMA foreign_keys=ON` is issued per connection; SQLAlchemy
                does not enable it by default. So the declared FKs are documentation, not a runtime guard.
Why it matters: No consequence in W5 (no deletion path exists; resolve_session already tolerates a dangling
                user/restaurant). It bites at W10 (deletion/offboarding), where orphaned sessions/staged rows or
                partial deletes could occur silently. Concept: a constraint you declared but the engine does not
                enforce is a false sense of integrity.
Fix:            Add a `connect` event listener that runs `PRAGMA foreign_keys=ON` for SQLite connections (a few
                lines in engine.py), or explicitly record that FK enforcement is deferred to the Postgres swap /
                W10. Not required to close W5.
Confidence:     High (standard SQLite behavior; no PRAGMA present in engine.py)
```

```
[NIT] reset_password docstring "the token is cleared on success either way" is garbled
Location:       onramp/plate_cost/src/auth/service.py::reset_password (L183–186)
What's wrong:   The token is cleared only on the success branch (after the password check passes); an expired or
                mismatched token is left in place (harmless — expiry is checked). "on success either way" reads
                as self-contradictory.
Why it matters: Minor doc clarity only; the behavior is correct.
Fix:            Reword to "the token is cleared on success; a failed/expired attempt leaves it (unusable) until a
                new request overwrites it."
Confidence:     High
```

---

## Step 5 — Sign-off

- **VERDICT: No (not yet).** W5's *named* deliverables are all present and, in isolation, well-built:
  the app DB stands up correctly and is provably never under `data/`; argon2id + opaque, DB-hashed,
  revocable sessions are a genuine security upgrade over W2's signed cookie (logout revocation verified
  by running); staged uploads are server-side, single-use, and re-validated at confirm; the invite CLI
  and reset flow work end-to-end. **But the phase regresses a non-negotiable invariant** (rule 06 /
  §5.1 tenant isolation): by shipping real multi-account creation over a still-global seam with no
  scoping and no guard, it makes cross-tenant disclosure and corruption reachable through its own
  headline feature — demonstrated by running. That must be resolved (or explicitly fenced with an
  enforced single-tenant guard) before W6, which would otherwise turn this from dormant to live. The
  strict §4 W5 row does not list seam isolation, so if you accept the builder's "one tenant until W9"
  framing this is "Yes with a BLOCKER to fence"; I am calling it No because the guarantee is currently
  an unenforced convention, and §2.5's own wording claims a safety W5 does not deliver.

- **TEST + LINT (observed):**
  - `make test` → **468 passed, 4 warnings** (pre-existing pandas `select_dtypes` deprecation in
    `forecasting/tests`, unrelated to W5). Exit 0.
  - `make lint` (`ruff check .`) → **All checks passed.**
  - `make import-lint` (`lint-imports`) → **2 contracts kept, 0 broken** (engine truth-firewall +
    onramp/forecasting seam independence).
  - `tests/test_module_boundaries.py` → **green**, and it structurally covers the new W5 `.py` and
    `.html` files (would catch a planted `forecasting` import or `_truth` reference in them).

- **TOP 3 FIXES (priority order):**
  1. **Close the cross-tenant hole (BLOCKER-1).** Enforce single-tenant in `create_account` until W9,
    *or* scope seam reads/writes by `restaurant_id` now; and correct `website_production_overview.md`
    §2.5 so it does not claim W5 delivers cross-tenant safety.
  2. **Make the migration the tested schema (MINOR-2).** Add an autogenerate-produces-empty-diff test
    so model/migration drift can't pass CI silently.
  3. **Fix the enumeration-timing gap + docstring (MINOR-1)** and **correct the stale DB-outage
    decision-log section (MINOR-4)** — both are cheap and both remove a false claim from a record Jay
    relies on.

- **WHAT I COULD NOT VERIFY (even after trying):**
  - The **concurrent** staged-upload TOCTOU (LOW-1): single-process SQLite serialization makes a true
    race hard to trigger deterministically in a test harness; I reasoned it from the check-then-set
    code rather than observing a duplicate write.
  - **Live migration in production layout** (`make migrate` against a real `instance/onramp.db`): I ran
    the in-process migration test (green) and confirmed 0001 matches the models by diffing, but did not
    execute the `cd onramp/plate_cost && alembic upgrade head` Makefile target against a fresh
    filesystem DB.
  - **Real browser/tablet rendering** of the new templates (reset pages): I confirmed markup/semantics
    and that routes return 200, but did not render them in a browser or check WCAG-AA contrast (that
    pass is scheduled W8; W5 adds no money figures, so the money-contrast rule has nothing to bind to
    here).

- **SINGLE BIGGEST RISK:** W5 hands out real, separate restaurant accounts but every one of them reads
  and writes the *same* global `data/raw/` — so the instant a second account is created (which the
  invite CLI exists to do), one operator can see, download, and overwrite another operator's numbers,
  and nothing in the phase prevents reaching that state.
