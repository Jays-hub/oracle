# W4 Review — Transparency + Bridge (`/your-data` deepened)

Adversarial review of on-ramp web phase **W4**. Read-only over the codebase; this file is the one
durable artifact. Reviewer ran the suite, lint, import-linter, boundary test, and rendered the page
against seeded/edge states rather than trusting the diff.

Acceptance criteria: `website_vision.md` §8 row **W4** — "The full 'your data' transparency view and
the forecasting 'what's next' panel" (Durable framing, provisional content) — read with `onramp/README.md`
(the on-ramp contract) and rules `05`/`06`/`07`.

## Step 0 — What W4 had to deliver (in my words)

- Deepen `/your-data` from W2's counts-only state into the **full transparency view**: enumerate every
  captured seam leg (BOM, sales, **and** the invoice/price-history leg W3 added), state why each is held,
  and offer one-click CSV export of each in the seam's open format.
- Explain the **firewall in plain English** — the raw-data vs. hidden-oracle (`_truth`) split and today's
  honest one-tenant (login-only, not physically partitioned) posture — as a first-class surface, not fine
  print (vision §4, rule 06).
- Add the **forecasting "what's next" bridge panel** (vision §6): preview the prep-sheet payoff the captured
  data unlocks, without citing simulation-only dollar figures as this operator's numbers.
- Stay thin: no new route required by the spec ("panel", not "page"), no JS, seam-firewall intact, existing
  thin-glue/pure-compute layering preserved.

No spec-vs-code conflict at the level of intent. One judgment call (one page vs. two — see Step 2) is a
defensible reading; I concur it is not a defect. The real defects are in *how* the "leg exists
independently" design meets the template, and in error-handling consistency — below.

---

## Step 2 — Hunt-list verdicts

**Seam firewall (highest priority)**
- On-ramp writes only `data/raw/`, reads only its own files: **pass**. `src/store.py` hard-codes
  `RAW_DIR = parents[3]/data/raw`, asserts the invariant at import, and `_read_raw_parquet` takes a
  *bare filename* (rejects `/`, `\`, `..`) — structurally incapable of registering a `_truth/interim/processed`
  path. New `read_price_observations()` uses the same gate. **verified-by-running** (boundary test + import-lint).
- No `forecasting/` import, no `_truth` path in changed code/template: **verified-by-running**
  (`test_module_boundaries.py` 4 passed; import-lint 2 kept / 0 broken; I read all four changed files —
  none reference `_truth` or `forecasting`).
- Seam writes through `schemas/`: **pass** — W4 adds no write path (read + export only). Export dumps the
  operator's own already-validated leg back out as CSV. No hand-rolled seam write introduced.
- Boundary test would catch a planted `.py` violation: **pass**, but see LOW-1 — it scans `*.py` only, and
  W4 is the first phase to put firewall prose into an `.html` template the grep does not cover.

**Architecture & layering (05)**
- Compute stays pure; no web import in `src/{bom,pricing,report}`: **pass** (W4 touches only `web/` + a store read).
- Thin controller / glue split held: **pass** — `app.py` route stays ~3 lines; `web/your_data.py` owns the
  derived counts; template is presentation.
- Durable chrome vs. provisional product: **pass** — transparency/firewall/export are durable; no chrome welded
  to plate-cost specifics; no premature DB, no JS framework, no new CSS.

**Front-end / UX trust (06)**
- False precision / non-reconciling numbers: **pass (N/A)** — page carries only exact integer counts and dates,
  no dollar/margin figures, so the rounding/reconciliation rules don't bite here.
- Unlabeled placeholder data: **pass** — `{% block sample_banner %}{% endblock %}` correctly suppresses the
  sample banner; this is the operator's own data.
- Provenance path: **pass** — counts trace to exportable CSV of the same rows.
- Tenant isolation: **pass for today's posture** — every route gated by `require_login`; single flat tenant,
  stated honestly on the page itself (W9 defers physical partitioning). No client-side filtering.
- **Transparency completeness / honesty in an edge state: FAIL** — see MAJOR-1: the "only invoices captured"
  state renders "Nothing captured yet" and hides the invoice leg + its export link while the firewall
  paragraph on the same page asserts the operator uploaded "invoice prices."
- Accessibility/legibility: **concern (NIT)** — section headings styled with the muted `.page-meta` utility
  (contrast passes AA at ~5.4:1, but hierarchy is de-emphasized; see NIT-1).

**Backend / API (07)**
- Boundary validation bypassed: **pass** — no inbound write in W4.
- Error handling legible / no crash: **FAIL (MINOR)** — see MINOR-1: `/your-data` has no calm-fallback wrapper
  (unlike the `grid` and `insights` routes); W4's new unconditional price read broadens the bare-500 surface.
  No stack-trace/path leak in prod mode (**verified-by-running** — body is a bare "Internal Server Error").
- Idempotent/atomic seam writes: **pass (N/A)** — no write path.
- AuthN/AuthZ on the new export leg: **pass** — `/your-data/export/prices` added to the auth-redirect
  parametrize list and gated by `require_login`. **verified-by-running**.
- Hostile input / statefulness: **pass** — no new input surface; handlers stateless.

**Anti-drift**
- **pass** — W4 is thin: no new route, no JS, no new store, reused CSS classes. Bridge panel points at the
  moat without inflating the on-ramp (vision §6). No over-engineering; no chrome-welding.

---

## Step 3 — Where a subtle bug would hide (and what I found)

1. **The `has_data` gate vs. the "leg exists independently" claim.** The builder's headline W4 correctness
   feature is reading the price leg independently of BOM/sales so `has_price_data` is right even when
   `has_data=False`. The riskiest spot is whether the *template* honors that independence. It does not —
   all price display is nested inside `{% if summary.has_data %}`. Rendered the only-invoices state: the
   page contradicts itself. **This is MAJOR-1.**
2. **The new unconditional read at the top of `build_your_data_summary`.** `_price_leg_stats()` runs before
   the BOM/sales try/except and catches only `FileNotFoundError`. A corrupt/unreadable price parquet now
   500s the whole trust page — even when BOM/sales are fine, even in the nothing-captured display path.
   Rendered a corrupt parquet: bare 500, no calm fallback, no correlation id. **This is MINOR-1.**
3. **Firewall prose entering a template the boundary grep doesn't scan.** The structural `_truth` guard is
   `.py`-only. Clean today; latent gap tomorrow. **This is LOW-1.**

---

## Step 4 — Findings

```
[MAJOR] "Only invoices captured" state renders a self-contradicting trust page
Location:       onramp/plate_cost/web/templates/your_data.html lines 29-86 (the
                `{% if summary.has_data %}` gate) together with web/your_data.py
                build_your_data_summary()'s has_data=False return (lines 47-58)
What's wrong:   `has_data` is True only when BOM *and* sales exist. The price-leg ledger row, the
                price counts, and the "Download invoice history (CSV)" link all live *inside* the
                `{% if summary.has_data %}` block. `build_your_data_summary()` correctly computes
                `has_price_data`/`price_observation_count` independently and even returns them in the
                has_data=False branch — but the template throws that data away in that branch and
                renders the `{% else %}` "Nothing captured yet. Connect your data to get started."
                Meanwhile the always-shown firewall paragraph directly above asserts the operator
                uploaded "invoice prices." Reproduced: seed only price_observations.parquet (reachable
                — `/invoice/upload` enforces no BOM/sales-first ordering), hit /your-data:
                  status 200; "Nothing captured yet" = True; price ledger/export absent;
                  firewall text "invoice prices" present.
Why it matters: This is the on-ramp's one differentiator surface (vision §4/D, rule 06 "transparency is
                a first-class surface"). In this state the page (a) says both "here is the firewall
                protecting the invoice prices you uploaded" and "Nothing captured yet," and (b) fails
                its own headline promise — "export it any time" — because the invoice-CSV link is hidden,
                so the operator cannot export the invoice data they *did* upload from the page whose whole
                job is one-click export / no lock-in. The builder's decision log documents this exact
                scenario as "confirmed" handled and calls the independent read "correct even in the
                has_data=False branch"; the code delivers the computation but the template never displays
                it, so the claimed correctness does not reach the user. (Concept: a per-leg boolean is only
                as honest as the template branch that renders it — gating three independent legs behind one
                combined `has_data` flag collapses three states into two and loses the odd-one-out.)
Fix:            Give the price leg its own render gate independent of `has_data`. Minimal: render the
                "What we hold, and why" ledger row + the prices export link based on
                `summary.has_price_data` regardless of `has_data`, and make the `{% else %}`/empty branch
                reflect "invoices captured, no menu data yet" rather than a flat "Nothing captured yet"
                when `has_price_data` is true. (Alternatively, if only-invoices is deemed out of scope,
                stop computing/returning the price fields in the has_data=False branch and say so — but
                that contradicts the stated design intent.)
Confidence:     High (reproduced end-to-end with the TestClient).
```

```
[MINOR] /your-data lacks the calm-fallback wrapper its sibling render routes have; W4 widened the bare-500 surface
Location:       onramp/plate_cost/web/app.py your_data() lines 158-165 (and the new unconditional read
                in web/your_data.py _price_leg_stats() line 84-88; also your_data_export() lines 183-186)
What's wrong:   `your_data()` calls `build_your_data_summary()` with no try/except. The `grid` route
                (116-128) and `insights` route (390-403) both wrap their compute in try/except and return
                a calm error.html + correlation id + logged exception. W4 adds `_price_leg_stats()` as an
                *unconditional* read at the very top of `build_your_data_summary()`, catching only
                `FileNotFoundError`. A corrupt/unreadable price_observations.parquet raises a DuckDB
                IO/parse error (not FileNotFoundError) that propagates uncaught and 500s the entire trust
                page — even when BOM/sales are perfectly readable, and even in the nothing-captured path.
                Reproduced (valid bom/sales + a garbage price parquet, prod-mode client): status 500,
                body "Internal Server Error", no correlation id logged, no calm page. The export route
                has the same shape: it catches FileNotFoundError but not a corrupt-file read error.
Why it matters: Rules 06/07 require "fail legibly" — a calm plain-language fallback, never a broken screen,
                with a correlation id support can trace. The trust page is exactly where an ungraceful 500
                is most damaging, and it is now inconsistent with the two routes that already do this right.
                Good news, verified: FastAPI's default (debug off) returns a bare "Internal Server Error"
                with NO traceback/file-path in the body, so this is not a data leak — it is a
                legible-degradation + observability gap, not a secrets/firewall leak.
Fix:            Wrap `build_your_data_summary()` in the same try/except → error.html(503) + correlation-id
                log the grid/insights routes use (or catch non-FileNotFoundError inside `_price_leg_stats()`
                and degrade the price leg to "unavailable" while the rest of the page renders). Apply the
                same to the export route's corrupt-file path.
Confidence:     High (reproduced with raise_server_exceptions=False to emulate prod).
```

```
[LOW] Boundary _truth grep is .py-only; W4 is the first phase to put firewall prose in a template it doesn't scan
Location:       tests/test_module_boundaries.py test_onramp_never_references_truth_path (lines 58-64),
                which globs `*.py` only (via _py_files, rglob("*.py")); the new firewall prose lives in
                onramp/plate_cost/web/templates/your_data.html
What's wrong:   The structural guarantee the W4 decision log and the page copy both lean on ("an automated
                check in our build fails loudly if any code ever tries to cross that line") is enforced only
                over Python files. The template is clean today (I read it in full — no `_truth`), but a future
                `_truth` reference added to a template, static asset, or CSS would pass CI unnoticed.
Why it matters: W4 is precisely the phase that starts describing the firewall in template prose, so the
                surface the copy promises is now broader than the check that backs it. Concept: a firewall
                guarantee is only as strong as the file globs the guard walks.
Fix:            Extend the truth-path scan to also cover onramp/**/*.{html,css,js,svelte,vue} (a second glob
                in the same test), or note the .py-only scope explicitly so the page copy doesn't over-promise.
Confidence:     High (read the test; confirmed rglob("*.py") scope).
```

```
[NIT] Trust-section headings use the muted `.page-meta` "fine print" utility
Location:       onramp/plate_cost/web/templates/your_data.html lines 17, 41, 74
                (`<h2 class="page-meta"><strong>…</strong></h2>`); style.css .page-meta (85-89)
What's wrong:   `.page-meta` is `color: var(--text-muted); font-size:.9rem` — the utility used for meta/
                fine-print lines. Applying it to the W4 section titles renders those headings as small muted
                text (the inline `<strong>` restores weight but not size/color). Contrast computes to ~5.4:1
                on the surface, which passes WCAG AA, so this is hierarchy/semantics, not a contrast failure.
Why it matters: Rule 06 says transparency is "a first-class surface, not fine print"; styling the firewall/
                bridge headings with the fine-print utility mildly undercuts that intent and flattens the
                page's visual hierarchy.
Fix:            Give section headings their own heading class (or drop `.page-meta` from the `<h2>`s) so titles
                read as titles, not meta text.
Confidence:     High (computed the contrast; read the CSS).
```

```
[NIT] Bridge-panel "validated on test data today" is a strong word for a partial engine
Location:       onramp/plate_cost/web/templates/your_data.html lines 78-79
What's wrong:   "That engine exists and is validated on test data today" — "validated" is a confident claim
                for an engine that is P0-P4 (a calibrated quantile-to-prep-quantity turn) validated only on a
                simulated restaurant. The very next clause ("hasn't run on your restaurant's numbers yet, and
                nothing on this page changes until it does") mitigates well, and the builder deliberately
                avoided every simulation dollar figure — the honest direction.
Why it matters: Minor overclaim risk on a trust page; flagged only so a future discovery-driven copy pass
                knows this is the one phrase leaning forward. Not a defect.
Fix:            Optional: "validated against simulated test data" to match the platform's own standing caveat
                that simulation numbers are plausible placeholders, not validated facts.
Confidence:     Low (judgment/subjective).
```

**On the builder's flagged one-page-vs-two call (Reviewer Focus Area #1):** concur it is acceptable, not a
finding. §8's W4 row says "panel," not "page"; §3 is a complete-surface map, not a per-phase route mandate;
the split is a template + one route later, costs nothing to defer (rule 05: don't over-build ahead of need).
The bundling does not weld chrome to plate-cost specifics.

---

## Step 5 — Sign-off

**VERDICT:** **Yes, with one MAJOR to fix first.** W4 delivers the three-leg transparency ledger, the
plain-English firewall story, the per-leg CSV export (closing the real W2/W3 gap where the price leg was
never exportable), and the honestly-scoped bridge panel — the substance of §8's W4 slice, thin and
seam-correct. But MAJOR-1 means the transparency view is *not fully honest in a reachable state*
(only-invoices → "Nothing captured yet" + hidden export), which is the one thing a transparency phase must
get right. Meets criteria on the happy path; fix MAJOR-1 before closing.

**TEST + LINT (observed):**
- `make test`: **429 passed**, 4 warnings, 10.9s (matches the progress-log claim of 429).
- `make lint` (`ruff check .`): **All checks passed**.
- `make import-lint` (`lint-imports`): **2 contracts kept, 0 broken**.
- Boundary test (`tests/test_module_boundaries.py`): **4 passed** — verified it scans `.py` files for
  `forecasting` imports and `_truth` paths (would catch a planted `.py` violation; would NOT catch one in a
  template — LOW-1).

**TOP 3 FIXES (priority order):**
1. MAJOR-1 — Ungate the price leg from `has_data` so the only-invoices state shows (and lets the operator
   export) the invoice data it holds, and stop the page contradicting its own firewall paragraph.
2. MINOR-1 — Wrap `/your-data` (and the export route's corrupt-file path) in the calm-fallback + correlation-id
   pattern the `grid`/`insights` routes already use, so a corrupt parquet degrades legibly instead of a bare 500.
3. LOW-1 — Extend the `_truth` boundary grep to templates/static, so the firewall guarantee covers the surface
   W4 now describes in prose.

**WHAT I COULD NOT VERIFY (even after trying):**
- The **empty-but-present** price parquet case (`price_observations.parquet` with 0 rows): would render
  `has_price_data=True` with "0 observations across 0 ingredients" and show the export link. I did not seed a
  0-row file because the write path (`write_price_observations_atomic`) is out of W4 scope; unverified whether
  it can ever produce an empty file. Low risk.
- **Responsive/tablet-phone rendering** of the new sections — no browser/visual harness available in this
  environment; I confirmed markup + reused classes + AA contrast by computation, not by rendering at device widths.
- **Real multi-tenant isolation** — untestable today by design (single flat tenant, `RESTAURANT_ID="default"`);
  the page states this honestly and W9 owns it. No W4 regression, but no isolation was *exercised* because there
  is only one tenant to exercise.

**SINGLE BIGGEST RISK:** On the on-ramp's one trust surface, an operator who has captured invoice prices but
not yet BOM/sales is told "Nothing captured yet" and cannot export the data they gave us — a self-contradiction
on exactly the page whose job is to earn trust, and one the builder's decision log believes was already handled.
