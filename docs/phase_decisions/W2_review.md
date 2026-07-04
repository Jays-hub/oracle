# W2 Adversarial Review — Account + persistence

**Reviewer:** web-reviewer (adversarial, read-only over code)
**Date:** 2026-07-04
**Phase:** W2 — Auth, single-tenant isolation, DuckDB-over-Parquet wired in, "your data" export
(`onramp/plate_cost/docs/website_vision.md` §8).
**Diff base:** uncommitted working tree on top of HEAD `9c92a65`. Scoped by `git status` (the 8
modified + 7 new paths listed there); confirmed against `docs/progress_log.md`'s newest entry.

---

## Step 0 — What this phase had to deliver ("done when")

- **Auth on every data-bearing route.** Anonymous callers must not reach `/upload`, `/confirm`,
  `/your-data`, or the exports. Enforced server-side, never client-side (rules 06/07).
- **Single-tenant isolation.** One restaurant never sees another's numbers. Per `website_vision.md`
  §9 this is explicitly *not* a mandate to build a multi-tenant partitioned store now — rule 05 calls
  the store "essentially single-tenant." So the honest reading is "gate every data path," not "build a
  `restaurant_id` partition."
- **DuckDB-over-Parquet store wired into the web layer** for the first time — `/your-data` is the first
  web caller of `src/store.py`, reading the operator's own captured seam legs back.
- **"Your data" export** — one-click download of the operator's own legs in the seam's open format.
- **Durable chrome, provisional views** — auth/storage/transparency are the durable parts; must not be
  welded to plate-cost specifics.

No spec-vs-code conflict on intent. The one place the code's language diverges from a rule is rule 06's
literal "every data fetch is scoped to the authenticated tenant" — see MINOR-1; the divergence is a
documented, defensible deferral, not a papered-over conflict.

---

## Step 2 — Hunt list verdicts

**Seam firewall (highest-priority structural law)**
- On-ramp writes only `data/raw/`, reads only its own files: **pass / verified-by-running.**
  `src/store.py` hard-codes `_RAW_DIR = parents[3]/data/raw`, asserts the invariant at import, takes a
  bare *filename* (rejects `/`, `\`, `..`), and binds the path as a parameterized DuckDB query.
  Structurally incapable of registering `_truth`/`interim`/`processed`.
- All seam writes pass through `schemas/`: **pass.** `write_seam_atomic` builds DataFrames from
  `BomRow`/`SalesExportRow.model_dump()` only; W2 added no new write path.
- No `forecasting/` import, no `_truth` path: **verified-by-running.** `lint-imports` → 2 contracts
  kept; `tests/test_module_boundaries.py` green. I re-implemented the test's AST/text detectors and fed
  them a planted `from forecasting.src...` import and a planted truth-path string — both are caught, so
  the test has teeth, not just a green tick. (The repo's own `deny_truth_access.py` hook also blocked my
  probe command — the firewall is live at the tooling layer too.)

**Architecture & layering (05)**
- Compute stays pure: **pass.** `src/auth/credentials.py` has no FastAPI import; the web glue
  (`web/auth.py`, `web/your_data.py`) holds no business math. Dependencies point inward.
- No premature server-class DB: **pass.** DuckDB embedded/in-process.
- Durable vs. provisional: **pass.** Auth/store/transparency are the durable parts; `/your-data`
  suppresses the sample banner (does not weld to the sample grid). Chrome is not plate-cost-specific.

**Front-end / UX trust (06)**
- False precision: **pass** — `/your-data` shows counts + period only, no dollar figures, so no
  cent-precision or margin-tier issue is introduced here. (The `/` grid is unchanged W0 code.)
- Non-reconciling numbers: **pass** — no cost/margin pair rendered on any W2 page.
- Real-vs-sample mislabel: **pass / verified.** `your_data.html` and `login.html` blank the
  `sample_banner` block, so real captured data is never stamped "illustrative"; only the W0 grid keeps
  the banner. Correct in both directions.
- Legible period: **concern (MINOR-2)** — the period renders as `2026-06-01 00:00:00`.
- Tenant isolation scoping: **concern (MINOR-1)** — auth-gated, but no fetch is scoped by tenant id.
- Firewall leakage to browser: **pass** — no `_truth`, engine internals, secrets, or other-tenant data
  in any payload; the password hash and session secret stay server-side/env.

**Backend / API correctness (07)**
- Boundary validation: **pass** — `/confirm` re-parses through `schemas/` before writing; never trusts
  the round-tripped hidden field.
- Error handling: **fail (MAJOR-1)** — a non-ASCII username crashes `/login` with a bare 500 instead of
  a clean 401. Elsewhere error handling is good (correlation ids, no traceback to client, legible 4xx).
- Atomic/idempotent seam writes: **pass** — stage-both-then-rename; full-replace matches single-tenant
  snapshot semantics.
- AuthN/AuthZ + secrets in env: **pass** (fails closed when unset; creds from env) — but see MAJOR-1.
- Hostile input: **pass** — bounded `read(MAX+1)` size guard, UTF-8-sig decode, per-row schema
  validation, base64 `validate=True`.
- Statefulness: **pass** — no per-request state in process memory; session in the signed cookie; upload
  round-trips bytes through hidden fields rather than server staging.
- CSRF: **concern (MINOR-3)** — no CSRF token on state-changing POSTs; relies on the framework-default
  `SameSite=lax`.

**Anti-drift**
- **pass.** No multi-tenant platform, no heavyweight client framework, no user table/OAuth built ahead
  of need. Single env credential + flat store is the thin slice `website_vision.md` §9 asks for. The
  "no physical partition" call is correctly scoped as a cross-peer, gated, future decision.

---

## Step 3 — Riskiest spots (looked deliberately, ran them)

1. **`verify_credentials` — the new auth compute.** This is the highest-risk new code: a security
   primitive on the most-exposed surface. Looked hard and ran it: the constant-time/fail-closed design
   is right for ASCII, but the raw username is fed straight to `hmac.compare_digest`, which raises on
   non-ASCII → the 500 in MAJOR-1.
2. **`store.py` wired into the web layer for the first time.** Risk: a path-traversal or wrong-layer
   read reaching the browser. Ran it: structurally locked to `data/raw/` by hard-coded dir + filename
   guard + parameterized query. Clean.
3. **`build_your_data_summary` — the new derived read of captured data.** Risk: type/format drift on
   round-trip and un-scoped reads. Ran it against the real `data/raw/`: counts are correct (11 dishes,
   41 lines, 787 covers) but the `date`→`Timestamp` round-trip surfaces a spurious `00:00:00`
   (MINOR-2), and the read is not tenant-scoped (MINOR-1).

---

## Step 4 — Findings

```
[MAJOR] Non-ASCII username crashes /login with a 500 instead of a clean 401
Location:       onramp/plate_cost/src/auth/credentials.py:42
                (username_ok = hmac.compare_digest(username, expected_username));
                unguarded caller onramp/plate_cost/web/app.py:113 (login_submit)
What's wrong:   hmac.compare_digest raises TypeError("comparing strings with non-ASCII
                characters is not supported") when either string argument contains a
                non-ASCII character. The submitted username is passed in raw. login_submit
                has no try/except around verify_credentials, so the TypeError propagates and
                FastAPI returns 500 Internal Server Error. Verified by running:
                POST /login {username:"café", password:"s3cret"} -> HTTP 500. (The password
                path is safe: hash_password() yields an ASCII hex digest before compare.)
Why it matters: Rule 07 mandates "friendly, typed failures — never a bare crash" and the auth
                form is called out as the most-exposed, hostile-until-validated surface. A login
                attempt with any accented character (a plausible operator name, or a trivial
                attacker probe) fails open into an unhandled 500 rather than the intended
                fail-closed 401. It also contradicts the module's own docstring promises: it is
                meant to *return False* for any bad credential and to be constant-time — a crash
                is neither (and is a loud behavior-oracle distinguishing "username contains
                non-ASCII"). No traceback leaks to the client (debug=False), so this is a
                robustness/contract bug, not a data leak. Concept: hmac.compare_digest is
                byte-oriented; on str it only accepts ASCII, so security-comparing raw
                user-controlled text is unsafe — compare fixed-width hex digests instead.
Fix:            Compare the *hash* of the username too, exactly as the password already does:
                hmac.compare_digest(hash_password(username), expected_username_hash) — both
                sides ASCII hex, non-ASCII can never raise. (Requires seeding a username-hash
                env var, or a normalize/encode step.) Minimal alternative: wrap the compare in a
                try/except that treats a TypeError as a non-match, or .encode() both operands to
                bytes before compare. Add a regression test feeding a non-ASCII username.
Confidence:     High (ran it end-to-end through the TestClient; got 500).
```

```
[MINOR] "Single-tenant isolation" is auth-gating only; no fetch is scoped to a tenant
Location:       onramp/plate_cost/web/your_data.py:33-54 (build_your_data_summary),
                :58-65 (exports); onramp/plate_cost/web/auth.py:19 (RESTAURANT_ID)
What's wrong:   Every /your-data read and export reads the entire flat data/raw/ with no tenant
                predicate. RESTAURANT_ID="default" is stored in the session but is only ever a
                presence marker (is_authenticated checks truthiness); it is never used to scope a
                read. Rule 06's literal "every data fetch is scoped to the authenticated tenant"
                is therefore not implemented — isolation today is "requires *a* valid session,"
                and there happens to be exactly one tenant's data physically present.
Why it matters: This is a documented, defensible deferral (website_vision.md §9 disclaims a
                multi-tenant build now; rule 05 calls the store "essentially single-tenant";
                CONTRACT.md carries the forward note; the single shared credential + full-replace
                writes mean only one tenant can ever exist). So it is NOT a leak today and I am
                not blocking on it. The risk to name loudly: the day a restaurant_id enters the
                seam without ALSO updating these reads to filter on it, this exact code will serve
                every tenant's data to any single login — the isolation is not structural, it is
                circumstantial (one-tenant store). This is the single thing to re-check when
                tenant #2 arrives, and the decision log correctly flags it as the phase's biggest
                architectural call.
Fix:            None required for W2. When the seam gains a restaurant_id, thread the session's
                tenant id into store.read_bom/read_sales as a WHERE predicate (or per-tenant
                subdir) in the same change — do not let the partition land without the scoped
                read. Consider a test asserting a read cannot return rows for another tenant id
                so the guarantee is enforced, not assumed.
Confidence:     High (traced every read; RESTAURANT_ID is never passed to a store call).
```

```
[MINOR] Transparency page shows a spurious "00:00:00" on a date-only field
Location:       onramp/plate_cost/web/your_data.py:53-54; rendered by
                web/templates/your_data.html:21 ("Period")
What's wrong:   SalesExportRow.period_start/period_end are pydantic `date`s, but written to
                Parquet and read back through DuckDB->pandas they come back as datetime64
                Timestamps, so str(min())/str(max()) yield "2026-06-01 00:00:00". Verified by
                running build_your_data_summary() against the real data/raw/: period_start ==
                "2026-06-01 00:00:00".
Why it matters: This is the trust/transparency surface — its whole job is "a chef looks and says
                'yes, that's about right.'" Rule 06 says speak the operator's language and keep
                money/figures calm and legible; a machine-formatted midnight timestamp on a plain
                date is exactly the kind of false-precision noise the precision discipline warns
                against. Not a wrong number, but a credibility paper-cut on the page that most
                needs to feel hand-checked.
Fix:            Format as a date: e.g. pd.to_datetime(sales_df["period_start"]).min().date()
                (or .strftime("%Y-%m-%d"), or "%b %-d, %Y" for operator-friendly "Jun 1, 2026").
Confidence:     High (ran it; saw the timestamp string).
```

```
[MINOR] No CSRF protection on state-changing POSTs; relies on the SameSite default
Location:       onramp/plate_cost/web/app.py:64-67 (SessionMiddleware config); forms in
                login.html, base.html (logout), upload.html, confirm.html
What's wrong:   /login, /logout, /upload, /confirm are all cookie-authenticated POSTs with no
                CSRF token. The only thing preventing a cross-site forged POST from carrying the
                session cookie is Starlette's default SameSite=lax on the session cookie — which
                is never set explicitly here, so the protection is an implicit framework default,
                not a stated decision.
Why it matters: SameSite=lax does block the classic cross-site auto-submitted POST, so real risk
                today (a single-operator tool bound to 127.0.0.1) is low. But leaning on an
                unstated default is fragile: if a future change sets same_site="none" for an
                embed, or a top-level-navigation CSRF vector is in scope, the funnel that WRITES
                the seam becomes forgeable. Concept: CSRF = a logged-in user's browser is tricked
                into sending an authenticated state-changing request; the defenses are a
                per-request token and/or SameSite cookies.
Fix:            Before any networked deploy, add a CSRF token to the POST forms (or a
                double-submit cookie), and set same_site explicitly rather than by default. No
                change needed for the current local-only reality, but record it as a gated
                pre-deploy item alongside the TLS/session-secret ones.
Confidence:     Medium (verified no token in forms and no explicit same_site; relied on
                documented Starlette default for the lax behavior rather than a live cross-origin
                test).
```

```
[MINOR] Ephemeral session secret + https_only=False — correctly deferred, flagged for the deploy gate
Location:       onramp/plate_cost/web/app.py:63 (secret fallback), :66 (https_only=False)
What's wrong:   Absent ONRAMP_SESSION_SECRET, a fresh per-process secrets.token_hex(32) is used,
                so every restart invalidates all sessions; https_only=False sends the session
                cookie over plain HTTP.
Why it matters: Both are acceptable and consciously chosen for today's single 127.0.0.1 dev
                process (builder flagged both). The note for the record: on any networked deploy,
                https_only=False makes the session cookie sniffable and the ephemeral secret means
                a horizontally-scaled or restarted process logs everyone out — both must flip
                before the app leaves localhost. This belongs on the same pre-deploy gate as
                W0_review.md's still-open hosting item.
Fix:            No change for W2. Gate: require ONRAMP_SESSION_SECRET and set https_only=True (and
                same_site) the moment a real host exists; consider failing startup if the secret
                is unset in a non-dev environment.
Confidence:     High (read the config; behavior is as the builder documented).
```

```
[NIT] CSV export performs no formula-injection neutralization
Location:       onramp/plate_cost/web/your_data.py:58-65 (to_csv)
What's wrong:   A dish/ingredient name beginning with = + - @ would be a live formula if the
                exported CSV is opened in Excel/Numbers.
Why it matters: Near-zero risk here: the data producer and consumer are the same single operator
                exporting their own upload, not an attacker feeding a victim. Noted only for
                completeness so it is a known, accepted tradeoff, not an oversight.
Fix:            If ever exporting to a third party, prefix at-risk cells with a quote or export
                Parquet. Not needed now.
Confidence:     High (self-export data flow; low consequence).
```

---

## Step 5 — Sign-off

- **VERDICT: Yes** — W2 meets its `website_vision.md` §8 acceptance criteria as scoped. Auth gates every
  data-bearing route (fails closed, env creds, server-side), the DuckDB store is wired into the web layer
  for the first time via `/your-data`, and one-click CSV export of the operator's own legs works. The
  "no physical multi-tenant partition" call is legitimately within §9's disclaimer and is documented as a
  gated cross-peer deferral. This is a *conditional yes*: MAJOR-1 (the non-ASCII `/login` 500) is a real
  defect on the auth path that should be fixed before the phase closes, but it does not fail the
  acceptance criteria (auth works for the ASCII credentials that are the actual usage).

- **TEST + LINT (observed, not claimed):**
  - `pytest -q` full repo: **295 passed, 4 warnings** (pre-existing pandas select_dtypes deprecation in
    `forecasting/tests`, unrelated to W2). On-ramp + repo-root subset: 151 passed.
  - `ruff check .`: **All checks passed.**
  - `lint-imports`: **2 contracts kept, 0 broken** (the onramp↔forecasting seam + engine truth-import
    contracts).
  - `tests/test_module_boundaries.py`: green, and confirmed to catch a *planted* forecasting import and a
    planted truth-path reference — not merely green.

- **TOP 3 FIXES (priority order):**
  1. MAJOR-1 — make `verify_credentials` non-ASCII-safe (hash/encode the username before
     `hmac.compare_digest`, or catch TypeError as non-match) so `/login` returns 401, not 500; add a
     non-ASCII-credential regression test.
  2. MINOR-2 — format the `/your-data` period as a date (drop the `00:00:00`) on the trust surface.
  3. MINOR-1 — leave the isolation deferral as-is, but when a `restaurant_id` enters the seam, land the
     tenant-scoped read in the *same* change; ideally add a test that a read cannot return another
     tenant's rows.

- **WHAT I COULD NOT VERIFY even after trying:**
  - The session-restart invalidation behavior of the ephemeral secret (no test restarts the process; I
    read the config and reasoned about it rather than killing/reviving a live server).
  - Real cross-origin CSRF behavior — I confirmed no CSRF token exists and no explicit `same_site` is set,
    and relied on the documented Starlette `SameSite=lax` default rather than a live cross-site POST.
  - Rendered accessibility/contrast and tablet/phone responsiveness of the new nav/login/your-data
    markup — I read the CSS and semantics (labels, `role="alert"`, autocomplete hints are present) but did
    not render in a browser at real widths or run a contrast/WCAG check on the money-adjacent chrome.

- **SINGLE BIGGEST RISK:** The auth primitive silently 500s on a non-ASCII username — the one piece of
  genuinely new security code in this phase mishandles the exact hostile/edge input rule 07 says the login
  surface must expect, and no test exercises it.
