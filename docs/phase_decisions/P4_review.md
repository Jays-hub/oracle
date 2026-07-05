# P4 Review — Distribution + the newsvendor turn (adversarial)

Reviewer: phase-reviewer (independent, read-only over code). Date: 2026-07-04.
Diff base: uncommitted working tree over HEAD `9c92a65`. Everything below was **run**, not just read,
in the pinned `restaurant-dev` conda env.

Scope read: `forecasting/docs/construction_roadmap.md` P4, `.claude/rules/01–04`, `data/CONTRACT.md`,
both `CLAUDE.md`, `.importlinter`, and the P4 source + tests. Metrics reproduced:
`newsvendor_floor.py`, `calibration.py`, `make test`, `make lint`, `make import-lint`.

---

## Step 0 — What P4 had to deliver (in my words)

- A **calibrated predictive distribution** per item (quantile regression, pinball objective, multiple
  levels, non-crossing enforced), not just a point estimate.
- The **newsvendor turn**: convert that distribution to a prep quantity `Q* = F⁻¹(q*)`,
  `q* = Cu/(Co+Cu)` per item, plus expected waste `E[(Q−D)⁺]` and stockout `E[(D−Q)⁺]` as integrals of
  the distribution.
- **Dollar-gated "done when" (two conjunctive conditions):** (1) quantiles **calibrated against
  `_truth/`**, AND (2) **realized newsvendor dollar cost beats the Phase-2/3 point-model-as-mean
  baseline**. This is "the product in miniature" — barely ML, an OR idea plus a quantile read-off.

No spec/intent conflict in the build itself. One framing gap surfaced (see MAJOR-1): the gate is
described as beating a "Phase-2/**3**" baseline, but as executed P3's contribution is out of scope.

---

## Step 1 — Ran it

- `make lint` → **All checks passed** (ruff).
- `make import-lint` → **2 contracts KEPT** (engine-truth-firewall + seam-independence). The
  `decision → evaluate` ban is real and enforced; the only carve-out is `models.baselines →
  evaluate.objective`, so a planted `decision → evaluate` import would break the build. Verified the
  contract's `source_modules` actually lists `forecasting.src.decision`.
- `make test` → **316 passed, 4 warnings, 0 failed** (~10s). The 4 warnings are a pandas-3 deprecation
  in `test_simulator.py`, unrelated to P4.
- `python -m forecasting.src.evaluate.newsvendor_floor` → **PASS**: quantile+newsvendor **$117,536.08**
  vs point-as-mean **$133,121.17**, win **$15,585.09**, positive in all 4 folds. Reproduced to the penny.
- `python -m forecasting.src.evaluate.calibration` → **PASS**: coverage within tolerance at all 19
  levels, PIT mean 0.499 / std 0.323, MAPIE CQR coverage 0.786 at target 0.80.

Firewall spot-checks (ran): no `_truth`/`truth_demand` reference anywhere under
`forecasting/src/{models,decision,features,data}`; no absolute paths in the 4 new source files; `mapie==1.4.1`
and `scikit-learn==1.9.0` pinned in `requirements.lock.txt`.

---

## Step 2 — Hunt list

- **Data leakage (decision-time):** PASS. `predict_quantiles` uses `check_leakage=True`; the pipeline's
  `.shift(1)`-before-`.rolling()` discipline is intact; the backtest's `leakage_canary` runs per fold and
  the split constructor hard-fails on `test_min <= train_max`. Verified the canary is invoked.
- **Target/label leakage:** PASS. Target is `unconstrain_demand(clean_demand())`; unconstraining uses an
  expanding-window (`.shift(1)`), never the oracle. Calibration scores against `truth_demand` (true,
  uncensored) — the correct ruler.
- **Split integrity:** PASS on disjointness/ordering, **CONCERN on placement** — see MAJOR-1. Rolling-origin,
  4 folds, expanding window, test strictly after train. But all 4 folds sit in the first 196 days.
- **The dollar verdict:** PARTIAL. Judged by realized `Σ(Co·overage+Cu·underage)` (correct, not MAPE/RMSE);
  newsvendor beats point-as-mean. But the gate window structurally excludes the go-forward/censored period
  (MAJOR-1), so it does not actually exercise the "Phase-2/**3**" baseline it claims to beat.
- **Reproducibility:** PASS. `random_state=42` throughout; `test_same_seed_twice_gives_identical_predictions`
  passes; deps pinned; no notebook-order dependence.
- **Data integrity / dtypes:** PASS. Non-negativity clamped; forecasts non-crossing via `np.sort`; date
  coercion consistent across the merge.
- **Seam firewall:** PASS. Only `evaluate/calibration.py` reads truth, guarded by `_assert_truth_only`.
  `decision/newsvendor.py` is pure math with zero data deps. Import-linter enforces it.
- **From-scratch math (waste/stockout integrals):** PASS on correctness (hand-verified against
  Uniform(0,100) closed form), MINOR on the truncation bias (MINOR-4).
- **Non-crossing (rule 03):** PASS — post-hoc rearrangement is a valid rule-sanctioned fix; the read-off
  happens on the monotonized curve.
- **Anti-drift:** PASS. No premature parametric distribution, no joint multi-quantile model, no registry.
  Scope matches "barely ML."
- **prep_type routing (rule 04):** FAIL (minor in context) — see MINOR-3.
- **Calibration granularity/robustness:** CONCERN — MINOR-2 / MINOR-5.

---

## Step 3 — Riskiest spots, and what I found

1. **The dollar-gate backtest window** (`RollingOriginBacktest.splits`, reused by `newsvendor_floor.py`).
   This is where the phase's whole verdict lives. Looked deliberately, ran it: the folds never leave
   spring 2022. **This is the real finding (MAJOR-1).**
2. **The "reproduces $133,121.17 exactly" claim.** The builder reads this as proof the wiring is correct.
   Traced it: it reproduces exactly *because* clean and unconstrained targets are identical over the tested
   window (all 66 censored rows are in 2024). The exact match is a symptom of a blind spot, not a validation.
3. **Calibration tails vs. the newsvendor read-off.** The read-off queries high quantiles (q* up to 0.81);
   if the upper tail is under-covered, prep under-buffers. Ran calibration: mild under-dispersion, within
   tolerance but directionally the wrong way for the tail the product depends on (MINOR-2).

---

## Step 4 — Findings

```
[MAJOR] Dollar gate only ever evaluates the first ~196 days; the go-forward/censored window is never scored
Location:       forecasting/src/evaluate/backtest.py :: RollingOriginBacktest.splits (anchored at all_dates[0]);
                consumed by forecasting/src/evaluate/newsvendor_floor.py :: compute_newsvendor_floor
What's wrong:   The series is 912 days (2022-01-01 → 2024-06-30). With n_folds=4, test_weeks=4,
                min_train_weeks=12, splits() anchors every fold at the series START, so the four test
                windows are 2022-03-26..04-22, 04-23..05-20, 05-21..06-17, 06-18..07-15. All of 2023 and
                2024 — ~78% of the data, and the ENTIRE go-forward window where the 86-log/censoring lives —
                is never trained on or scored. I ran splits() on the real series to confirm the exact dates,
                and confirmed all 66 censored rows fall in 2024-04-05..06-30, i.e. ZERO inside any evaluated
                fold. That is the mechanical reason point-as-mean reproduces P2's $133,121.17 to the penny:
                clean_demand() and unconstrain_demand(clean_demand()) are IDENTICAL over the tested window,
                so P3's unconstraining is a complete no-op for this gate.
Why it matters: Two consequences. (1) The phase's "done when" says beat the "Phase-2/3 point-model-as-mean
                baseline", but as executed it beats a Phase-2-only baseline — P3's contribution is provably
                absent from the number. (2) The verdict rests on the oldest, least representative slice of
                the data (thin lag history, pre-drift menu era) and never touches the actual product horizon.
                The builder's decision log cites the exact reproduction as "confirming the shared-target
                backtest is wired correctly"; it actually confirms the gate is blind to the exact rows P3
                exists to fix. Concept: rolling-origin CV should place folds so the LAST test window lands at
                (or near) the series end, maximizing training history and testing on the most recent, most
                decision-relevant period. Anchoring all folds at the start is valid (non-leaking) but wastes
                the data and evaluates the wrong era.
                NOTE — not a BLOCKER: the newsvendor-beats-mean CONCLUSION still holds on the tested window,
                and the mechanism generalizes (all 11 items have q*>0.5, so prepping above the mean cuts the
                dominant underage cost). If anything the win would likely be LARGER on the heavier-tailed
                go-forward window — but that is an inference I did not run, which is exactly why the gate
                should be re-run there.
Fix:            Re-run the P4 dollar gate on a window that includes the go-forward period — either offset the
                fold anchor so the last test fold ends at all_dates[-1] (slide, don't just expand), or add
                folds so the series end is covered, or set min_train_weeks large enough that the 4 folds land
                in 2024. Then re-state the headline number and confirm the win persists where censoring/
                unconstraining actually bite. This is a P1-harness limitation P4 inherited; fixing it in the
                harness fixes P2/P3 gates too.
Confidence:     High (ran splits() and the gate on the real series; located every censored row's date).
```

```
[MINOR] Predictive distribution is mildly under-dispersed; upper tail (the newsvendor's read-off region) is under-covered
Location:       forecasting/src/models/quantile.py (spread of the fitted quantiles);
                observed in forecasting/src/evaluate/calibration.py output
What's wrong:   Ran calibration: empirical coverage sits ABOVE nominal at low quantiles (0.05→0.117,
                0.10→0.177, 0.25→0.328) and BELOW nominal at high quantiles (0.90→0.867, 0.95→0.898,
                0.99→0.935). PIT std is 0.323 vs the Uniform(0,1) target of 0.289 — a U-shaped PIT, the
                signature of intervals that are too tight. MAPIE CQR coverage 0.786 < 0.80 undershoots in
                the same direction.
Why it matters: Within the 0.15 checkpoint tolerance, so the gate passes — but the direction matters. The
                newsvendor reads F⁻¹(q*) at q* up to 0.81; an under-covered upper tail means the prep
                quantity systematically under-buffers the true right tail, i.e. slightly more stockouts than
                the nominal service level promises. Some of this is an artifact: the block backtest predicts
                a 28-day window in one call, so lag_1/lag_7 are mostly NaN and the model leans on
                categoricals, narrowing the spread (same degradation documented in point.py). Concept:
                calibration is a credibility instrument — "90% sure" must mean right 90% of the time; a
                confidently-narrow distribution is worse than an honest wide one.
Fix:            No blocker. Note it explicitly; consider reporting calibration on the realistic day-ahead
                regime (day_ahead_eval.py's extend_history replay) so the spread isn't understated by lag
                degradation, and watch the upper-tail coverage when Phase 8 monitoring lands.
Confidence:     High (ran the calibration checkpoint; numbers above are from this run).
```

```
[MINOR] Dollar gate applies the dish-count newsvendor to made_to_order items (rule 04 prep-type routing not applied)
Location:       forecasting/src/evaluate/newsvendor_floor.py :: _NewsvendorAdapter.predict
                (and forecasting/src/decision/newsvendor.py has no prep_type awareness)
What's wrong:   The adapter computes prep_quantity = F⁻¹(q*) for ALL 11 configured items. But config/items.yaml
                marks 4 of them made_to_order (wild_mushroom_risotto, classic_caesar_salad,
                pappardelle_bolognese, tuna_tartare). Rule 04 is explicit: the dish-count newsvendor math
                applies to batch items ONLY; made_to_order routes to ingredient par logic (Phase 7) and must
                never get a "make N portions" number. Those 4 items also carry the HIGHEST q* values
                (0.786/0.812/0.731/0.684), so they contribute materially to the headline win.
Why it matters: For the dollar GATE the effect is symmetric (both arms compute prep for all items), so the
                win DIRECTION is unaffected — hence MINOR, not MAJOR. But the reported $117,536 vs $133,121
                figures mix batch and made_to_order, and the decision layer has no prep_type routing even
                though config.py's own docstring anticipates decision/ doing exactly that. The prep sheet
                (Phase 8) cannot ship this way. Concept: the batch/made-to-order fork changes which decision
                OBJECT an item gets; flattening it prints prep quantities nobody would batch.
Fix:            Either restrict the P4 gate to batch items (and report the batch-only number), or add a
                prep_type filter in the decision/adapter layer now so the fork exists before Phase 8. At
                minimum, state that the current gate number is over a mixed set.
Confidence:     High (read the config; confirmed 4 made_to_order items and their q* values by running).
```

```
[MINOR] Calibration checkpoint is a single tail holdout and aggregates coverage across items, not per-item
Location:       forecasting/src/evaluate/calibration.py :: _train_test_tail_split, empirical_coverage
What's wrong:   The checkpoint trains on all-but-last-4-weeks and tests on that one tail. Rule 03 asks for
                rolling-origin (>=4 folds) for evaluation and for reliability diagrams / underage-rate checks
                PER ITEM. empirical_coverage groups only by quantile level (n=616 = 11 items x 2 periods x 28
                days aggregated), so a single badly-calibrated high-Cu item can be masked by the pool.
Why it matters: A single window can be luckily-good or unluckily-bad; per-item calibration is where the
                money is (rule 03: "empirical underage rate should approximate (1-q*) per item"). This is a
                diagnostic, not the dollar gate, and the roadmap "done when" only says "calibrated against
                _truth" — so it PASSES the letter — but it is weaker than rule 03's stated intent.
Fix:            Add a per-item coverage/underage breakdown at each item's own q*, and ideally evaluate
                calibration across the same folds the dollar gate uses (once MAJOR-1 is fixed).
Confidence:     High (read and ran the checkpoint).
```

```
[MINOR] expected_stockout truncates at the top fitted quantile, biasing the reported stockout low
Location:       forecasting/src/decision/newsvendor.py :: expected_stockout / _integrate_cdf
What's wrong:   E[(D-Q)^+] is integrated only up to xs[-1] (the 0.99 forecast), treating F≈1 beyond it, so
                probability mass in the top 1% tail is dropped. The math is otherwise correct — I verified
                the trapezoidal integration against the closed-form Uniform(0,100) identities and the
                E[(Q-D)^+]-E[(D-Q)^+] = Q-E[D] structural identity; both hold.
Why it matters: Builder-acknowledged and NOT used in the dollar gate (only prep_quantity is), so it does not
                touch the verdict. But expected_stockout is pitched as the "free waste/stockout byproduct"
                for the chef, and that number is systematically optimistic (under-states stockout), worst for
                a hypothetical item whose q* sits near the grid edge. All current items are comfortably
                inside [0.05,0.95] so the effect is small today.
Fix:            Document the downward bias where the byproduct is surfaced, or extend the top anchor / add a
                light tail assumption before this feeds an operator-facing number in Phase 8.
Confidence:     High (ran the newsvendor unit tests; re-derived the identity).
```

```
[NIT] critical_ratio duplicated in decision/newsvendor.py rather than imported from evaluate/objective.py
Location:       forecasting/src/decision/newsvendor.py :: critical_ratio
What's wrong:   A one-line reimplementation of evaluate/objective.py's identical function.
Why it matters: Two copies of q*=Cu/(Co+Cu) can drift. I agree with the builder's call here: the
                import-linter firewall genuinely forbids decision→evaluate, extending the carve-out is a
                larger and more permanent structural change than duplicating stable closed-form
                microeconomics, and both copies are unit-tested. Lowest-priority; flagging only for the
                record since the builder asked for a second opinion.
Fix:            None required. If it ever matters, hoist the formula into a shared dependency-free module
                both decision/ and evaluate/ may import (not evaluate/objective.py).
Confidence:     High.
```

**Genuinely good (one line):** the seam firewall, non-crossing rearrangement, reproducibility seeding, and
the independent-MAPIE-cross-check design are all correct and the import-linter contract really would catch a
planted decision→evaluate leak.

---

## Step 5 — Sign-off

- **VERDICT:** **Yes, with a material caveat.** Both dollar-gated conditions reproduce and PASS as written
  (calibration against `_truth/` on the recent tail; newsvendor $117,536.08 < point-as-mean $133,121.17,
  win in all 4 folds). BUT the dollar gate is evaluated entirely on spring-2022 data and never touches the
  go-forward/censored window, so it does not actually demonstrate beating the *Phase-2/3* baseline it claims
  (P3's unconstraining is a no-op in-window). The newsvendor conclusion is sound; the gate as run is weaker
  than represented. I'd re-run the gate on a go-forward-inclusive window before calling this demo-ready.
- **TEST + LINT:** `make test` → **316 passed, 4 warnings, 0 failed**. `make lint` → **clean**.
  `make import-lint` → **2 contracts kept, 0 broken**. All observed directly.
- **TOP 3 FIXES (priority order):**
  1. Re-run the dollar gate on a window that includes the go-forward/censored period (slide the fold anchor
     to the series end); re-state the headline number (MAJOR-1).
  2. Apply prep_type routing so made_to_order items don't get a dish-count Q*, or report a batch-only gate
     number (MINOR-3).
  3. Add per-item calibration (coverage/underage at each item's own q*) and watch the under-covered upper
     tail (MINOR-2 / MINOR-5).
- **WHAT I COULD NOT VERIFY (even after trying):** whether the newsvendor win *persists or grows* on the
  go-forward window — the harness will not evaluate there without a code change I am not permitted to make,
  so my "likely larger" is inference, not a measured result. I also did not independently re-derive MAPIE's
  internal conformalization; I confirmed its coverage output only.
- **SINGLE BIGGEST RISK:** the dollar verdict is quietly established on the oldest ~20% of the data and never
  on the window where censoring and unconstraining live — so "beats the Phase-2/3 baseline" reads as proven
  when P3's contribution was never in scope, and the exact $133,121.17 reproduction the builder trusts is the
  fingerprint of that blind spot, not a proof of correctness.
```
```
