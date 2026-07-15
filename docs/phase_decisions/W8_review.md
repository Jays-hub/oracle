# W8 Adversarial Review — the public face (storefront + design & accessibility pass)

**Reviewer:** web-reviewer (adversarial, read-only over code; Write scope = this file only)
**Date:** 2026-07-15
**Branch:** onramp/w7-production-hardening (W8 built on it, uncommitted)
**Diff base:** working tree vs. HEAD (`f2082f6`) — `git diff` + untracked `_progress_meter.html`,
`tests/test_web_landing.py`, `docs/phase_decisions/W8.md`. Confirmed no `.py`/route/schema/seam
files changed: the whole phase is docs + 5 templates + 1 stylesheet + 1 new template + 1 new test.

---

## Step 0 — What W8 had to deliver ("done when")

From `website_production_overview.md` §1 row 11 + §4 (W8 row) + §5 invariants, and vision §5:

- A **public storefront** at `GET /` a stranger can find and judge without us in the room, making
  the site's own one-sentence pitch (vision §1), **with the sample grid kept embedded inside it as
  a clearly-labeled live demo.**
- The **vision §5 design pass across every existing screen**: calm/restaurant-appropriate, one accent
  reserved for "this is money," responsive tablet/phone layouts, and the **WCAG-AA accessibility
  audit rule 06 mandates** (contrast, semantics, keyboard) under kitchen-hostile defaults.
- **Onboarding UX polish**: the recipe-sitdown progress meter and a visible "good enough to show
  value" threshold (vision §3A).
- **Still server-rendered, no JS framework** — a design-and-markup pass, not a stack change.
- The review closes on the **rule-06 trust law** — honest precision, reconciles-by-eye, labeled
  sample data, AA contrast on money figures — which a redesign can silently break.

No spec/intent conflict found. Scope matches: this is a presentation-layer pass over already-built
compute/routes. The layering discipline (rule 05) held perfectly — zero `src/` compute, zero new
routes, zero seam/schema touch — which is exactly what a design pass should be.

---

## Step 2 — Hunt list (pass / concern / fail / verified-by-running)

**Seam firewall (highest-priority structural law):**
- onramp never reads `_truth`/`interim`/`processed`, never imports `forecasting/`: **verified-by-running**
  — `lint-imports` 2 contracts kept / 0 broken; `tests/test_module_boundaries.py` green (part of the
  17-test targeted run). W8 adds no data access at all, so nothing could regress here.
- All seam writes through `schemas/`: **pass (N/A)** — W8 writes nothing new to the seam; no new store
  or capture code.
- Store helper raw-only: **pass (N/A)** — untouched.

**Architecture & layering (rule 05):**
- Compute stays pure, no web import in `src/{bom,pricing,report}`: **verified** — no `src/` file changed.
- Dependencies point inward; presentation doesn't reach past the API: **pass** — pure templates/CSS.
- One threshold constant (`_value_threshold = 3`) lives in the Jinja template, not `web/upload.py`:
  **pass** — defensible; it's UI copy selection, not plate-cost math the engine/seam consumes (rule 05
  is about business math; this isn't).
- Durable chrome vs. provisional product: **pass** — the storefront hero carries plate-cost copy but is
  a swappable template; skip-link/focus/nav/progress-meter chrome is product-agnostic.

**Front-end / UX trust (rule 06):**
- False precision: **pass** — W8 introduces no new numeric displays; grid money figures untouched.
- Non-reconciling numbers: **verified** — grid.html's dish rendering (`margin_display`, `cost_display`,
  `menu_price`) is byte-unchanged; the "Menu − ~Cost = Margin reconciles by eye" footer is intact.
- Unlabeled sample data: **verified** — storefront demo is labeled "Live demo — sample menu" + the
  `sample-banner` fires on `GET /`; every real-tenant template (`dishes`, `menu_prices`, `your_data`,
  `insights`, funnel, invoice) correctly overrides `sample_banner` to empty (grep-confirmed all 14).
- Provenance path: **pass (N/A)** — unchanged.
- Tenant isolation: **verified** — no fetch changed; nav `logged_in` is cosmetic-only (`_nav_context`)
  and gates no content.
- Firewall leakage to browser: **pass** — nothing new reaches markup.
- AA contrast on money figures: **verified-by-hand-calc** — `--money #8c6214` on `--bg` = 5.07:1, on
  white = 5.42:1 (passes 4.5:1). Focus ring `#0b57d0` ≥3:1 on both surfaces. New value-threshold green
  reuses the existing `.tier--strong` pairing (`#1f5c2a` on `#e6f4ea` = 7.05:1). All pass.
- Legibility of *links*: **concern** → see MINOR-1 (the one real regression this pass introduced).

**Backend / API (rule 07):** **pass (N/A) across the board** — no route, handler, validation, error
path, upload, or auth code changed. Error handling (`error.html` + correlation-id) untouched and still
receives `request` via the context processor on every render (checked — no 500-in-500 risk from the new
`request.url.path` reference).

**Software engineering:** tests meaningful on the value-threshold (both sides of the boundary) and the
active-nav marker (positive + negative) — **good**. Two test-name overstatements and one fragile partial
— **NIT** (below). Structure/style otherwise clean.

**Anti-drift:** **pass** — no JS framework, no backend logic, no data-model reach; last item on a
recorded, approved map. Correctly did *zero* modeling. No over-engineering.

---

## Step 3 — Riskiest spots, and what I found when I looked

1. **The global `a {}` restyle (blast radius = every link on every screen).** This was the highest-risk
   change: a single rule repainting all links. It *did* degrade something — inline prose links (see
   MINOR-1). The deliberate hunt paid off here.
2. **The new `aria-current` inline-`if` + `| safe` idiom in `base.html`.** Verified by running: renders
   the attribute when the path matches and an empty string otherwise (Jinja default `Undefined`); the
   `| safe` string is a static literal, no injection surface. **Clean.**
3. **`_progress_meter.html` include sharing `{% set step %}` from the parent.** Verified by running: the
   context is shared and the right step is marked current/done on all three funnel pages. Fragile if a
   future includer forgets `step` (MINOR/NIT-3), but correct as used.

---

## Step 4 — Findings

```
[MINOR] Inline prose links lost their visual affordance after the global link restyle
Location:       onramp/plate_cost/web/static/style.css  a { color: var(--text);
                text-decoration-color: var(--border); }  — most visible on
                web/templates/success.html ("set your menu prices" / "your dishes")
What's wrong:   Every content link now renders in the body-text color (--text #1a1a1a) with an
                underline in --border (#e4ddd6). That underline's contrast against the page is
                ~1.3:1 (I computed #e4ddd6 on white = 1.35:1, on --bg = 1.26:1) — effectively
                invisible. So an inline link is the *same* color as surrounding text with a
                near-imperceptible underline. Before W8, links were the browser default blue and
                clearly distinguishable.
Why it matters: The success page is the highest-trust moment (right after a first save) and its one
                actionable next step — "One step left... set your menu prices, then check your
                dishes" — now visually buries the two links that ARE the call to action. Under
                rule 06's kitchen-hostile brief (glare, grease, gloves), a 1.3:1 underline is gone.
                Concept: a link needs a non-color affordance that is itself perceivable; an
                underline satisfies "don't rely on color alone" only if the underline is actually
                visible. Nav links are fine (distinct region + hover/focus underline + aria-current);
                the loss is specifically inline links in prose.
Fix:            Give content links a visible underline: set text-decoration-color to --text-muted
                (or --money for the money-adjacent CTAs), not --border. One-line change; keeps the
                "no second accent hue" intent while restoring the affordance. Optionally scope a
                .confirm-summary a / .page-intro a rule so nav styling stays separate.
Confidence:     High (read the CSS; computed the underline contrast; the rule has no more-specific
                override for content links).
```

```
[MINOR] "Good enough to show value" gates on BOM-distinct dish count, including uncostable/unmatched dishes
Location:       onramp/plate_cost/web/templates/confirm.html  {% set _value_threshold = 3 %}
                against summary.dish_count (web/upload.py::build_summary →
                len({r.dish_name for r in bom_rows}))
What's wrong:   dish_count counts distinct dish names in the *BOM* only. A dish that appears in the
                recipe sheet but matches no sales row (surfaced right below as only_in_bom), or a
                dish that won't cost cleanly, still increments the count. So the green "That's enough
                dishes to show value — set your menu prices next to see your real margins" can fire
                on 3 BOM names even when fewer than 3 dishes will actually render costed on /dishes.
Why it matters: Mild honesty gap against rule 06's "honest presentation" — the badge implies "enough
                to see a real spread across quadrants" but is counting a looser thing than what the
                grid will show. Low-stakes (it's soft encouragement, the count is shown right beside
                it, and no dollar figure is claimed), but the threshold's basis and its promise don't
                quite line up. The builder flagged the *magnitude* of "3" as unvalidated; this is the
                separate point that the *thing being counted* is BOM-distinct, not grid-eligible.
Fix:            If cheap, gate on dishes that appear in BOTH files (dish names ∩ sales) — the count
                that will actually cost. Otherwise soften the copy so it promises menu breadth, not
                grid-ready dishes. Either is a template-only change.
Confidence:     Medium (read build_summary and the template; did not build the specific mismatched
                upload to watch the badge fire alongside the only_in_bom warning, but the logic is
                unambiguous from the source).
```

```
[NIT] Two test names claim more coverage than the assertions prove
Location:       onramp/plate_cost/tests/test_web_landing.py
                test_skip_link_present_on_every_page, test_main_landmark_is_the_skip_links_target_and_focusable
What's wrong:   Both assert only against GET / . The skip link and #main-content live in base.html so
                they ARE inherited by every page, but neither test exercises a second page (e.g. an
                authenticated route) to prove "every page."
Why it matters: A future edit that moved these out of base.html into grid.html only would keep both
                tests green while breaking the skip link everywhere else. The name promises a
                guarantee the test doesn't enforce.
Fix:            Add one assertion against a non-landing render (e.g. /login or a bypassed /upload),
                or rename to "...on the landing page."
Confidence:     High (read the tests).
```

```
[NIT] _progress_meter.html hard-depends on the includer setting `step`, with no fallback
Location:       onramp/plate_cost/web/templates/_progress_meter.html  ({{ ... if s.n == step }},
                {{ ' is-done' if s.n < step }})
What's wrong:   If a future template includes the partial without {% set step = N %}, `step` is
                Undefined and `s.n < step` raises UndefinedError (default Jinja Undefined), 500-ing
                the page. The contract is documented in the partial's comment but not defensive.
Why it matters: A shared partial is exactly the thing that gets reused by someone who doesn't read
                its comment. Cheap to make safe.
Fix:            Add {% set step = step | default(0) %} at the top of the partial.
Confidence:     High (Jinja default Undefined raises on ordered comparison; behavior confirmed by how
                the existing pages must set step for the tests to pass).
```

```
[NIT] A logged-in operator visiting GET / sees a "Log in" CTA and the sample banner
Location:       onramp/plate_cost/web/templates/grid.html (hero) — GET / is public, nav shows the
                logged-in branch when is_authenticated is true
What's wrong:   The hero always renders "no login required" + a "Log in" button + the sample banner,
                while the nav (cosmetic is_authenticated check) simultaneously shows the logged-in
                links. So an authenticated user on / gets a mildly contradictory screen.
Why it matters: Purely cosmetic; not a data or trust issue (GET / is the public storefront by design).
                Worth a line only because the storefront is the phase's headline surface.
Fix:            Optional — hide the hero's "Log in" CTA (and/or swap in a "Go to your dishes" link)
                when logged_in. Template-only.
Confidence:     High (read the template + the GET / handler; nav is cosmetic per app.py's own comment).
```

**Not findings (checked and cleared):** the decision log's "no new color pairing" claim holds — the
value-threshold green reuses the existing `.tier--strong` (`#1f5c2a`/`#e6f4ea`, 7.05:1). Money-figure
AA contrast passes (verified by hand-calc, matching the log's 5.07:1). Sample-data labeling is correctly
scoped to the storefront only. Grid reconciliation is byte-unchanged. Heading order (h1→h2→h2→h3) skips
no level. No seam, tenant-isolation, or firewall exposure — this phase adds no data access.

---

## Step 5 — Sign-off

- **VERDICT:** **Yes** — W8 meets its acceptance criteria in `website_production_overview.md` §4 / §5
  and vision §5. The public storefront exists at `GET /` with the pitch verbatim and the sample grid
  embedded and labeled; the accessibility pass (skip link, `:focus-visible` rings, `aria-current`,
  semantic landmarks) and responsive breakpoints landed; onboarding got the progress meter + value
  threshold; it stayed server-rendered with zero JS and zero backend change; and the trust law
  (reconcile-by-eye, labeled sample data, AA money contrast) is intact. The findings are all MINOR/NIT
  polish, none blocking. Fix MINOR-1 before this is shown to a real stranger.

- **TEST + LINT (observed, not claimed):**
  - `python -m pytest -q` (full repo, restaurant-dev env): **611 passed, 4 warnings** in 17.22s (the
    warnings are pre-existing pandas dtype-deprecation in `forecasting/tests`, unrelated to W8).
  - Targeted: `test_web_landing.py` (12) + `tests/test_module_boundaries.py` (5) = **17 passed.**
  - `ruff check .`: **All checks passed.**
  - `lint-imports`: **2 contracts kept, 0 broken** (the onramp↔forecasting seam contract among them).
  - Boundary test would still catch a planted `forecasting/` import or `_truth` path — confirmed it's
    in the passing set and the import-linter contract is active.

- **TOP 3 FIXES (priority order):**
  1. MINOR-1 — restore a visible underline on inline links (use `--text-muted`/`--money`, not `--border`);
     the success-page CTA is currently near-invisible.
  2. MINOR-2 — gate the value threshold on grid-eligible (BOM ∩ sales) dishes, or soften the copy.
  3. NIT-3/4 — make the skip-link tests exercise a second page; give `_progress_meter.html` a
     `step | default(0)`.

- **WHAT I COULD NOT VERIFY (even after trying):**
  - **Actual rendered pixels / real-browser contrast.** No browser, axe-core, or Lighthouse in this
    env (same gap the builder flagged). I re-derived the WCAG relative-luminance contrasts by hand and
    they agree with the builder's figures, but no automated checker cross-checked them, and I could not
    see the CSS rendered — focus-ring visibility, wrapped-nav crowding on a real phone, and the
    skip-link's on-focus placement are reasoned-about, not seen.
  - **A live socket-bound server.** Like the builder, I used `TestClient(app)` (same ASGI app,
    middleware, Jinja) rather than `python -m web`, which the W7 `ensure_safe_bind` guard blocks without
    explicit authorization. Everything asserted is via the real request path, but not over a real socket.

- **SINGLE BIGGEST RISK:** The one thing most likely to be silently wrong is **MINOR-1** — the global
  link restyle made inline links (the success page's "set your menu prices / your dishes" CTA above all)
  visually indistinguishable from body text, so the storefront's own guided next step is buried at the
  exact moment the design pass was meant to make the site presentable to a stranger.
