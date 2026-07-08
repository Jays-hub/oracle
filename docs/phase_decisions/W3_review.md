# W3 Review — Insight & price (adversarial)

Reviewer: web-reviewer (adversarial, read-only over code). Built 2026-07-05, reviewed 2026-07-06.
Diff base: working tree (detached HEAD), scoped to the W3 files in `git status`. Confirmed against
`website_vision.md` §8 (W3 = "Invoice ingestion (post-gate), price-trend alerts, the opportunities
surface") and `onramp/README.md`'s on-ramp contract.

---

## Step 0 — What W3 had to deliver ("done when")

- A capture surface for the **invoice / price-history leg** (the 3rd of the engine's 4 data legs),
  writing to a new `data/raw/price_observations.*` seam file **through `schemas/`**, additive to
  the existing BOM + sales legs — the durable capture-funnel half of §8's W3 row.
- **Price-trend detection** (week-over-week ingredient moves) and an **opportunities surface** that
  states plain-language, dollar-quantified findings — the "second hook" of §3 group C.
- All of it obeying the seam firewall (no `_truth`/`interim`/`processed`, no `forecasting/` import),
  the precision discipline (rounded costs, reconcile-by-eye, no fabricated margins), server-side
  auth/tenant scoping, and fail-legibly error handling (rules 05/06/07).

**Spec-vs-code conflicts to surface first (not defects, but read them before the findings):**
1. §8 tags W3 invoice ingestion **"(post-gate)"**, and `plate_cost/CLAUDE.md` discipline #4 says the
   POS-absorption competitive check is a real pre-Phase-2 gate. It is **still unresolved**. The
   builder surfaced it and Jay directed building anyway ("skip the gate, build W3 as scoped"). This
   reads as a deliberate, recorded business call (see LOW-3), not a silent bypass — but the code does
   ship a client-facing invoice surface ahead of a gate the governance calls real.
2. §8 W3 is tagged "Mixed" durable/provisional and the roadmap example headline is *"Beef +16% this
   week → 3 dishes affected → short rib is now your thinnest-margin entrée."* The code deliberately
   drops the margin/tier clause because **no `menu_price` crosses the seam** — a correct, honest
   call (rule 06), well documented. Worth noting the leg W3 captures (ingredient prices) is **not**
   the `food_cost`/`Co` leg the engine actually needs; that still requires menu-price capture, which
   no phase has built. W3 advances the funnel, not yet the engine handoff.

---

## Step 1 — Verify by running

- `conda run -n restaurant-dev python -m pytest -q` (repo root): **400 passed, 4 warnings** (pandas
  deprecation in a forecasting test, pre-existing/unrelated).
- On-ramp subset (`onramp/plate_cost/tests/`): **152 passed**.
- Boundary test (`tests/test_module_boundaries.py`): **4 passed**. It `rglob`s all of `onramp/**.py`
  (so the new W3 modules are in scope) and would catch a planted `forecasting` import or `_truth`
  text reference in any of them.
- `ruff check .`: **All checks passed.**
- `lint-imports` (import-linter): **2 contracts kept, 0 broken** — the onramp↔forecasting no-code-
  coupling contract holds with the new modules.
- Ran the pure compute and the `/insights` route directly against staged sample data (see Step 3) —
  this is how MAJOR-1 was confirmed as a real 500, and how reconciliation + idempotency were
  confirmed as correct.

Test/lint claims in the progress log and decision log matched what I observed.

---

## Step 2 — Hunt list

| Area | Verdict |
|---|---|
| Seam firewall — writes to `data/raw/` only, no `_truth`/`interim`/`processed`, no `forecasting/` import | **verified-by-running** (boundary + import-lint green; store reads `raw` only; writes go through `PriceObservationRow`) |
| Schema gate — every written row validated before touching the seam | **pass** (`parse_invoice_csv` builds `PriceObservationRow`; `write_price_observations_atomic` only `model_dump`s validated rows; re-validates on `/invoice/confirm`) |
| Store helper structurally `raw`-only | **pass** (`_read_raw_parquet` takes a bare filename, asserts no `/`/`..`, hard-coded `_RAW_DIR`) |
| Layering — compute pure, no web import in `src/{pricing,insights,capture}` | **verified-by-running** (imported and ran `build_opportunities`/`price_trend` with no web layer) |
| False precision — costs on the $0.25 grid | **verified-by-running** (happy path: prior=3.25, new=3.75, delta=0.50, all on-grid) |
| Numbers reconcile by eye (`Menu − ~Cost = Margin`) | **verified-by-running** — delta derived from the **rounded** prior/new (`_display_opportunity`); reconciles. But see MINOR-2 (counterfactual "prior") |
| Placeholder/sample data labeled | **pass** (insights/invoice templates blank the `sample_banner` block; regression-tested) |
| Provenance reachable | **concern** (opportunity dishes can't expand to recipe-line inputs — LOW-2) |
| Tenant isolation | **concern** — global single-tenant files, `RESTAURANT_ID` unused for scoping (LOW-1); documented W2 deferral, no cross-tenant leak today |
| Firewall/internal leakage to browser | **pass** (no `_truth`, no engine internals, no secrets in markup/payload) |
| Accessibility/responsiveness of money figures | **concern (not fully verified)** — semantic `dl`/`role="alert"` present; did not measure contrast/responsive breakpoints |
| Boundary validation at the door | **pass** (missing-column, bad-row, non-UTF8, empty all rejected legibly with named errors) |
| Error handling — never a bare crash / no leak | **fail → MAJOR-1** (`GET /insights` 500s un-legibly on realistic captured data) |
| Atomic + idempotent seam writes | **verified-by-running** (temp+rename; exact re-submit dedupes to 1 row, incl. null `source_invoice`). Concurrency caveat → MINOR-4 |
| AuthN/AuthZ on every new data path | **pass** (all 3 new routes call `require_login`; added to `test_web_auth.py`) |
| Hostile input | **pass** (bounded `read(MAX+1)`, UTF-8 gate, schema gate; `.csv` accept is a client hint but server validates content) |
| Statelessness | **pass** (base64 round-trip through hidden field; no per-request server state) |
| Tests meaningful for the bug I feared | **concern** — no test exercises the `/insights` crash path (all use convertible `oz/oz` units) |
| Anti-drift | **pass** — thin CSV path, OCR/`src/ingestion/` left gated, no multi-tenant platform, no heavy client framework |

---

## Step 3 — Riskiest spots (looked deliberately, ran them)

1. **`GET /insights` end-to-end costing of the *captured* BOM (new derived-metric route).** This is
   the first surface that runs the captured seam BOM through `convert()` (W0/`/your-data` never
   cost captured data). It is the riskiest new code, and it contains **MAJOR-1**.
2. **`build_opportunities` ceteris-paribus reconstruction (new derived metric).** Correct delta, but
   the absolute "prior"/"new" it displays are counterfactuals and the affected-dish count can
   undercount (MINOR-2, MINOR-3).
3. **`write_price_observations_atomic` accumulate/dedup (new store-write shape).** Idempotency
   verified across a read-back-from-parquet cycle and with a null `source_invoice`; atomic via
   rename. The one real gap is a concurrent-writer lost update (MINOR-4).

---

## Step 4 — Findings

```
[MAJOR] /insights returns a bare 500 (no legible page, no correlation id, no log) on a
        schema-valid but non-convertible BOM unit pair
Location:       onramp/plate_cost/web/app.py  GET /insights (the route has no try/except),
                onramp/plate_cost/web/insights.py::build_insights_summary (catches only
                FileNotFoundError), onramp/plate_cost/src/insights/opportunities.py::
                dish_ingredient_cost -> src/bom/units.py::convert (raises ValueError)
What's wrong:   BomRow (schemas/seam.py) does NOT restrict recipe_unit/canonical_unit to the
                convertible set — any non-empty string validates. convert() raises ValueError on a
                cross-family or typo'd pair (e.g. recipe_unit="each" -> canonical_unit="g", or
                "lbs"/"ounce"). That ValueError propagates: dish_ingredient_cost doesn't catch it,
                build_insights_summary catches only FileNotFoundError, and the /insights route has
                no try/except (unlike /, /confirm, /invoice/confirm, which all render error.html
                with a correlation id). Verified by running: staged a BomRow with each->g plus a
                real +16% beef move, hit GET /insights via TestClient -> status 500,
                body "Internal Server Error", no correlation id, and nothing is logged.
Why it matters: A chef who enters one odd unit on the W1 recipe sheet (there is no convertibility
                check at capture, so the bad row persists into the seam) gets a broken Insights page
                with zero explanation, and support has no correlation id to grep. This violates the
                codebase's own established fail-legibly pattern and rules 06 ("Fail legibly ... never
                a stack trace or a blank page") and 07 ("Friendly, typed failures — never a bare
                crash"). Concept: validate at the edges, but the *edge* here (BomRow) doesn't
                enforce convertibility, so the compute must either treat an unconvertible dish the
                way dish_ingredient_cost already treats a missing price (skip it, non-fatal) or the
                route must wrap the call the way every sibling route does. With default FastAPI
                config the client sees plaintext "Internal Server Error" (no traceback leak), so
                this is MAJOR, not a BLOCKER — but debug=True or a future middleware change would
                turn it into a traceback leak.
Fix:            Minimal: wrap build_insights_summary() in /insights in the same try/except the /
                grid route uses (log with correlation id, return error.html + 503). Better: also
                make dish_ingredient_cost skip a dish whose units don't convert (catch ValueError
                from convert, set priced=False) so one bad recipe line degrades to "that dish
                omitted" instead of taking down the whole surface — mirroring its existing
                missing-price skip. Best (durable): add a convertibility check to the W1 capture
                gate so the bad row never reaches the seam. Add a test with a non-convertible unit
                asserting a 200 legible page or a clean 5xx error.html, not a raw 500.
Confidence:     High (reproduced the 500 via TestClient and the ValueError via direct call).
```

```
[MINOR] Opportunity headline hardcodes "this week" even when the compared prices are far apart
Location:       onramp/plate_cost/src/insights/opportunities.py::Opportunity.headline
                ("... this week — N dish{es} affected"); driven by src/pricing/trends.py::
                price_trend, which picks the prior as the most recent obs AT LEAST lookback_days
                (7) earlier — which can be arbitrarily older than 7 days.
What's wrong:   Verified by running: two beef observations 45 days apart ($3.00 -> $4.20) render as
                "Beef +40% this week — 1 dish affected". The 40% is real; the "this week" is not.
Why it matters: On-screen trust is the product (rule 06: sanity-checkable, honest). A chef who knows
                beef did not jump 40% in a week will distrust the number — or worse, act on a
                phantom weekly spike. False precision about the *timeframe* is as corrosive as false
                precision about the dollars.
Fix:            Either (a) show the actual span ("since your <date> invoice" or "over N days") from
                prior["observed_date"], or (b) only attach "this week" when the gap is actually
                within the lookback window, else drop the temporal claim. The template
                (insights.html) renders o.headline verbatim, so the fix belongs in headline.
Confidence:     High (reproduced the mislabel).
```

```
[MINOR] Displayed "prior"/"new" dish costs are ceteris-paribus counterfactuals, not the dish's
        real cost then vs. now — and can read as historical fact
Location:       onramp/plate_cost/src/insights/opportunities.py::build_opportunities
                (base_prices holds every OTHER ingredient at its LATEST price), surfaced by
                insights.html as "~$24.00 -> ~$28.00 (+$4.00)".
What's wrong:   "prior_cost" is "what this dish would cost now if only the moving ingredient were
                still at last week's price" — every other ingredient is at today's price, not its
                own prior price. So the absolute prior/new are hypotheticals; only the delta is a
                real, isolated figure. The template labels them as a plain prior->new transition
                with no framing.
Why it matters: The delta reconciles and is correct (verified). But a chef reading "Short Rib
                ~$24 -> ~$28" will take $24 as "what my dish cost last week" — which it isn't if any
                other ingredient in that dish also moved. A number a chef can't reconcile against
                their own mental model erodes trust (rule 06: sanity-checkable). This is the
                builder's documented deliberate simplification, but the UI doesn't disclose it.
Fix:            Lead with the delta ("+$4.00 in ingredient cost from this move") and either drop the
                absolute prior/new or label them "estimated ingredient cost (other prices held at
                today's)". A one-line framing on the card is enough.
Confidence:     High (traced the price maps; delta verified correct, framing verified absent).
```

```
[MINOR] "N dishes affected" silently undercounts when an affected dish has an unpriced ingredient
Location:       onramp/plate_cost/src/insights/opportunities.py::build_opportunities /
                dish_ingredient_cost (a dish with ANY ingredient missing from the price map is
                dropped entirely; headline n = len(affected_dishes) counts only fully-costed dishes)
What's wrong:   If beef is in 3 dishes but one of those dishes also uses an ingredient that has no
                price observation yet, that dish is excluded, and the headline says "2 dishes
                affected". The count reflects "dishes we could fully cost", not "dishes affected".
Why it matters: Under-reports the scope of a price move on a surface whose whole job is quantifying
                money on the table. Honest about what it can compute, but the headline claims a
                different thing than it counts.
Fix:            Either count affected dishes from the BOM (all dishes using the moving ingredient)
                and note "(k of them not yet fully priced)", or keep the costed count but change the
                wording to "N dishes costed". Small; pick one and make headline say what it counts.
Confidence:     Medium (traced by code; consistent with the missing-price skip in dish_ingredient_cost).
```

```
[MINOR] Accumulating price-history write is read-modify-write — a concurrent second confirm can
        lose the first's rows
Location:       onramp/plate_cost/src/capture/invoice_upload.py::write_price_observations_atomic
What's wrong:   The function reads the whole existing parquet, concats, dedupes, then atomically
                renames. The rename is atomic, but the read-modify-write is not serialized: two
                overlapping /invoice/confirm requests each read N rows, then each write their own
                N+delta, and the second rename overwrites the first — a classic lost update.
Why it matters: Rule 07 asks for atomic AND idempotent seam writes; idempotency holds (verified) but
                durability under concurrency does not. Today's reality is single-tenant, single dev
                process, so it's latent — but the file is explicitly the "accumulating" leg, and an
                accumulator that can silently drop a committed invoice is the kind of thing that
                bites exactly when a second operator or a retry lands. Concept: read-modify-write on
                shared state needs a lock or an append-only log to be safe under concurrency; a
                rename alone only makes the final swap atomic, not the whole operation.
Fix:            Out of scope to fully solve now (matches the deferred multi-tenant/versioning notes).
                Record it as a known limitation in W3.md's deferrals with the concrete failure mode,
                so it isn't rediscovered as a data-loss surprise. If cheap: a per-file advisory lock
                around the read-modify-write.
Confidence:     High (evident from the code; single-process tests can't exercise it).
```

```
[LOW] Two independent _RAW_DIR constants (read vs. write) are a footgun the builder already tripped
Location:       onramp/plate_cost/src/store.py::_RAW_DIR (reads) vs
                onramp/plate_cost/web/app.py::_RAW_DIR = RAW_DIR (writes, from seam_upload)
What's wrong:   The read path and the write path resolve data/raw/ through two separate module-level
                constants. In production both point at the real .../data/raw so they agree; it is a
                test-isolation and future-refactor trap (a test that writes via one and reads via
                the other must patch both — the builder hit this and documented it).
Why it matters: Not a production bug, but two sources of truth for one path is how a future
                "why is this test reading real data/raw?" afternoon gets lost.
Fix:            Consider a single shared constant (e.g. store exposing RAW_DIR that seam_upload and
                app both import) so there is one path definition. Low priority.
Confidence:     High (read both constants; confirmed the tests patch both where needed).
```

```
[LOW] Opportunities have no provenance drill-down
Location:       onramp/plate_cost/web/templates/insights.html
What's wrong:   Rule 06 asks that any displayed cost expand to its inputs (recipe lines, prices,
                yields). The opportunity dish rows show a delta but can't be expanded to the recipe
                math behind it.
Why it matters: "No black-box numbers" is a stated trust requirement; a chef can't audit the $4.00.
Fix:            Acceptable to defer to the dish-detail/transparency work (W4), but note it — don't
                let "looks done" hide the missing audit path.
Confidence:     Medium (feature-absence by inspection).
```

```
[LOW / PROCESS] POS-absorption gate skipped; client-facing invoice surface ships ahead of it
Location:       docs/phase_decisions/W3.md (Load-Bearing Assumptions); plate_cost/CLAUDE.md #4
What's wrong:   The pre-Phase-2 competitive check (is Toast/Square about to bundle invoice-price
                monitoring for free?) is unresolved. W3 built the thin digital-feed CSV path and
                left src/ingestion/ (the OCR/entity-resolution spend the gate actually guards)
                untouched and gated.
Why it matters: Confirming the review focus ask: this reads as a DELIBERATE, recorded decision (Jay
                directed it via AskUserQuestion; the expensive engineering the gate protects is
                still gated), not an agent quietly building through a documented gate. The residual
                strategic risk: if discovery later shows this is absorbed, it's now a shipped
                client surface (not just deferred code) that gets reshaped.
Fix:            None on the code. Keep the gate visibly unresolved until the competitive check runs.
Confidence:     High (decision log + AskUserQuestion trail corroborate).
```

```
[LOW] Tenant scoping is global-file, not per-tenant (carried forward from W2)
Location:       onramp/plate_cost/src/store.py (reads global data/raw/*), invoice write path,
                web/auth.py::RESTAURANT_ID (unused for scoping)
What's wrong:   /insights and the invoice write operate on single global seam files; RESTAURANT_ID
                is a placeholder and does not scope any read or write.
Why it matters: No cross-tenant leak exists today (one physical tenant), and this is a documented W2
                deferral. But rules 06/07 require server-side per-tenant scoping, so when a second
                restaurant lands, /insights, read_price_observations, and the invoice write ALL
                become leak surfaces at once — none of them are structured to scope yet.
Fix:            Track it with the existing multi-tenant-partitioning deferral; ensure the eventual
                partitioning covers the new price_observations leg and the insights reads, not just
                bom/sales.
Confidence:     High (by inspection; consistent with W2.md).
```

**Genuinely good (one line, per the rules):** the reconcile-by-eye discipline is done correctly —
`_display_opportunity` derives the delta from the rounded prior/new, so the card adds up by eye; the
seam firewall, schema gate, and idempotent dedup are all intact and verified by running.

---

## Step 5 — Sign-off

- **VERDICT:** **No — not yet.** All three §8 W3 deliverables (digital-feed invoice ingestion,
  price-trend detection, opportunities surface) are present and functionally correct, and the
  firewall/precision/reconciliation bars are met. But the opportunities surface (`GET /insights`)
  **does not meet rules 06/07's fail-legibly bar on realistic captured data** — a schema-valid
  recipe with one non-convertible unit takes the whole page down with a bare 500. That MAJOR should
  land a fix before the phase closes. It is not a firewall/tenant/reconciliation BLOCKER.
- **TEST + LINT (observed):** `pytest -q` repo-root **400 passed, 4 warnings**; on-ramp subset
  **152 passed**; boundary test **4 passed**; `ruff check .` **clean**; `lint-imports` **2 contracts
  kept, 0 broken**. Everything green — the MAJOR is *uncovered* by the suite, not failing it.
- **TOP 3 FIXES (priority order):**
  1. MAJOR-1 — wrap `/insights` in the fail-legibly try/except every sibling route uses, and make
     `dish_ingredient_cost` skip an unconvertible dish (catch `convert`'s `ValueError`) so one bad
     unit degrades gracefully; add a non-convertible-unit test.
  2. MINOR-2 — stop labeling every move "this week"; show the real span or drop the temporal claim.
  3. MINOR-3 / MINOR-4 — frame the counterfactual prior/new (lead with the delta) and record the
     concurrent-writer lost-update as an explicit known limitation.
- **WHAT I COULD NOT VERIFY (even after trying):** (a) WCAG-AA contrast and tablet/phone
  responsiveness of the money figures — the templates use semantic markup but I did not measure
  rendered contrast or breakpoints; (b) behavior under genuine concurrent `/invoice/confirm`
  requests — single-process tests can't exercise the lost-update race, so I reason it from the
  read-modify-write code, not from a repro; (c) real-world unit-typo frequency — I proved the crash
  is reachable from a schema-valid BOM, but not how often chefs actually produce a non-convertible
  pair.
- **SINGLE BIGGEST RISK:** one odd unit on a chef's recipe sheet (which the capture gate accepts and
  persists) silently arms a bare 500 on the Insights page the moment a price moves — a trust surface
  that dies with no explanation and no correlation id to debug it.
