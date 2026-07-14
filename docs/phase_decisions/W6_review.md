# W6 Adversarial Review — the costed reveal over the tenant's own data

**Reviewer:** web-reviewer (adversarial, read-only over code; Write scoped to this file only)
**Date:** 2026-07-14
**Diff base:** uncommitted working tree (all W6 changes), scoped against `git status` + the builder's
decision log `docs/phase_decisions/W6.md`. `website_vision.md` §8 stops at W4 and hands W5–W10 to
`website_production_overview.md` §4, so acceptance is read from that table's **W6** row + §1 items
#6/#8 + §3 two-store laws + §5 invariants, alongside `onramp/README.md`.

---

## Step 0 — What W6 had to deliver ("done when")

- **Capture the one missing seam input — menu price — into the app DB**, on-ramp-private, never
  crossing the seam (two-store law #1). Delivered: `Dish` table keyed `(restaurant_id, dish_name)`,
  tenant-scoped upsert, UUID PK (the "stable item_id app-side").
- **Show the operator their *own* costed grid + dish detail** from their captured legs + prices,
  replacing counts-only/sample-only surfaces. Delivered: `GET /dishes`, `GET /dishes/{dish_id}`.
- **Write the derived `food_cost` (Co) seam leg through a new `schemas/` definition**, closing the
  Co-provenance forward note (two-store law #3). Delivered: `FoodCostRow` + `write_food_cost_atomic`.
- **Honest-precision invariant still holds** (overview §5.3, rule 06): rounded dollars, reconciles by
  eye, no margin claim the inputs can't support. **This is where the phase fails — BLOCKER-1.**
- **No new infra; thin over pure compute; seam law + boundary tests stay green.** Boundary tests green
  (verified). Compute purity is mostly respected but the dish-detail costing math leaked into the web
  layer — MAJOR-2.

**Spec-vs-code conflicts to flag up front (not papered over):**
1. The phase's own honest-precision invariant is violated — the conflict is code-vs-acceptance, and it
   is the defect (BLOCKER-1).
2. The W6 acceptance row also names "opportunities computed from the operator's own legs + **prices**"
   and "replacing counts-only `/your-data`." The builder deferred the menu-price-derived margin claim
   on `/insights` (defensible — W3's structural regression guards protect exactly that) and did **not**
   touch `/your-data` at all, so the "own data" value lands on a *new* surface (`/dishes`) rather than
   by upgrading the surfaces the text names. Reasonable given ambiguous wording — but it also leaves
   `/your-data` omitting the new leg it now sends (MAJOR-1).

---

## Step 2 — Hunt-list verdicts

**Seam firewall (highest priority)**
- Writes only `data/raw/`, reads only own files; no `_truth`/`interim`/`processed`: **PASS**.
- All seam writes through `schemas/`: **PASS (verified-by-running)** — `FoodCostRow` is constructed
  (pydantic-validated) in `build_food_cost_rows` before `write_food_cost_atomic` dumps it; no
  hand-rolled write.
- Store helper structurally raw-only: **PASS** — unchanged; hard-coded `data/raw` + load-time assert;
  correctly no `read_food_cost` added.
- `tests/test_module_boundaries.py` catches a planted violation: **PASS (verified-by-running, 5
  passed)** — the new `src/costing/` imports only `schemas` + intra-package `src`.
- No `forecasting/` import either direction: **PASS**.

**Architecture & layering**
- No web-framework import in `src/{bom,pricing,report,costing}`: **PASS** — `src/costing` imports
  pandas + SQLAlchemy only (mirrors the `src/auth` DB-aware-but-framework-free split).
- API embeds no business math compute should own: **FAIL** — `web/dishes.py::build_dish_detail`
  inlines the per-line plate-cost formula (MAJOR-2).
- Durable chrome vs. provisional product: **PASS** — catalog/persistence durable; plate-cost views
  provisional; nav additions generic.
- No premature server-class DB: **PASS**.

**Front-end / UX trust**
- False precision on headline: **PASS** (`round_to_quarter`) — but see MINOR-4 (integer-% vs tier).
- **Non-reconciling numbers: FAIL (BLOCKER-1, verified-by-running)** — same dish, different plate cost
  and margin on `/dishes` vs `/dishes/{id}`.
- Unlabeled placeholder/sample data: **PASS** — W6 templates blank `sample_banner`; menu-price form
  shows blank, never a fabricated $0.
- Provenance reachable: **PRESENT but self-contradicting** — the detail page *is* the provenance path,
  but BLOCKER-1 makes it disprove the grid's number instead of confirming it.
- Tenant isolation (server-side): **PASS for W6's additions** — `menu_prices_by_seam_key` filters
  `restaurant_id`; global seam read is the documented W9 deferral, fenced to one tenant by W5.
- **Transparency completeness: FAIL** — `/your-data` never discloses the new `food_cost` leg now sent
  to the engine (MAJOR-1).
- Firewall/other-tenant leakage to browser: **PASS**.
- Accessibility/responsiveness on money figures: **not audited** (scheduled W8; out of W6 scope).

**Backend / API correctness**
- Boundary validation not bypassed: **PASS** — menu-price form parsed + range-checked; seam write via
  `FoodCostRow`.
- Error handling that leaks/crashes: **PASS (verified)** — all 4 routes wrap in try/except → calm
  `error.html` + correlation id + 503; unknown dish → 404; bad price → named 422; a test asserts the
  internal path never reaches the client.
- Idempotent/atomic seam writes: **PASS** happy path (temp-then-`os.replace`, full-replace) — see LOW-6
  for the empty-result edge.
- AuthN/AuthZ on every data path: **PASS** — all 4 routes require a session.
- Hostile input: **PASS** — display name re-read from authoritative BOM, never round-tripped through
  the form; unknown submitted `dish_id`s ignored.
- Statefulness leaks: **PASS**.

**Software engineering**
- Core-logic correctness: BLOCKER-1 / MAJOR-2 are correctness, not style.
- Tests meaningful: **CONCERN** — the "reconciles by eye" dish-detail test uses a single-ingredient
  dish, so it structurally cannot catch BLOCKER-1 (MINOR-5).
- Edge cases: mostly handled (empty BOM, no sales, no prices, unknown dish, bad price); two low edges
  (LOW-6 stale file, MINOR-6 normalize collision).
- Typed contracts reuse `schemas/`: **PASS** — `FoodCostRow` exported; no parallel DTO for the seam row
  (the TypedDicts are presentation shapes, fine).

**Anti-drift: PASS** — no new model/stats, no heavyweight framework, no multi-tenant platform ahead of
the fenced single tenant. Durable chrome not welded to plate-cost specifics.

---

## Step 3 — Riskiest spots, and what I found

1. **Two rounding disciplines for the same dish's plate cost** (`build_dishes_summary` rounds the
   aggregate once; `build_dish_detail` rounds each line then sums). Looked here first; ran both real
   paths on a multi-ingredient dish → they diverge. **The phase's defect (BLOCKER-1),** rooted in the
   detail path being a separate reimplementation (MAJOR-2).
2. **The derived seam write's trigger + atomicity.** Atomicity is clean; the *trigger* (menu-price
   save, not invoice confirm) leaves the leg stale after a price change (MINOR-3); the empty-result
   guard leaves a stale file (LOW-6).
3. **The transparency surface after a new leg starts crossing the seam.** `/your-data` was not updated;
   it hides the food_cost leg it now sends, and menu_prices.html points the operator there for exactly
   that (MAJOR-1).

---

## Step 4 — Findings

```
[BLOCKER] Same dish shows a different plate cost and margin on the grid vs. its detail page
Location:       onramp/plate_cost/web/dishes.py — build_dishes_summary (line ~73:
                cost_q = round_to_quarter(r.cost)) vs build_dish_detail (lines ~150-163: each line
                as_used_cost = round_to_quarter(...) summed into `total`; cost_display = total)
What's wrong:   The grid computes cost = round_to_quarter(Σ precise line costs) — round ONCE on the
                aggregate. The dish-detail computes cost = Σ round_to_quarter(each line) — round each
                line THEN sum. These are different numbers whenever a dish has ingredient lines that
                round differently individually than in aggregate — the common case for any real entrée
                with several small supporting ingredients (aromatics, oil, butter, garnish, salt).
                Verified by running the real src/ functions on a 4-ingredient dish ($0.13 each,
                $0.52 true total, $9.00 menu):
                  /dishes        -> ~Cost $0.50   Margin $8.50   Food cost 6%
                  /dishes/{id}   -> ~Cost $1.00   Margin $8.00   Food cost 11%
                Same dish, reached by clicking the grid card. The detail total ($1.00) also disagrees
                with the food_cost value written to the SEAM (the unrounded $0.52), so the detail page
                is the outlier against both the grid and the engine input.
Why it matters: Rule 06 and overview §5.3 (the phase's own acceptance criterion) make "numbers
                reconcile by eye" a hard law, and the core journey is grid -> click dish -> detail. The
                detail page is the provenance/audit surface whose entire job (vision §3B) is to let a
                chef "trust the total" — so when it shows a different cost than the grid it was reached
                from, provenance actively DISproves the headline. Worse, rounding each cheap line up to
                $0.25 inflates the total by up to ~2x — a "confidently-wrong plate cost" (CLAUDE.md
                discipline #2) on the one surface meant to build trust. Concept: rounding is not
                distributive over addition, round(Σxᵢ) ≠ Σround(xᵢ); the per-item error accumulates and
                biases upward when several small parts each jump to the grid. Round ONCE, on the
                aggregate, at display.
Fix:            Derive both screens' ~Cost from one source with one rounding rule: keep the
                aggregate-rounded total (round_to_quarter of the precise dish cost) as the ONE ~Cost on
                both, and show per-line costs at real cents (a genuine audit trail — which
                build_dish_detail's own docstring already claims) with a note that the total is the
                rounded plate cost. Add a multi-ingredient regression test asserting grid ~Cost ==
                detail ~Cost for the same dish (see MINOR-5). Best fixed together with MAJOR-2.
Confidence:     High (ran the real src/costing + src/report functions; numbers above reproduced).
```

```
[MAJOR] Transparency page (/your-data) hides the new food_cost leg it now sends to the engine
Location:       onramp/plate_cost/web/your_data.py::build_your_data_summary + templates/your_data.html
                ("What we hold, and why" lists only BOM / Sales / Invoice-price); cross-referenced by
                templates/menu_prices.html footer.
What's wrong:   W6 begins writing data/raw/food_cost.parquet, a derived leg that crosses the seam to
                the forecasting engine (data/CONTRACT.md now lists it). Neither your_data.py nor
                your_data.html was touched: the ledger still enumerates exactly three legs and exports
                only those three. And menu_prices.html actively tells the operator "only the resulting
                cost figure does [cross the seam] (see your data for what we send the forecasting
                engine)" — pointing them at a page that does not show that cost figure among what's
                sent.
Why it matters: Transparency is a first-class trust surface, not fine print (rule 06 / vision §4: "a
                human-readable list of the data legs we hold... one-click export of everything we hold
                for them"). The site makes a promise ("see your data for what we send") that the target
                page silently breaks. For a product whose differentiator is "we show you exactly what
                we do with your data," an undisclosed engine-bound leg is precisely the gap that costs
                trust when an operator later notices it.
Fix:            Add a fourth ledger row ("Per-dish food cost we send the engine — derived from your
                recipes + prices, N dishes") and a matching CSV export of food_cost.parquet, keeping
                the "menu price never crosses / only the derived cost does" framing menu_prices.html
                already promises.
Confidence:     High (read both templates + glue; confirmed no food_cost reference anywhere in the
                transparency path).
```

```
[MAJOR] Dish-detail plate-cost math is re-implemented in the web glue layer (root cause of BLOCKER-1)
Location:       onramp/plate_cost/web/dishes.py — build_dish_detail, lines ~148-159
                (convert(...) / row["yield_factor"] * price; round_to_quarter; running total)
What's wrong:   The per-line as-used cost formula and the total live in web/, not src/. Rule 07 is
                explicit: "Business math (plate cost, margins, the grid) lives in src/, never inlined
                in a handler — so it stays unit-testable and reusable by the engine handoff." The grid
                path correctly delegates to the pure src/costing/tenant_grid.build_tenant_grid, but the
                detail path hand-rolls the plate-cost formula a THIRD time (after
                src/pricing/compute.py::plate_cost and src/insights/opportunities.py::
                dish_ingredient_cost). The decision log's own stated practice — "layered reuse over
                duplication ... rather than forking a third copy" — is contradicted here.
Why it matters: (a) It is the structural root cause of BLOCKER-1 — because the detail total is a
                separate reimplementation, it silently drifted from the grid's rounding discipline; a
                single shared src/ function makes that divergence impossible. (b) The detail costing has
                no src-level unit test; it is exercised only through the HTTP route with a
                single-ingredient dish, so the multi-line math is untested. (c) Compute the engine
                handoff/CLI could reuse is trapped behind the web layer.
Fix:            Move the per-line breakdown into a pure src/costing function (e.g.
                build_dish_line_items(bom_df, prices, dish_id) -> (lines, total)) sharing the same
                qty/yield/price formula and the SAME single rounding rule the grid uses; web/dishes.py
                only shapes the result. Add a multi-ingredient src-level unit test.
Confidence:     High (read the code; confirmed no src/ delegation on the detail path).
```

```
[MINOR] build_dish_detail docstring claims per-line "real precision" but the code rounds each line
Location:       onramp/plate_cost/web/dishes.py::build_dish_detail docstring (lines ~118-126)
What's wrong:   The docstring states "Per-line costs are shown at real precision (this is a
                provenance/audit surface...)". The code does the opposite:
                as_used_cost = round_to_quarter((qty_canonical / yield) * price). Comment and code
                disagree; per review discipline, the code is the truth.
Why it matters: This is the most decision-heavy line in the phase (the builder flagged the rounding
                choice as a focus area). A docstring describing the OPPOSITE of what runs misleads the
                next maintainer — and here it happens to describe the CORRECT behavior the BLOCKER-1
                fix should adopt. Comments that lie are worse than none because they are trusted.
Fix:            Resolve with BLOCKER-1: make the code match the docstring (per-line at real cents),
                which also fixes the reconciliation bug.
Confidence:     High.
```

```
[MINOR] Displayed food-cost % (rounded to whole percent) can contradict its own tier label at the boundary
Location:       templates/dishes.html line 68 and dish_detail.html line 38
                ("%.0f"|format(food_cost_pct*100) shown beside food_cost_tier(food_cost_pct))
What's wrong:   The percentage is displayed rounded to an integer, but the tier is computed from the
                unrounded fraction. Verified by running: food_cost_pct = 0.2480 displays "25%" while
                food_cost_tier(0.2480) = "strong" (whose stated boundary is <25%), rendering
                "25% (strong)" — which the chef's own tier table says should be "ok".
Why it matters: A small false-precision-at-the-boundary credibility ding: the label and the number
                beside it disagree, on the exact food-cost-% language a chef reads first.
Fix:            Bin the tier from the SAME rounded percentage that is displayed (round first, then
                bin), or display one decimal place so number and bin agree.
Confidence:     High (ran the boundary case).
```

```
[MINOR] The food_cost seam leg goes stale after an invoice upload (recompute tied to the wrong event)
Location:       web/menu_prices.py::save_menu_prices_and_recompute_food_cost; and its ABSENCE from
                web/app.py::invoice_confirm_submit
What's wrong:   food_cost is recomputed and rewritten only when a menu price is saved. But Co
                (ingredient cost) changes when a new INVOICE arrives, not when a menu price is edited.
                An operator who uploads a new invoice and never revisits /menu-prices leaves
                data/raw/food_cost.parquet reflecting the OLD prices.
Why it matters: A derived engine input silently drifting from the data it is derived from is a
                correctness trap the moment a forecasting phase reads this leg. The decision log's
                reasoning is weak: it ties the recompute to the menu-price save "to avoid silently
                expanding W3's reviewed scope" — but adding a recompute call to the existing
                /invoice/confirm POST (which already writes the seam atomically) is small and
                well-scoped, and keeping a derived leg correct outranks phase-boundary tidiness. The
                "GET must not mutate" half of the reasoning is sound; the choice of WHICH write action
                is not.
Fix:            Extract a shared recompute-and-write helper; call it from BOTH the menu-price save and
                a successful /invoice/confirm. Low urgency (no consumer reads the leg yet) but record
                it so the future reader doesn't inherit stale Co.
Confidence:     High (verified the only writer is the menu-price path).
```

```
[MINOR] The "reconciles by eye" dish-detail test can't catch BLOCKER-1 (single-ingredient fixture)
Location:       tests/test_web_dishes.py::test_dish_detail_shows_ingredient_breakdown_reconciling_to_total
                (Burger has ONE ingredient; the assert comment says "the one line IS the total here"),
                and the absence of any test comparing grid total to detail total for one dish
What's wrong:   With a single ingredient whose cost sits on the $0.25 grid, round-of-sum and
                sum-of-rounds are trivially equal, so the test passes while the multi-line divergence
                is untested. No test asserts grid ~Cost == detail ~Cost for the same dish.
Why it matters: A green suite here reads as "reconciles by eye" when it does not — a test that cannot
                fail on the bug it names manufactures false confidence.
Fix:            Add a multi-ingredient fixture (several sub-$0.25 lines) and assert grid ~Cost ==
                detail ~Cost (and margins / food-cost %) for that dish.
Confidence:     High.
```

```
[MINOR] menu_prices_by_seam_key can silently collapse two catalog rows to one price
Location:       src/costing/menu_prices.py line 51
                ({normalize_name(d.dish_name): d.menu_price for d in rows})
What's wrong:   Dish is uniquely constrained on the EXACT (restaurant_id, dish_name), but joined to
                the seam by normalize_name(). If a BOM is re-uploaded with different casing/spacing for
                a dish, upsert's exact-name lookup creates a SECOND Dish row; both normalize to the
                same seam key, and the dict comprehension keeps only the last one in query order,
                silently discarding the other's price (and orphaning the old row).
Why it matters: Rare, but a stale or ambiguous price could surface with no signal. The catalog's
                uniqueness key (exact name) and the join's key space (normalized name) are subtly
                mismatched; a rename silently loses a price.
Fix:            Store/enforce uniqueness on the normalized name, or on read aggregate colliding rows by
                a defined rule (most-recently-updated wins) rather than query order; prune orphaned
                rows on re-upload.
Confidence:     Medium (edge path, reasoned not run).
```

```
[LOW] A stale food_cost.parquet is never cleared when no dish is costable
Location:       web/menu_prices.py lines ~74-76 (rows = build_food_cost_rows(...); if rows: write...)
What's wrong:   write_food_cost_atomic raises ValueError on empty rows, so the caller guards with
                `if rows:`. If a later state yields zero costable dishes (e.g. a BOM re-upload where
                nothing can be fully costed), the old snapshot is left on disk untouched.
Why it matters: The seam retains food-cost rows for a state that no longer holds — violating the
                "current snapshot" contract the leg claims. Minor, no consumer yet.
Fix:            When rows is empty, atomically write a valid empty artifact (or remove the file)
                instead of silently keeping the prior one.
Confidence:     Medium (reasoned).
```

```
[NIT] Menu-price validation error surfaces the internal seam key, not the dish's display name
Location:       web/app.py::_parse_menu_price_form (errors.append(f"{dish_id}: ..."))
What's wrong:   On a bad price the operator sees "caesar salad: menu price must be a positive number"
                (the normalized key) rather than the dish's real display name.
Why it matters: Minor "speak the operator's language" (rule 06) nit — readable enough to be cosmetic,
                but the display name would be cleaner.
Fix:            Map dish_id -> dish_name from the current BOM when composing the message.
Confidence:     High.
```

```
[NIT] Stale type hint on build_grid's parameter
Location:       src/report/grid.py::build_grid (dish_costs: dict[UUID, tuple])
What's wrong:   The tenant path passes str-keyed dicts. DishResult.dish_id was correctly widened to
                UUID | str this phase, but build_grid's parameter hint still says dict[UUID, ...].
Why it matters: Cosmetic; Python doesn't enforce it. Keep annotations honest.
Fix:            Widen to dict[UUID | str, tuple].
Confidence:     High.
```

**Isolation note (documented + fenced, not a numbered finding):** `/dishes`, `/dishes/{id}`, and the
food-cost recompute read the *global*, unpartitioned `data/raw/` seam combined with per-tenant menu
prices. This is the documented W9 deferral, and W5's `create_account` fences the system to exactly one
restaurant (verified the fence exists). No live cross-tenant leak today. Worth stating plainly: **W6
raises the blast radius of that fence** — menu prices now make margins reconstructable, so if the W5
fence ever regressed, a second tenant's `/dishes` would show tenant A's costs *and* margins. Isolation
on these routes now leans entirely on that one fence.

---

## Step 5 — Sign-off

- **VERDICT: No — does not meet W6's acceptance criteria as written.** The functional slice
  (menu-price capture, costed grid, dish detail, the `food_cost` seam leg through `schemas/`) is built
  and works, and the seam discipline is clean. But the phase's own honest-precision invariant
  (overview §5.3 / rule 06: "reconciles by eye") is violated — the grid and the dish-detail page show
  different plate costs and margins for the same dish (BLOCKER-1, verified by running) — and the
  transparency surface hides a leg it now sends to the engine (MAJOR-1). Both hit the two things W6
  most had to get right: a reconciling number and an honest data story. Neither is expensive to fix.

- **TEST + LINT (observed):**
  - `make test` (`python -m pytest -q`): **521 passed, 4 warnings, 0 failed** (~17s). The warnings are
    pre-existing pandas deprecations in `forecasting/tests`.
  - `make lint` (`ruff check .`): **All checks passed.**
  - Boundary test `tests/test_module_boundaries.py`: **5 passed** — verified it would fail on a planted
    `forecasting` import or `_truth` reference in `onramp/**` (`.py` + web assets).
  - Note: green suite despite BLOCKER-1 because the relevant test uses a single-ingredient dish
    (MINOR-5) — the tests pass *around* the bug, not through it.

- **TOP 3 FIXES (priority order):**
  1. **BLOCKER-1 + MAJOR-2 together:** move the dish-detail costing into one pure `src/costing`
     function sharing a single rounding discipline with the grid, so both screens (and the seam value)
     agree on ~Cost / Margin / Food-cost; show per-line at real cents.
  2. **MAJOR-1:** disclose (and export) the new `food_cost` leg on `/your-data` so "what we send the
     engine" is complete and menu_prices.html's cross-reference stops misdirecting.
  3. **MINOR-5 (+ MINOR-3):** add a multi-ingredient reconciliation test so this rounding regression
     can't pass CI again; also recompute+write `food_cost` on invoice confirm so the derived leg
     doesn't go stale after a price change.

- **WHAT I COULD NOT VERIFY (even after trying):**
  - The per-dish *dollar magnitude* of BLOCKER-1 on this operator's real menu — `data/raw/` holds no
    seeded tenant BOM, so I proved the divergence with representative inputs via the real compute
    functions rather than by rendering the production pages. Mechanism and a concrete divergence are
    confirmed; the size depends on the tenant's recipes.
  - Whether "opportunities computed from own legs + prices" was truly required *this* phase — the
    acceptance wording is genuinely ambiguous; the builder's deferral is defensible. Recorded as a
    verdict nuance, not a finding.
  - The Alembic migration applied against a live DB — I read `0002_add_dishes_table.py` (it matches the
    `Dish` model: id/restaurant_id/dish_name/menu_price/timestamps, FK, unique(restaurant_id,dish_name))
    but the 521 tests build schema from `Base.metadata`, so the migration itself is not exercised.
  - WCAG-AA contrast / responsive behavior on the money figures — explicitly W8, not audited, not
    gating W6. LOW-6 / MINOR-6 are reasoned from code, not run against a live re-upload sequence.

- **SINGLE BIGGEST RISK:** A chef clicks a dish on the grid to audit its cost and the "audit" page
  shows a *different* (and inflated) plate cost and margin than the grid did — the provenance surface
  silently contradicting the headline number, on the one screen whose whole job is to earn trust.

**Rules:** The seam discipline, atomic full-replace write, defensive form parsing, and calm
correlation-id error handling are genuinely well done — reused primitives, no hand-rolled writes, no
leaks. That craft is exactly why the two display/trust gaps stand out.
