# W9 Adversarial Review — Multi-tenancy across the seam

Reviewer: web-reviewer (adversarial, read-only over code; Write scoped to this file only).
Date: 2026-07-16. Diff base: uncommitted working tree (`git diff`), per the build agent's note.
Acceptance criteria: `website_production_overview.md` §4 W9 row (the vision doc §8 defers W5–W10 to
that overview). On-ramp contract: `onramp/README.md`.

---

## Step 0 — What this phase had to deliver ("done when")

- **Physically partition the seam per tenant.** `data/raw/` stops being a flat file store and becomes
  a container of one subdirectory per `restaurant_id` (`data/raw/<restaurant_id>/…`) — a *gated,
  cross-peer* `data/CONTRACT.md` change coordinated across both peers (`onramp/plate_cost/src/store.py`
  + capture writers on the write side; `forecasting/src/data/loader.py`, `cleaner.py`,
  `simulate/generator.py` on the read/simulate side).
- **Make the store and every read/write path tenant-scoped.** Every `store.read_*` requires a
  `restaurant_id`; every web write threads `identity.restaurant_id`; the engine's default read path
  is repointed to a fixed sentinel tenant so the existing dollar-floor scripts keep working untouched.
- **Keep the seam firewall and all invariants intact.** `_truth/` still unreachable from `onramp/`;
  boundary tests still green; every seam write still through `schemas/`; compute stays pure.
- **Do it as forward infrastructure, not on the phase's own trigger.** W9's stated trigger ("a second
  real tenant") has not fired; Jay directed a speculative build with the guessed shape flagged.

**Spec conflict surfaced up front (protocol requires listing this first):** the §4 W9 row lists
**three** deliverables, and the third — *"stable `item_id` carried into the seam schemas"* — was **not
built**; it was moved to the "Explicitly Deferred" table. The docs are internally inconsistent about
this (§4 names it a W9 deliverable; §6 says item_id format is "seam-side confirmed in W9"; §3's PoC
table row 9 assigns it to "W6/W9"). The physical partition (the heart of W9, and what its trigger and
the CONTRACT forward note describe) is delivered; one named §4 sub-deliverable is not. See Finding 1.

---

## Step 2 — Hunt-list verdicts

**Seam firewall (highest-priority structural law):**
- On-ramp writes only `data/raw/`, reads only its own files: **PASS** (verified). `store.RAW_DIR` is
  still hard-wired to `.../data/raw`; only a *validated* tenant segment varies beneath it.
- `_truth/`/`interim/`/`processed/` never reachable from `onramp/`: **PASS (verified by running)** —
  `tests/test_module_boundaries.py` green; `lint-imports` reports "Contracts: 2 kept, 0 broken."
- All seam writes through `schemas/`: **PASS**. The three writers (`write_seam_atomic`,
  `write_price_observations_atomic`, `write_food_cost_atomic`) are unchanged and still build rows from
  `BomRow`/`SalesExportRow`/`PriceObservationRow`/`FoodCostRow`. W9 only appended a path segment.
- Store helper structurally incapable of a non-`raw` path: **PASS**. `tenant_raw_dir()` is the single
  place a caller string becomes a path; the regex rejects separators/`..` and `assert path.parent ==
  RAW_DIR` is the backstop.
- Firewall guard still fires one level deeper: **PASS (verified)**. `_assert_raw_only` now checks
  `Path(path).parent.name == "raw"`; `data/_truth/<x>` and bare `data/raw` are both refused
  (`test_rejects_non_raw_dir`, `test_rejects_bare_raw_dir_with_no_tenant_segment`).

**Architecture & layering:**
- Compute stays pure: **PASS**. No web import entered `src/`. The write-side compute
  (`seam_upload.py`, `invoice_upload.py`, `tenant_grid.py`) is genuinely untouched — it already took an
  opaque `raw_dir: Path`, so the web layer resolves tenancy once at the route boundary. This is the
  phase's cleanest structural win.
- Dependencies point inward; presentation doesn't reach past the API: **PASS**.
- No premature server-class DB: **PASS**. Still DuckDB-embedded over Parquet.
- Durable chrome vs. provisional product: **PASS**. Tenancy is durable-slot plumbing, not welded to
  plate-cost specifics.

**Front-end / UX trust:**
- False precision / non-reconciling numbers / provenance: **PASS** — W9 changed **no** display or cost
  math (the diffs to `dishes.py`/`insights.py`/`menu_prices.py`/`your_data.py` only thread
  `restaurant_id`). The W6 round-once-on-aggregate discipline is untouched.
- Tenant isolation: **CONCERN** — enforced server-side by threading `identity.restaurant_id`, and
  proven at the store/loader unit level, but **no end-to-end web test with two real accounts** proves
  request-path isolation (Finding 3).
- Firewall leakage to browser: **PASS**. The `FileNotFoundError` message uses `base_dir.name` (the
  tenant's own segment, not an absolute path) and is caught in routes before reaching the client.

**Backend / API correctness:**
- Boundary validation bypassed: **PASS**.
- Error handling leaks/crashes: **PASS**. New-tenant/empty-tenant reads degrade to `has_data=False`,
  not a crash (tenant dir simply doesn't exist → `FileNotFoundError` caught).
- Non-idempotent / non-atomic seam writes: **PASS**. Writers unchanged; still temp-then-rename, and the
  invoice `fcntl` lock is now per-tenant (correct — the lost-update race is scoped correctly).
- AuthN/AuthZ on every data path: **PASS**. `/insights`, `/your-data`, `/your-data/export/*` correctly
  moved from `require_login` (boolean) to `current_identity` so `restaurant_id` is actually available;
  all data routes reject an unauthenticated request with a 303 to `/login`.
- Hostile input: **CONCERN** — `tenant_raw_dir`'s validator has a trailing-newline hole (Finding 2).
- Statefulness leaks: **PASS**.

**Software engineering / tests:**
- Tests meaningful: **MOSTLY PASS**. `test_tenant_isolation_*` in `test_store.py` and `test_loader.py`
  genuinely write two tenants and assert reads don't cross — they would fail on a real leak. The write
  path is asserted tenant-scoped too (`test_web_upload.py` reads `tmp_path / "r1" / "bom.parquet"`).
  Gap: web-level two-tenant composition (Finding 3).
- Anti-drift: **PASS**. Speculative build is flagged as Jay-directed forward infra; scope was held
  tight (`_truth/` deliberately not dragged in — see Decision 3 verdict below); no framework or
  multi-tenant-platform gold-plating crept in.

**Reviewer focus areas the builder flagged:**
- **Decision 3 (`data/_truth/` not partitioned): PASS — the scope reading is correct.** W9's spec
  governs *the seam*, and `data/CONTRACT.md`/rule 01 define the seam as `data/raw/`; `_truth/` is
  scoring-internal to `forecasting/src/evaluate/` and named nowhere in the W9 row. For the single
  sentinel tenant that exists, the simulator writing raw to `data/raw/<sentinel>/` and truth to flat
  `data/_truth/` is internally consistent (the evaluate scripts read both by the same default), so
  there is **no live bug** — only the documented latent risk that a *second simulated* tenant would
  overwrite flat truth. Correctly left as a CONTRACT forward note.
- **Decision 2 (permissive slug vs. strict UUID): the permissive-vs-strict *judgment* is defensible**
  (the real threat at this boundary is traversal, not "must look like a UUID"; `restaurant_id` is
  always DB-issued in production) — **but the regex as written has a concrete anchoring defect**
  orthogonal to that judgment (Finding 2).

---

## Step 3 — Riskiest spots, and what I found when I looked

1. **`store.tenant_raw_dir()` — the one place a request-derived string becomes a filesystem path.**
   Ran it against `..`, `a/b`, `a\b`, null byte, empty, 65 chars, and a trailing newline. Traversal and
   over-length are correctly rejected; **a trailing `\n` is accepted** (Finding 2). Not a live traversal
   and not attacker-reachable today, but the function's whole stated job is hostile-input rejection.
2. **The firewall guard's move from `path.name` to `path.parent.name`.** Checked whether it opened a
   `_truth/` hole: it does not — `data/_truth` (parent `data`) and `data/_truth/<x>` (parent `_truth`)
   are both refused. The name-based whitelist keeps its pre-existing "any dir literally named `raw`"
   weakness, but that is not a W9 regression.
3. **Call-site completeness (the builder flagged a dropped signature change).** Grepped every
   `store.read_*`/`RAW_DIR`/`write_*_atomic` site in `src/` and `web/`: no zero-arg read and no bare
   `store.RAW_DIR` write remains outside docstrings. All signatures match call sites; the full suite
   agrees.

---

## Step 4 — Findings

```
[MINOR] "Stable item_id carried into the seam schemas" — a named W9 §4 deliverable — was deferred, not built
Location:       onramp/plate_cost/docs/website_production_overview.md §4 (W9 row) vs. W9 decision log
                "Explicitly Deferred" table; schemas/seam.py (unchanged this phase)
What's wrong:   The W9 acceptance row lists three deliverables; the third ("stable item_id carried into
                the seam schemas") was moved to the deferred table. The seam still joins on a
                name-derived key (normalize_name), which is the fragile pattern the item_id work exists
                to retire. The docs contradict themselves on whether this is a W9 item (§4 says yes;
                §6 says "seam-side confirmed in W9"; §3 says W6/W9), so this is at least an unresolved
                spec ambiguity the phase closed over rather than reconciled.
Why it matters: A phase's review closes on whether it met its acceptance criteria. Silently dropping a
                named sub-deliverable — even a defensible one — means "W9 done" and "W9 spec" no longer
                agree, and the next reader can't tell deferral-by-decision from oversight. The concept:
                acceptance criteria are a contract; when you can't meet one clause, the honest move is
                an explicit, accepted amendment, not a quiet reassignment.
Fix:            Either (a) reconcile the three docs so exactly one says where stable item_id lands and
                have Jay consciously accept the deferral, or (b) build the item_id seam-schema change as
                part of closing W9. (a) is the smaller, honest step given the partition is the real W9.
Confidence:     High  (verified against the spec text and the schemas/ diff — no item_id field was added)
```

```
[MINOR] Path-safe-slug validator accepts a trailing newline (Python `$` vs `\Z`/`fullmatch` gotcha)
Location:       onramp/plate_cost/src/store.py:43 (_RESTAURANT_ID_PATTERN) + tenant_raw_dir()
What's wrong:   The pattern is re.compile(r"^[A-Za-z0-9_-]{1,64}$") used with .match(). In Python's
                default (non-MULTILINE) mode, `$` matches at end-of-string OR just before a trailing
                newline — so "abc\n" MATCHES. Verified by running: 'abc\n' -> ACCEPTED (while 'good\nbad',
                '..', 'a/b', null byte, and 65 chars are all correctly rejected). A restaurant_id of
                "abc\n" would resolve to a directory literally named "abc\n".
Why it matters: The function's documented purpose (and the CONTRACT's claim) is "keep an arbitrary
                caller-supplied string from ever becoming a traversal ... hostile until validated." A
                validator that its own docstring sells as the hostile-input gate should not have a hole,
                even a benign-looking one. Consequence today is LOW — restaurant_id always originates
                from identity.restaurant_id (a DB-issued UUID hex), so the newline is not reachable by an
                attacker at this boundary — but that is the *architecture* defending it, not the
                *validator*, which is exactly the coupling the validator exists to remove. The concept:
                for whole-string validation always use re.fullmatch() (or anchor with \Z, not $), because
                $ is line-end, not string-end.
Fix:            Use re.fullmatch(_RESTAURANT_ID_PATTERN, restaurant_id) or change the anchor to \Z. Add
                "abc\n" to test_tenant_raw_dir_rejects_path_traversal so the gotcha can't silently return.
Confidence:     High  (reproduced directly: the compiled pattern accepts 'abc\n')
```

```
[MINOR] No end-to-end web-level two-tenant isolation test — the phase's whole promise is untested at the request boundary
Location:       onramp/plate_cost/tests/test_web_auth.py / test_web_dishes.py (no two-account case)
What's wrong:   Isolation is proven at the store (test_store.py) and loader (test_loader.py) unit level,
                and the write path is asserted to land under tmp_path/"r1"/. But no test creates two real
                accounts (A and B), seeds each tenant's data/raw/<id>/, and asserts B's /your-data,
                /dishes, or /your-data/export/* can never surface A's rows. The composition
                (session -> identity.restaurant_id -> store) is the actual thing W9 makes "true by
                construction," and it is the layer with the most moving parts.
Why it matters: A store unit test cannot catch a route that accidentally passes a constant, the wrong
                identity field, or an un-scoped read — precisely the regression class this phase exists
                to make impossible. "Isolation by construction" deserves a construction-level regression,
                not only a component-level one. The concept: test at the seam where the guarantee is
                actually composed, not only where a single piece of it lives.
Fix:            Add one test: seed accounts A and B, seed distinct BOM/sales under each tenant dir, log in
                as B, assert B's /your-data covers count and /dishes reflect B's data and never A's.
Confidence:     High  (searched the suite; the two-account cases that exist are password-reset, not
                seam-isolation, tests)
```

```
[NIT] Security-relevant invariants are `assert` statements (stripped under `python -O`)
Location:       onramp/plate_cost/src/store.py:34, :57, :72 (RAW_DIR invariant; path.parent==RAW_DIR;
                filename traversal guard)
What's wrong:   The path-escape backstop and the bare-filename traversal guard are `assert`s, which are
                removed when Python runs with -O/-OO.
Why it matters: LOW in practice — each assert sits behind a real guard that is NOT an assert (the regex
                ValueError for the id; a hardcoded literal filename for the reader), so -O removes only
                defense-in-depth, not the primary defense. Still, a firewall backstop that vanishes under
                an optimization flag is worth knowing about. The concept: never let a security check be an
                assert if it is the *only* thing standing between input and a path.
Fix:            If these are meant as real guards, convert to explicit `if … raise`. If they are only
                belt-and-suspenders (they are), a one-line comment saying so is enough.
Confidence:     High  (assert semantics under -O are language-defined)
```

Positive, stated once (no padding): the write-side compute needing zero changes because it already took
an opaque `raw_dir: Path` is the layering paying for itself, and the self-caught `backup.py` regression
(flat `iterdir()` would have silently backed up nothing post-W9) with its own regression test is exactly
the "find the defect the seam-shape change downstream-breaks" instinct this review hopes to see.

---

## Step 5 — Sign-off

**VERDICT:** **Yes, with one documented scope deferral to consciously accept.** W9's core acceptance
criteria in `website_production_overview.md` §4 — physical per-tenant partitioning of `data/raw/`, a
tenant-scoped store + capture writers, a coordinated cross-peer CONTRACT change, the firewall and
boundary invariants held — are met and verified by running. The one gap is that the §4 row's third
named clause, "stable `item_id` carried into the seam schemas," was deferred rather than built (the docs
are self-contradictory on whether it belonged to W9). That is a completeness/spec-reconciliation issue,
not a correctness or firewall failure.

**TEST + LINT (observed, not trusted):**
- `pytest -q` (repo-root, `restaurant-dev` env): **621 passed, 4 warnings in ~18s.** Matches the
  builder's claim.
- Boundary + isolation + backup subset run explicitly: **36 passed** (`tests/test_module_boundaries.py`,
  `test_store.py`, `forecasting/tests/test_loader.py`, `test_backup_script.py`).
- `ruff check .`: **All checks passed.**
- `lint-imports`: **Contracts: 2 kept, 0 broken** (the onramp↔forecasting no-coupling contract and the
  engine model-path no-truth-import contract both hold).

**TOP 3 FIXES (priority order):**
1. Reconcile the item_id spec across §3/§4/§6 and have Jay explicitly accept the deferral (or build it)
   — so "W9 done" and "W9 spec" agree (Finding 1).
2. Change `tenant_raw_dir`'s `.match(... $)` to `re.fullmatch`/`\Z` and add the `"abc\n"` test case
   (Finding 2).
3. Add one end-to-end two-account web test proving request-path tenant isolation (Finding 3).

**WHAT I COULD NOT VERIFY even after trying:**
- The `data/_truth/` overwrite risk under a *second simulated* tenant is real but unreachable to
  exercise today (nothing simulates two tenants), so I confirmed it by reading the generator's flat
  `truth_dir` default, not by running a two-tenant simulation. The single-tenant path is verified
  consistent.
- Behavior against *real* pre-existing flat `data/raw/` files: the store is empty on disk (only
  `.gitkeep`), so I could not observe what happens to legacy flat files (they would become invisible to
  the tenant-scoped readers). Moot today per the builder's confirmed "empty store" assumption, but there
  is no migration path if that assumption were ever false in a deployed environment.
- I did not stand up the live server; route behavior was verified via the existing `TestClient` suite
  and by tracing `identity.restaurant_id` through every touched call site, not by manual HTTP.

**SINGLE BIGGEST RISK:** Tenant isolation is real and correct in the store, but its request-boundary
composition (authenticated session → `restaurant_id` → scoped read) rests on every route threading the
right id with only unit-level proof underneath — so the one thing most likely to be silently wrong later
is a future route added without that end-to-end regression to catch an un-scoped or mis-scoped read.
