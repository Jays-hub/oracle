# W1 Review — Capture funnel (self-serve POS + recipe upload)

Adversarial code review of on-ramp web phase **W1** against `onramp/plate_cost/docs/website_vision.md`
§8 (the W1 row) and the on-ramp contract (`onramp/README.md`). Read-only over the codebase; this file
is the one durable artifact. Reviewer ran the suite, lint, import-linter, and exercised the routes.

## Step 0 — What W1 had to deliver ("done when")

- **POS-export upload + recipe-confirmation workspace**, self-serve in the browser: a chef uploads a
  sales export and a recipe (BOM) sheet, reviews what was found, and confirms.
- **Writes the sales + BOM legs to `data/raw/` through `schemas/`** — the same head-chef validation
  gate the CLI export uses. This is the durable on-ramp funnel (vision §8 marks W1 **Durable**).
- **Seam-correct and uncoupled**: writes only `data/raw/`, never reads `_truth`/`interim`/`processed`,
  never imports `forecasting/`; all writes pass through `schemas/seam.py`.
- **Thin over pure compute**: capture logic lives in `src/`, framework-agnostic; the web layer is glue.
- **Explicitly out of scope for W1 (deferred to W2, per vision §8):** auth, single-tenant isolation,
  reading a tenant's own uploaded data back into the grid at `/`. Their absence is *by plan*, not a
  finding. The builder's log confirms this and `success.html` states the grid still shows sample data.

No spec/intent conflict found: the build matches the W1 slice as written. The one place the *code's
behavior* conflicts with the *product intent* is the sample-data banner (Finding 1) — reported first.

Diff base used: the uncommitted working tree. I verified the builder's characterization by diffing each
file. Confirmed W1's real surface = `src/capture/seam_upload.py`, `web/upload.py`, `web/app.py`
(new `/upload`+`/confirm`), `src/run.py` (refactored to the shared writer), the three new templates,
`test_seam_upload.py` + `test_web_upload.py`, `requirements*.txt`, progress log. The `base.html`,
`grid.py`, `web/compute.py`, `grid.html`, `test_web.py`, `W0.md` edits are prior W0-remediation
leftovers — **but note base.html's banner is inherited by W1's new pages, which is where it becomes
wrong (Finding 1).**

## Step 2 — Hunt-list verdicts

**Seam firewall (highest priority)**
- Writes only to `data/raw/` (`RAW_DIR`/`_RAW_DIR`), pinned by `assert RAW_DIR.parts[-2:] == ("data","raw")`
  and `test_raw_dir_invariant` — **pass / verified-by-running**.
- All seam writes go through `schemas/` (`BomRow`/`SalesExportRow`) before `to_parquet` — **pass**. No
  hand-rolled write bypasses the gate.
- Never reads `_truth`/`interim`/`processed`; never imports `forecasting/` — **verified-by-running**
  (import-linter: 2 contracts kept; boundary test green; I re-ran its AST/text scan against a *planted*
  `from forecasting… import` + `_truth` string and confirmed both are caught).
- Store/write helper structurally incapable of a non-`raw` path — **pass** (path is computed + asserted,
  not caller-supplied at the module level).

**Architecture & layering (05)**
- `src/capture/seam_upload.py` has no web-framework import — compute stays pure and unit-testable —
  **pass / verified** (import-linter + read).
- Dependencies point inward (compute ← `web/upload.py` glue ← templates); handlers are thin, business
  logic in `src/` — **pass**.
- Durable chrome vs. provisional views: capture funnel is built as the durable slot; not welded to
  plate-cost specifics — **pass**.
- No premature server-class DB; embedded Parquet writes only — **pass**.

**Front-end / UX trust (06)**
- False precision / non-reconciling numbers: **N/A for W1** — the new capture pages show only *counts*
  (dishes, recipe lines, sales rows, covers, period), no money figures. **pass** (nothing to reconcile).
- Unlabeled placeholder data: **fail** — the inverse problem: the chef's *real* data is labeled "Sample
  data — illustrative only, not your restaurant's numbers" (Finding 1).
- Provenance path: N/A (no derived money numbers on these pages).
- Tenant isolation: absent, **deferred to W2 by plan** — not scored as a W1 fail; see Step 0.
- Firewall/secret leakage to browser: none — **pass**. Error pages carry only a correlation id.
- Accessibility/responsiveness: `role="alert"`/`role="note"`, semantic `<dl>`, viewport meta present —
  **pass** (not deeply audited; no money figures to contrast-check here).

**Backend / API (07)**
- Boundary validation bypassed: no — every write re-validates through `schemas/` (incl. `/confirm`,
  which re-parses from scratch) — **pass / verified**.
- Error handling leak/crash: named errors, 4xx/503 + correlation id, no stack trace/path in responses —
  **pass** (`error.html` read; `/confirm` bad-base64 and re-validation paths return clean 400).
- Idempotent/atomic seam writes: **concern** — atomic *per file* but **not across the bom/sales pair**
  (Finding 3, verified by running).
- Hostile input / size limits: **concern** — `MAX_UPLOAD_BYTES` enforced on `/upload` only, not on the
  `/confirm` write path (Finding 2, verified by running).
- AuthN/Z: deferred to W2 by plan.
- Statefulness leaks: none — upload→confirm is genuinely stateless (base64 round-trip, re-validated) —
  **pass**.

**Software engineering**
- Tests are meaningful: they accumulate-all-errors, assert schema-valid round-trip, tamper-rejection,
  size boundary, isolation from real `data/raw/`. Good. One gap: the "atomicity" test only proves
  *per-file* atomicity and silently bakes in the cross-file mismatch (Finding 3).
- Typed contracts reuse `schemas/` (not parallel DTOs) at the seam — **pass**. `UploadSummary`/`DishRow`
  are presentation TypedDicts that never touch the seam — correct separation.

**Anti-drift**: W1 is on-ramp *function*, correctly scoped and thin. No multi-tenant platform, no heavy
client framework (server-rendered Jinja, no JS framework). No over-engineering flagged. No drift.

## Step 3 — Riskiest spots (looked deliberately, ran them)

1. **The base64 hidden-field round-trip (`/upload`→`/confirm`).** Ran it end-to-end. The stateless
   re-validation is sound (tamper test passes; I re-confirmed a `-999` count is rejected with a 400 and
   nothing is written). The real risk it *does* carry is size: the size check lives on the wrong side of
   the round-trip and the base64 inflation collides with a Starlette limit (Finding 2).
2. **The shared atomic writer (`write_seam_atomic`).** The per-file temp-then-rename is correct. The
   two-file transaction is not — a mid-write failure leaves a mismatched seam pair (Finding 3, reproduced).
3. **`normalize_name()`-derived seam ids.** Correct reuse of the one canonical key, but it keys the seam
   on a mutable display string (Finding 4 — known/deferred, low).

## Step 4 — Findings

```
[MAJOR] "Sample data — illustrative only" banner renders over the chef's OWN captured data
Location:       onramp/plate_cost/web/templates/base.html:13-15 (unconditional banner),
                inherited by web/templates/{upload,confirm,success}.html (new in W1)
What's wrong:   Every page that extends base.html shows the fixed banner
                "Sample data — illustrative only, not your restaurant's numbers". W1's new capture
                pages extend base.html, so the confirm page ("Here's what we found" + the chef's real
                dish names, covers, and period) and the success page ("N dishes and M covers … are now
                on record") both display that banner directly above the operator's own real data.
                Verified by rendering: the confirm page contains BOTH "Sample data — illustrative
                only, not your restaurant's numbers" AND the chef's real dish "Chef Marco Special".
Why it matters: W1 IS the durable trust funnel — its entire job is to make the operator believe the
                numbers we pulled from THEIR files. Telling them, at the exact confirm/save moment,
                that these are sample data and "not your restaurant's numbers" is a flat
                self-contradiction and a credibility leak. Rule 06 says label *sample* data as such;
                this is the inverse defect — real data mislabeled as sample. The banner was correct
                for the W0 grid (which does show shared demo data); it is wrong the moment a page shows
                the tenant's own capture. (The banner predates W1, but W1 is the phase that introduced
                pages where it is false — so it is W1's to fix.)
Fix:            Move the banner into an overridable Jinja block (e.g. {% block sample_banner %}) that
                only the W0 grid page fills, OR gate it on a context flag that the capture templates
                set false. The upload/confirm/success pages must not claim the operator's data is
                sample/illustrative.
Confidence:     High (rendered the confirm and success pages via TestClient and saw both strings)
```

```
[MINOR] Upload size limit is enforced on /upload but not on /confirm; base64 inflation + Starlette's
        1024 KB field cap make the two ceilings inconsistent and fail opaquely
Location:       onramp/plate_cost/web/app.py — MAX_UPLOAD_BYTES checked in upload_submit (lines 84-95)
                but NOT in confirm_submit (lines 118-161, which b64decode + parse + WRITE)
What's wrong:   /upload rejects a file > MAX_UPLOAD_BYTES (1,000,000 decoded bytes) with a friendly
                "too large" message. /confirm carries the original bytes as a base64 string (≈ ×1.33
                size) in a form field and applies NO size check of its own. Starlette 1.3.1 caps a
                single form field at 1024 KB, so /confirm is incidentally backstopped — but at a
                DIFFERENT, TIGHTER effective ceiling (~786 KB decoded) than /upload's 1 MB, and the
                failure surfaces as a raw JSON body, not the app's fail-legibly page.
                Verified by running: a 972 KB sales CSV (UNDER the app's own 1 MB limit) passes
                /upload and renders the confirm page, then /confirm returns HTTP 400 with body
                {"detail":"Field exceeded maximum size of 1024KB."}. Files in the ~786 KB–1 MB band
                pass review, then dead-end at confirm.
Why it matters: (a) The app's own hostile-input policy (rule 07: size-limit uploads) is not enforced on
                the endpoint that actually writes the seam — it relies on an incidental framework
                default. (b) A legitimately-app-sized upload can pass review and then fail to save with
                a machine-readable JSON blob, violating "fail legibly" (rules 06/07: a calm
                plain-language fallback, never a raw error). At W1's stated ~15-25-item scale (a few KB)
                this won't trigger in normal use — hence MINOR — but it is a real inconsistency and an
                opaque dead-end, and it resolves the builder's own open question (Reviewer Focus #1):
                the Starlette limit DOES exist and CAN reject a legitimately-sized confirm POST.
Fix:            Re-apply the MAX_UPLOAD_BYTES check on the decoded bytes in confirm_submit and return
                the same friendly 422 the upload path uses; size the check to account for the base64
                round-trip (or raise Starlette's field limit to match). Concept: never trust that a
                validation done at one entry point still holds at another endpoint that is directly
                reachable — /confirm can be POSTed to without ever visiting /upload.
Confidence:     High (drove /confirm at graduated sizes; captured the 400 + JSON body)
```

```
[MINOR] Seam write is atomic per file but not across the bom/sales pair
Location:       onramp/plate_cost/src/capture/seam_upload.py:199-216 (write_seam_atomic)
What's wrong:   write_seam_atomic writes bom.parquet, then sales_export.parquet, each via its own
                temp-then-rename. Each file is individually crash-safe (no torn file). But if the
                second write fails after the first succeeds, the seam is left with a NEW bom.parquet
                and the PRIOR sales_export.parquet — a mismatched pair that disagree about which
                dishes exist. Verified by running: seeded an old {OldDish} pair, then failed the
                sales write on a new {Burger} upload → bom.parquet = ['Burger'],
                sales_export.parquet = ['OldDish']. The existing test only asserts the sales file and
                temp files are absent; it does not assert bom.parquet rolled back (it doesn't).
Why it matters: The decision log and progress log present atomicity as a headline guarantee ("writes
                are atomic and idempotent"); that is true PER FILE, not for the seam as a unit. A
                consumer reading the pair between a failed confirm and the next successful one sees an
                inconsistent BOM/sales snapshot. Blast radius today is low (single-tenant, a retry
                self-heals, the engine does not yet consume real tenant data) — hence MINOR — but the
                claimed guarantee is stronger than what the code provides, which is exactly the kind of
                gap worth naming. Concept: multi-file consistency needs a transaction boundary; two
                independently-atomic writes are not jointly atomic.
Fix:            Stage BOTH temp files first, then do BOTH os.replace calls back-to-back (shrinks the
                inconsistency window to two near-instant renames), or write a single versioned/manifest
                snapshot the engine reads by version. At minimum, document that the pair is not jointly
                atomic and add a test asserting the intended post-failure state.
Confidence:     High (reproduced the mismatched pair by running)
```

```
[MINOR / known-deferred] Seam ids are derived from a mutable display name with no stability guard
Location:       onramp/plate_cost/src/capture/seam_upload.py:144-153 (dish_id/ingredient_id =
                normalize_name(name))
What's wrong:   dish_id/ingredient_id are casefold+strip of the display name. Two genuinely-distinct
                dishes whose names collide under that transform get the same id (different dish_name),
                and renaming a dish changes its id — the seam key is not stable identity. There is no
                check that a given dish_id maps to a single consistent dish_name/unit set.
Why it matters: The seam join becomes name-based, the exact fragility normalize_name exists to soften,
                not remove. The builder correctly flags this as the pre-existing issue in
                data/CONTRACT.md forward-note #4 and notes W1 adds a call site, not a new class of bug.
                Recorded here for completeness, not as a W1 regression.
Fix:            None required for W1; track under the CONTRACT's "stable item_id across the seam" note.
                If cheap, add a guard that flags two different names colliding to one id in one upload.
Confidence:     Medium (read + reasoned; consistent with the documented deferral)
```

```
[NIT] Import-time side effects and cosmetic row numbering
Location:       src/capture/seam_upload.py:39-41 (sys.path.insert on import); parse_*_csv line
                numbering enumerate(reader, start=2)
What's wrong:   Importing the pure compute module mutates sys.path as a side effect (consistent with
                the existing run.py pattern and contract-sanctioned for the platform-owned schemas
                import, but still a side-effecting import). Separately, error messages number rows as
                header=1 / data from 2, which will mis-cite the row if a CSV contains a quoted
                multi-line field.
Why it matters: Cosmetic; neither affects correctness of the seam write.
Fix:            Optional. Leave as-is or centralize the schemas bootstrap; note the row-number caveat.
Confidence:     Medium (read)
```

## Step 5 — Sign-off

**Rules:** No praise padding. Genuinely good, in one line each: compute purity and the shared-writer
refactor are clean; `/confirm` re-validating rather than trusting the round-trip is the right instinct
and is tested; the boundary firewall holds and its test has real teeth (I planted a violation against
its logic and it caught it).

- **VERDICT:** **Yes, with one MAJOR fix.** W1 meets its `website_vision.md` §8 acceptance criteria —
  self-serve upload → confirm → schema-validated atomic write of both seam legs to `data/raw/`, seam
  firewall intact, auth/isolation correctly deferred to W2. But the sample-data banner over the
  operator's own confirmed data (Finding 1) directly undercuts the trust the funnel exists to build and
  should be fixed before this ships to a real chef. Nothing here is a seam-firewall breach, a
  cross-tenant/engine leak, or a non-reconciling number, so no BLOCKER.
- **TEST + LINT (observed):** `make test` → **249 passed, 4 warnings** (pandas deprecation only), 6.0s.
  `make lint` (`ruff check .`) → **All checks passed**. `make import-lint` (`lint-imports`) →
  **2 contracts kept, 0 broken.** Boundary test `tests/test_module_boundaries.py` green, and verified
  to catch a planted `forecasting` import + `_truth` string.
- **TOP 3 FIXES (priority order):**
  1. Stop showing "Sample data — illustrative only, not your restaurant's numbers" on the
     upload/confirm/success pages (Finding 1). Make the banner an overridable block/flag.
  2. Enforce `MAX_UPLOAD_BYTES` on `/confirm` (decoded bytes) with the friendly 422, and reconcile it
     with the base64 inflation / Starlette 1024 KB field cap so a legit-sized file can't dead-end on an
     opaque JSON error (Finding 2).
  3. Make the seam write jointly atomic across bom + sales (stage both, then rename both), or document
     and test the non-atomic pair honestly (Finding 3).
- **WHAT I COULD NOT VERIFY (after trying):**
  - Real-browser rendering / responsiveness / WCAG-AA contrast on an actual tablet/phone — I rendered
    HTML via `TestClient` and read the CSS references but did not run a headless browser or a contrast
    checker. The capture pages carry no money figures, so the contrast-on-money rule doesn't bite here.
  - Behavior under a genuine concurrent double-confirm (two writers racing on the same `data/raw/`
    files) — single-tenant W1 doesn't exercise it, and it's W2's isolation concern; I reasoned about it
    but did not stress-test a race.
  - Whether `python-multipart==0.0.32` is the intended pin vs. the `>=0.0.9` floor in requirements.txt —
    both were added cleanly (no machine-local `file://` pollution, no secrets), lock is a single line.
- **SINGLE BIGGEST RISK:** The capture funnel — W1's whole durable purpose is to make an operator trust
  the numbers we pulled from their own files — greets them at the confirm-and-save moment with a banner
  saying those numbers are "sample data … not your restaurant's numbers," silently telling the chef not
  to trust the exact act we need them to trust.
