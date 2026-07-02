# Phase W0 — Adversarial Web Review

> Independent findings from the `web-reviewer` subagent. This file is written directly to Jay, not
> relayed through the builder's thread. It reviews **build progress only** — comprehension is a
> separate `/learn` + `docs/mastery.md` track that nothing here gates.
>
> Reviewed: `onramp/plate_cost/web/**` as it exists on disk (landed in squashed `a66f85a`), against
> `website_vision.md` §8 (W0 = "Read-only reveal") + the on-ramp contract (`onramp/README.md`) +
> rules `05`/`06`/`07`. Backfilled decision log (`docs/phase_decisions/W0.md`) read and weighed as
> reconstructed, not contemporaneous.

## Step 0 — What W0 had to deliver ("done when")

- A **single page** that renders the existing plate-cost **grid + dish list** for one restaurant,
  computed from the on-ramp's **source inputs** (`data/sample_*.csv`) via the same `src/` chain as
  `src/run.py` — deliberately **not** the seam (`data/raw/` carries only BOM+sales, no prices, so
  margins can't be reconstructed from it). **No auth, no editing.** The "show a client in 60s" artifact.
- **Durable vs. provisional:** the chrome (shell, banner, footer, error page) is durable; the
  plate-cost-specific grid views are provisional and swappable.
- **Layering proof (rule 05):** thin presentation over pure, already-built compute — the web layer must
  not become the only way to run a plate-cost.
- **Seam firewall + on-screen trust:** never import `forecasting/`, never touch `_truth`/`interim`/
  `processed`, and every number must reconcile by eye (`Menu − ~Cost = Margin`) with no false precision
  and sample data visibly labeled.
- **One spec ambiguity flagged up front:** §8 calls W0 "a single **hosted** page," but the code only
  binds `127.0.0.1:8000` with no deploy artifact. "Hosted" is unmet as literally worded (see MINOR-1) —
  I judged the *renderable reveal* to be the substantive acceptance target, since §9 restates W0 as
  "one page over existing data" and the builder self-flagged deployment as unscheduled.

## Step 2 — Hunt list

**Seam firewall (highest priority):**
- W0 reads only `plate_cost/data/sample_*.csv`; never `data/raw/`, `_truth/`, `interim/`, `processed/`
  — **VERIFIED-BY-RUNNING** (`grep` of `web/**` shows `data/raw` only in comments that say it is *not*
  read; no `_truth`/`interim`/`processed` anywhere).
- Never imports `forecasting/` — **VERIFIED-BY-RUNNING** (`tests/test_module_boundaries.py` green; I
  re-ran the AST scan logic against planted `import forecasting.*` / `from forecasting import *` forms
  and it flags all static forms; dynamic `importlib.import_module` evades it — a documented limitation).
- All seam writes pass through `schemas/` — **PASS (vacuous)**: W0 is read-only, writes nothing.
- Store helper (`src/store.py`) opens only `data/raw/**` — **PASS**: hard-coded `_RAW_DIR`, bare-filename
  guard (rejects `/`, `\`, `..`), parameterized query, import-time `assert`. Structurally sound. (Not
  used by W0; verified for completeness.)
- Boundary test would catch a planted violation — **VERIFIED-BY-RUNNING** (see above).

**Architecture & layering (05):**
- Compute stays pure — **VERIFIED-BY-RUNNING**: `grep` finds no `fastapi/starlette/uvicorn/flask/django`
  import anywhere in `src/`, and `src/` never imports `web`. The `src.run` CLI path still runs the same
  compute independently.
- Dependencies point inward (templates ← `app.py` ← `compute.py` ← `src/`) — **PASS**.
- No premature server-class DB — **PASS**: W0 touches no DB; `store.py` is embedded DuckDB and unused here.
- Durable chrome vs. provisional product — **CONCERN (NIT-3)**: `base.html`'s footer welds plate-cost
  copy ("Margin = Menu − ~Cost", "$0.25") into the *durable* shell.

**UI trust (06):**
- False precision — **CONCERN (MINOR-2)**: costs correctly rounded to $0.25, but `food_cost_pct` is
  printed as a raw whole-number percentage.
- Non-reconciling numbers — **PASS for the headline** (`Menu − ~Cost = Margin` reconciles, verified for
  all 11 sample rows), **CONCERN (MINOR-2)** for the food-cost-% line (derived from *unrounded* cost).
- Unlabeled sample data — **PASS**: banner always rendered (test-guarded).
- Provenance path — **FAIL/CONCERN (MINOR-4)**: displayed cost cannot be expanded to its inputs.
- Tenant isolation — **N/A at W0** (single restaurant, "no auth" per §8); deferred to W2.
- Firewall leakage to browser — **PASS**: only sample dish names/costs reach markup; error path leak-free.
- Accessibility/legibility on money — **VERIFIED-BY-RUNNING**: money accent `#8c6214` on `#ffffff` ≈
  **5.4:1** contrast (WCAG AA pass for the 1.6rem bold margin figure); responsive `@media` present.

**Backend/API (07):**
- Boundary validation bypassed — **N/A** (no inbound writes at W0).
- Error handling leaks/crashes — **VERIFIED-BY-RUNNING**: `test_grid_failure_returns_legible_error`
  passes; broad `except` → calm 503 + correlation id; message/traceback/path stay server-side.
- Non-idempotent/atomic writes — **N/A** (no writes).
- AuthN/AuthZ gaps — **N/A at W0** (spec: no auth); correctly deferred to W2.
- Hostile input — **PASS for scope**: single `GET /` with no params/uploads; nothing to abuse yet.
- Statefulness leaks — **PASS**: handler recomputes from files per request; no cross-request in-memory state.

**Software engineering:**
- Core-logic correctness — **PASS**: margin reconciliation is correct and structurally guarded.
- Tests meaningful — **MOSTLY PASS**: `test_margin_reconciles_with_rounded_cost`,
  `test_uncostable_dish_is_surfaced_not_dropped`, and `test_grid_failure...` are real guards.
  **CONCERN**: no test covers the food-cost-% reconciliation (MINOR-2) or the covers-join honesty gap
  (MINOR-3).
- Edge cases — empty grid → 0 covers, no quadrants render (graceful); no upload/tenant/dup paths exist yet.
- Typed contracts — **PASS**: `DishRow`/`GridData` TypedDicts reuse `src/` types; DTOs justified as
  presentation-only (never seam rows), a correct call.

**Anti-drift:** **PASS** — genuinely thin: server-rendered Jinja2, no JS framework, no multi-tenant
platform, no polish beyond §8's slice. This is the honest next step, not drift.

## Step 3 — Riskiest spots (looked deliberately)

1. **The derived-metric card (`web/compute.py` `build_grid_data` + `grid.html`).** This is where a
   number can silently stop reconciling. The headline margin was fixed and is correct — but the
   *food-cost-%* line was not brought under the same discipline (MINOR-2). This is the single most
   concrete on-screen-trust finding.
2. **The compute→template honesty parity vs. the CLI (`web/compute.py` vs. `src/run.py`).** The web path
   mirrors the uncostable-dish skip list but **not** `_report_covers_join`. Name-mismatched or orphaned
   sales are silently handled on the web (MINOR-3). Latent on the clean sample; live once W1 feeds real
   POS exports.
3. **The error/exception seam (`web/app.py`).** Verified leak-free by running — this one is solid.

## Step 4 — Findings

```
[MINOR] "Hosted" page ships as a localhost-only dev server with no deploy artifact
Location:       onramp/plate_cost/web/__main__.py:15 (uvicorn.run(app, host="127.0.0.1", port=8000))
What's wrong:   website_vision.md §8 calls W0 "a single hosted page / the show-a-client-in-60s
                artifact," but the only run path binds to 127.0.0.1 with no Dockerfile, no prod ASGI
                config, no TLS, and no note of what "hosted" means today. It is reachable only on the
                builder's own machine. Not listed in any phase's deferred table.
Why it matters: "hosted" is the one word of the acceptance criterion the code does not satisfy. It is
                probably fairly W1/W2 infra (and the builder self-flagged it), but because it is
                unscheduled it sits in an ambiguous "in-scope-and-missing vs. out-of-scope" gap. A
                localhost bind also can't be demoed to a client without a tunnel — the exact use case
                §8 names. Concept: binding host 127.0.0.1 accepts only loopback connections; 0.0.0.0
                (behind a reverse proxy/TLS) is what exposes a service — but that is a real deployment
                decision, not a one-line flip, and should be a recorded, gated step.
Fix:            Either (a) record deployment as an explicit deferred item pointing at W1/W2 so it stops
                being an unscheduled gap, or (b) add a minimal documented run recipe (host, proxy, TLS)
                if "hosted" is meant to be satisfied now. Don't silently flip to 0.0.0.0.
Confidence:     High
```

```
[MINOR] Food-cost % is a raw whole-number percentage derived from the UNROUNDED cost — doesn't
        reconcile by eye with the displayed rounded ~Cost
Location:       onramp/plate_cost/web/compute.py:111 (food_cost_pct = r.food_cost_pct, the unrounded
                cost/menu) and templates/grid.html:47 ("%.0f" | format(dish.food_cost_pct * 100))
What's wrong:   The card carefully derives the displayed margin from the rounded cost (correct), but the
                Food-cost line prints food_cost_pct computed from the *unrounded* cost. So the third
                number on the card doesn't tie to the rounded ~Cost shown right above it. Ran the sample:
                Pan-Seared Salmon shows ~Cost $10.00, Menu $38.00, "Food cost 27%" — but 10.00/38.00 =
                26.3%, i.e. a chef reading the card computes ~26%, not 27%. House Burger shows "21%"
                while $4.50/$22.00 = 20.5% (~20%). Separately, rule 06 / seam_and_precision.md say to
                bin margin/cost percentages into labeled tiers "rather than displaying raw percentages"
                — the card shows the raw percent AND the tier, so it half-obeys, half-violates.
Why it matters: This is the exact class of credibility leak the reconciliation rule exists to prevent,
                just applied to the percentage line instead of the dollar line. Magnitude is small (≤1%)
                and it is a secondary ratio, not the headline dollar — hence MINOR, not MAJOR — but it
                is the most concrete rule-06 violation in the phase and the cheapest to close. Latent
                second-order bug: at a tier boundary the printed percent and the badge can disagree
                (a 24.8% cost prints "25%" but wears the "strong" badge, while the tier legend calls
                25% "ok"). Not triggered by the current sample, but real.
Fix:            Derive the displayed food-cost % (and, if you want full consistency, the tier) from the
                SAME rounded cost used for ~Cost and margin — or drop the raw percent and show only the
                labeled tier/range, per the "bin, don't print raw" discipline. Then add a test asserting
                round(cost_display / menu_price * 100) equals the printed percent, mirroring the existing
                margin-reconciliation test.
Confidence:     High
```

```
[MINOR] Web path does not mirror the CLI's covers-join honesty; "covers on record" can silently
        understate, and name-mismatched dishes get no alert
Location:       onramp/plate_cost/web/compute.py:98-99 (total_covers = sum(r.covers for r in rows));
                contrast src/run.py:50-68 (_report_covers_join) which the web path omits
What's wrong:   The decision log (W0.md) claims the web "fails the same honest way" as the CLI. It
                mirrors the uncostable-dish skip list, but NOT _report_covers_join: (1) a menu dish that
                matches zero sales rows (after normalize_name) silently shows "0 covers" and drops into a
                low-popularity quadrant with no warning — the CLI prints a "matched NO sales row" alert;
                (2) a sales row matching no menu item is silently excluded, and total_covers only sums
                COSTED, matched dishes, so "N covers on record" can understate the true covers total when
                data is dirty. Also, an uncostable (skipped) dish's covers vanish from the "covers on
                record" headline with no indication. Verified on the sample: 787 = full raw total, zero
                orphans, zero zero-cover dishes, zero skips — so none of this fires today.
Why it matters: "covers on record" is a client-facing number the operator can sanity-check against what
                they know they served; a silently-low total erodes exactly the trust the site is built
                to earn. The claim of CLI-parity in the decision log is inaccurate, which matters because
                W1 will feed real (dirty) POS exports through this same shape and inherit the blind spot.
                Concept: a name-based join (dish_name ↔ sales dish_name) is fragile; normalize_name
                defends the easy cases but the residual mismatches are exactly what must be surfaced,
                not swallowed. Latent for W0's fixed sample; a real gap for W1.
Fix:            Port the CLI's covers-join report into build_grid_data as a second surfaced list
                (unmatched menu dishes + orphaned sales), render it beside the existing skipped banner,
                and compute the "covers on record" headline from total sales (or label it "covers on
                costed dishes"). Add a test with a deliberately mismatched sample row.
Confidence:     High
```

```
[MINOR] Displayed plate cost is a black box — no provenance drill-down to recipe lines / prices / yields
Location:       onramp/plate_cost/web/templates/grid.html (dish-card shows totals only); no dish-detail
                route in web/app.py
What's wrong:   Rule 06 states flatly: "Any displayed cost can be expanded to its inputs (recipe lines,
                prices, yields). No black-box numbers — a chef must be able to audit any figure." W0
                shows the rounded ~Cost with no way to reach the line-by-line breakdown behind it.
Why it matters: Rule 06 is written as an absolute, but website_vision.md §3 schedules "Dish detail — the
                plate-cost breakdown line by line" as its own later surface, and §8's W0 slice is
                "grid + dish list," not dish detail. So this is a genuine rule-vs-scope tension, not a
                clear defect — flagged so Jay decides rather than papered over. For a "show a client in
                60s" artifact, the inability to answer "why is this $10?" is the first question a
                skeptical chef asks, so it is worth a conscious call now.
Fix:            Either (a) explicitly record provenance/dish-detail as deferred to the W-phase §3 names,
                closing the rule-06 tension on paper, or (b) add a lightweight expandable breakdown to
                the card if you want to satisfy rule 06 within W0. Don't leave it silently unaddressed.
Confidence:     High
```

```
[NIT] OpenAPI schema still served though Swagger/ReDoc are disabled
Location:       onramp/plate_cost/web/app.py:22 (docs_url=None, redoc_url=None; openapi_url left default)
What's wrong:   Disabling docs_url/redoc_url hides the UIs but /openapi.json is still reachable by
                default. For W0 it exposes only a single HTML GET route with no data, so the disclosure
                is negligible.
Why it matters: Minor attack-surface/info-disclosure hygiene; harmless now, worth a habit before any
                real API routes (W1) land. Concept: disabling the docs UI is not the same as disabling
                the machine-readable schema behind it.
Fix:            Pass openapi_url=None too (there is no client-facing API contract to publish at W0).
Confidence:     Medium
```

```
[NIT] Durable chrome (base.html) welds plate-cost-specific copy into the shell
Location:       onramp/plate_cost/web/templates/base.html:13-18 (footer: "Margin = Menu − ~Cost",
                "$0.25", "Sample data — ... not your restaurant's numbers")
What's wrong:   website_vision.md §2 and rule 05 say keep the durable chrome swappable — "don't weld the
                chrome to today's product." base.html (the durable shell every future on-ramp product
                would inherit) hard-codes plate-cost-specific footer/banner copy.
Why it matters: A different on-ramp product dropped into this shell would inherit a plate-cost footer.
                Trivial to fix now, cheaper than after more pages extend base.html. NIT because W0 is
                early and the coupling is one template block.
Fix:            Move plate-cost-specific footer copy into the grid template (or a block base.html
                exposes), leaving base.html generic (wordmark, main, error slot).
Confidence:     Medium
```

```
[NIT] Grid quadrant is classified on absolute DOLLAR margin, so a "thin"-food-cost dish can sit in a
      high-margin quadrant (inherited from Phase-0 src/report/grid.py, surfaced now that it's client-facing)
Location:       onramp/plate_cost/src/report/grid.py:80-92 (margin_high = r.margin >= mean_margin, where
                margin is absolute dollars), rendered by web/templates/grid.html
What's wrong:   Ribeye ($58 menu, 47% food cost, "thin" badge) lands in "Puzzle" (a high-margin quadrant)
                because its absolute dollar margin ($30.75) beats the mean, while its food-cost RATIO is
                the worst on the menu. On screen the card reads "high-margin quadrant" + "thin" badge —
                mixed signals a chef may find contradictory. Similarly a "Dog" can show a higher dollar
                margin than a "Plowhorse."
Why it matters: This is a pre-existing Phase-0 design property (dollar-margin axis), not a W0 regression
                — W0 only presents it — so it is out of W0's code scope and rated NIT. But making it
                client-facing is exactly when the interpretability wrinkle starts to cost trust, so it is
                worth a conscious note for the roadmap.
Fix:            Roadmap decision, not a W0 edit: consider whether the popularity×margin axis should be
                margin % (chef-legible ratio) rather than absolute dollars, and/or surface the axis
                definition on the page. Record the choice; don't silently carry it into client-facing UI.
Confidence:     Medium
```

## Step 5 — Sign-off

- **VERDICT:** **Yes, with one caveat.** W0's substantive acceptance target — a single page that renders
  the plate-cost grid + per-dish numbers for one restaurant from the source inputs (not the seam), with
  reconciling headline math, labeled sample data, and a leak-free error path — is met and verified by
  running. The one unmet word is "**hosted**": the page binds localhost-only with no deploy artifact and
  no scheduled home (MINOR-1). No BLOCKER or MAJOR found; the seam firewall is clean and the layering
  proof (thin presentation over pure compute) holds.
- **TEST + LINT:** `make test` → **209 passed, 4 warnings** (pandas deprecation, engine-side, unrelated).
  Web suite `onramp/plate_cost/tests/test_web.py` → **all pass**; boundary test
  `tests/test_module_boundaries.py` → **pass**, and I independently confirmed its AST scan flags planted
  static `forecasting` imports (dynamic `importlib` evades — a documented limitation).
  `make lint` (`ruff check .`) → **All checks passed!** No JS/TS toolchain exists (no `package.json`), so
  no `eslint`/`tsc` to run — correct for a no-framework server-rendered slice.
- **TOP 3 FIXES (priority order):**
  1. MINOR-2 — bring the food-cost-% line under the reconciliation discipline (derive from the rounded
     cost, or show only the labeled tier), and add a test. Cheapest, most concrete rule-06 fix.
  2. MINOR-3 — port the CLI's covers-join honesty into the web path and fix/label the "covers on record"
     total; the decision log's CLI-parity claim is currently inaccurate and W1 inherits the blind spot.
  3. MINOR-1 — record the deployment/"hosted" question as an explicit deferred item (or add a minimal
     hosted run recipe) so it stops being an unscheduled gap.
- **WHAT I COULD NOT VERIFY (even after trying):**
  - Real-tenant / dirty-data behavior — W0 only ever renders the clean fixed sample, so MINOR-2's
    tier-boundary mismatch and MINOR-3's understated-covers path are reasoned/latent, not observed live.
    They surface for real in W1.
  - Actual browser rendering, responsive breakpoints, and real-device contrast — I verified the CSS/HTML
    statically and computed the money-figure contrast ratio (~5.4:1, AA pass) by hand, but did not paint
    the page in a real browser at tablet/phone widths.
  - The `_truth` half of the boundary text-scan — my own probe command was (correctly) blocked by the
    `deny_truth_access` hook, so I confirmed that half by reading the test logic, not by executing it.
    The firewall hook firing on my probe is itself evidence the layered defenses are live.
- **SINGLE BIGGEST RISK:** The food-cost-% number on every dish card is computed from the unrounded cost
  while the cost beside it is rounded — the one place on the "show a client in 60s" screen where a chef
  doing the arithmetic in their head can catch a number that doesn't quite tie, which is exactly the
  day-one trust the on-ramp is built to win.

**Rules:** No praise padding. Genuinely good: the seam firewall is clean, the headline margin
reconciliation is correct and structurally test-guarded, and the phase is honestly thin (no drift).
