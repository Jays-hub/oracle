# P3 Adversarial Review — Censored-demand unconstraining

Reviewer: `phase-reviewer` (adversarial, read-only over code). Date: 2026-07-02.
Diff base: uncommitted working tree (new: `unconstrain.py`, `unconstrain_check.py`,
`unconstrain_floor.py`, `test_unconstrain.py`; modified: `progress_log.md`, `requirements.txt`).

## Phase in my own words (Step 0)

- **Deliver:** recover true demand on sold-out (censored) day-items so the modeling target stops
  systematically understating popular dishes, using a censored-regression / Tobit-style method, and
  fold the corrected demand back into the target.
- **Dollar-gated "done when" (the bar):** two conjoined conditions — (1) on the go-forward window,
  recovered demand tracks `truth_demand` on capped days, **and** (2) popular-item dollar cost
  **improves** vs. Phase 2.
- No spec/intent conflict in the correction algorithm itself. There **is** a conflict between the
  delivered dollar-gate's *verdict* ("FAILS, -$3,533.87") and what the phase's work actually achieves
  when measured correctly (a **~$1,507 improvement**) — see BLOCKER-1. That conflict is the headline.

---

## Step 2 — Hunt-list verdicts

- **Data leakage (features/decision-time):** PASS (verified by running + logic). Every statistic is
  `.expanding().shift(1)` per group; `test_correction_is_prefix_stable` proves truncating the series at
  a censored row reproduces its correction. No same-day actuals, no weather, lag >= 1.
- **Target/label leakage:** PASS. Censored positions are NaN-masked out of the distribution fit, so the
  fit sees only genuine uncensored sales; the cap used is the row's own observed value (available at that
  row). Recovery only raises the target (`max(observed, estimate)`), never fabricates below the bound.
- **Split integrity:** PASS. Rolling-origin, `n_folds>=4` enforced, test strictly after train,
  `leakage_canary` fires inside `run()`. No random k-fold.
- **The dollar verdict:** **FAIL — BLOCKER-1.** The gate scores the clean arm against the *capped*
  actual and the unconstrained arm against the *corrected* actual — two different rulers — which
  fabricates the reported regression. On any single common ruler (incl. oracle true demand)
  unconstraining WINS by $1,507.15.
- **Reproducibility:** PASS (verified). Deterministic (MoM, seed=42); my independent re-run reproduced
  the gate's two numbers to the cent.
- **Data integrity / dtypes:** PASS. Output `demand` is float64 (documented, correct — mixes int sales
  with fractional estimates), `censored` bool, explicit NaN handling, missing-column `ValueError`.
- **Seam firewall:** PASS (verified). No `_truth` substring anywhere under
  `forecasting/src/{data,features,models,decision,report}`; `unconstrain.py` imports only
  numpy/pandas/scipy; `unconstrain_check.py` (the sanctioned second oracle reader) sits in `evaluate/`
  with a `_assert_truth_only` path guard. `test_module_boundaries.py` passes.
- **ML implementation correctness:** PASS (verified). Method-of-moments NegBin is correct (I checked the
  mean/variance identities: `nbinom(r, p)` with `r=m^2/(v-m)`, `p=r/(r+m)` reproduces mean=m, var=v);
  Poisson fallback when `var<=mean`; `E[D|D>cap]` via `dist.expect(lb=cap+1, conditional=True)` matches
  the `sf(cap)` conditioning set; underflow guard returns `cap+1`. The test re-derives the expectation
  independently via scipy (not a tautology).
- **Software engineering / tests:** PASS on `unconstrain.py` (12 meaningful tests). GAP: nothing tests
  the *gate's* comparison fairness — the one place the real defect lives (see BLOCKER-1 fix).
- **Anti-drift:** PASS. The MoM tail-expectation is the right level; full parametric Tobit MLE was
  correctly deferred. Good restraint.

---

## Step 3 — Riskiest spots I looked at deliberately

1. **`unconstrain_floor.py::compute_unconstrain_floor` — the clean vs. unconstrained comparison.** This
   is where the phase's dollar conclusion is produced, and it is where the defect is. The two arms are
   scored against different `demand_df`s (hence different "actual" columns). Found and confirmed by
   running (BLOCKER-1).
2. **`_tail_conditional_mean` — the from-scratch count-distribution math.** Verified correct against the
   NegBin moment identities and against the test's independent scipy re-derivation. The residual
   post-recovery bias (-1.70) is consistent with the un-modeled seasonal uplift (censored days cluster in
   spring/summer; the fit blends all months) — conservative, not a defect, and the `max(observed,est)`
   floor keeps it safe.
3. **The `.expanding().shift(1)` prefix-stability (target-leakage surface).** Ran the truncation logic
   through the test and by hand; holds. No leak.

---

## Step 4 — Findings

```
[BLOCKER] P3 dollar gate compares the two arms against different "actual" rulers — the reported failure is a measurement artifact; unconstraining actually WINS in dollars
Location:       forecasting/src/evaluate/unconstrain_floor.py, compute_unconstrain_floor() lines 140-145
                (via forecasting/src/models/baselines.py::score_predictions, which scores forecasts
                against test_demand_df["demand"]).
What's wrong:   The clean arm runs the backtest on clean.drop(columns=["censored"]) — so its scored
                "actual" is the CAPPED demand. The unconstrained arm runs on
                unconstrained.drop(columns=["censored"]) — so its scored "actual" is the CORRECTED
                (higher) demand. The two models are therefore graded against DIFFERENT answer keys. On
                exactly the censored test days, the unconstrained arm's actual is raised while the clean
                arm's is left artificially low, so the unconstrained arm mechanically accrues more
                underage cost for hitting the same predictions. The reported headline —
                clean $102,050.21 vs unconstrained $105,584.08, "-$3,533.87" — is
                clean_vs_CAPPED compared against unconstrained_vs_CORRECTED. I reproduced both numbers to
                the cent and confirmed they come from different rulers.

                When BOTH arms are scored against a SINGLE common ruler (I ran all three; same 4 folds,
                same fold placement, seed 42):
                  - vs ORACLE TRUE demand:  clean 109,809.21 | unconstrained 108,302.06 | +1,507.15
                  - vs CORRECTED (both):    clean 107,091.23 | unconstrained 105,584.08 | +1,507.15
                  - vs CAPPED (both):       clean 102,050.21 | unconstrained 100,543.06 | +1,507.15
                Unconstraining IMPROVES popular-item dollar cost by $1,507.15 on every common ruler,
                including the honest oracle-true-demand ruler. The gate's own fold decomposition already
                hinted at this: the "no censored test day" rows (identical actuals in both arms) were
                flat-to-slightly-better for unconstrained (30,737.88 -> 30,615.88); the entire "loss" was
                on the "touching a censored test day" rows, i.e. exactly the rows where the ruler differs.
Why it matters: This inverts the phase's headline conclusion and its dollar-gated "done when." The
                builder correctly argues that scoring a model against a still-capped actual is perverse
                ("charges overage for demand that was genuinely there") — but then applies honest scoring
                ONLY to the unconstrained arm and leaves the CLEAN arm on the perverse capped ruler,
                which is the opposite of a fair fight. Concept: a dollar comparison of two forecasts is
                only valid if the actual (the answer key) is held fixed; changing the label between arms
                measures the label change, not the model. The false "fail" then propagates into the
                durable record (progress_log.md, docs/phase_decisions/P3.md, the unconstrain_floor.py and
                point.py docstrings), all of which now tell Jay "P3's dollar gate fails, Phase 4 will fix
                it" — a conclusion that is not true.
Fix:            Score BOTH arms against ONE fixed actual. Best (and sanctioned, since unconstrain_floor.py
                lives in evaluate/): use oracle true demand on the go-forward window as the scored actual
                for both models — that is the honest realized-cost test the roadmap asks for. If a
                truth-free gate is preferred, score both arms against the SAME observable series (either
                both vs corrected, or both vs capped) — both still show unconstraining winning by
                $1,507.15. Then flip the pass/fail logic accordingly, correct the progress_log/P3.md
                narrative, and add a regression test asserting the gate scores both arms on a common
                ruler (the current 12 tests cover unconstrain.py but nothing guards the gate's fairness).
Confidence:     High (ran it; reproduced the gate's numbers to the cent and the corrected comparison
                across three rulers).
```

```
[MINOR] Two of 66 observable censored rows fall outside every test fold
Location:       forecasting/src/evaluate/unconstrain_floor.py::_min_train_weeks_reaching_tail (lines 75-84)
What's wrong:   min_train_weeks = (total_days - test_span_days)//7 uses integer-week truncation, so the
                test window ends 2024-06-28 while censored rows run through 2024-06-30. 64 of 66 censored
                rows land in the test folds; the last 2 days are silently excluded.
Why it matters: Small coverage gap in the go-forward window the phase is specifically meant to validate.
                It does not change the BLOCKER-1 conclusion (both arms use identical folds), but it means
                the gate slightly under-samples the very window it targets.
Fix:            Anchor the last fold's test_end to the series max date (or add the truncated remainder
                days to the final test window) so the full go-forward tail is scored.
Confidence:     High (ran it; printed the fold window and the excluded rows).
```

```
[NIT] Reported capped-MAE (5.28) doesn't match the actual run (5.076) and is internally inconsistent
Location:       forecasting/src/models/unconstrain.py docstring (line ~23-27); docs/phase_decisions/P3.md;
                docs/progress_log.md ("5.28 -> 3.09", "bias -5.08").
What's wrong:   unconstrain_check reports capped MAE 5.076 (bias -5.076), recovered MAE 3.090 (bias
                -1.699). The docs state capped MAE 5.28. Because every censored capped error has the same
                sign, MAE must equal |bias|, so the doc's own "MAE 5.28 / bias -5.08" pair is
                self-inconsistent.
Why it matters: Cosmetic; the recovered=3.09 headline and the direction of the result are correct.
Fix:            Refresh the quoted numbers from the current run (5.076 -> 3.090).
Confidence:     High (ran unconstrain_check).
```

---

## Step 5 — Sign-off

**VERDICT:** No — **as delivered** the phase does not meet its dollar-gated acceptance criteria, but for
a *measurement* reason, not a modeling failure. Condition (1) of "done when" (recovered demand tracks
truth on capped days) is genuinely met: MAE 5.076 -> 3.090, bias -5.076 -> -1.699. Condition (2)
(popular-item dollar cost improves vs. Phase 2) is **actually met too** — I measured +$1,507.15 on a
common ruler — but the committed gate mismeasures it, reports a false -$3,533.87 regression, exits 1, and
the durable docs conclude "fails." The correction algorithm (`unconstrain_demand`) is sound and should
ship; the gate (`unconstrain_floor.py`) and the narrative around it must be fixed before P3 can honestly
close. The fix is small and will flip the verdict to a legitimate pass.

**TEST + LINT:** `make test` → **232 passed, 4 warnings** (5.38s, pandas deprecation warnings in an
unrelated simulator test). `make lint` → **All checks passed!** The phase's own metrics:
`unconstrain_check` → PASS (recovered MAE 3.090 < capped 5.076). `unconstrain_floor` → exits 1
("FAILED"), which is the false negative described in BLOCKER-1.

**TOP 3 FIXES (priority order):**
1. **BLOCKER-1** — score both gate arms against one fixed actual (oracle true demand preferred; both-vs-
   corrected or both-vs-capped also work). Then correct the pass/fail logic and the progress_log/P3.md
   conclusion, and add a regression test guarding gate fairness.
2. **MINOR-1** — extend the last test fold so the full go-forward tail (through 2024-06-30) is scored.
3. **NIT-1** — refresh the quoted MAE/bias numbers in the docstring and decision docs.

**WHAT I COULD NOT VERIFY:** I could not directly `head` the `_truth/` CSVs (correctly blocked by the
truth-access hook); I read the oracle only through the sanctioned `evaluate/` reader inside a scratch
script, which is the intended path. I did not independently re-derive the LightGBM internals — I trust
the Poisson objective and seed as configured, having confirmed determinism by reproducing the gate
numbers exactly. My "oracle true demand" ruler treats non-censored days' clean demand as true (correct
for at-or-below-cap days) and replaces only the observable censored days with `true_demand`; silent
historical 86s remain capped in all arms equally, so they cannot bias the *relative* comparison.

**SINGLE BIGGEST RISK:** The phase ships a dollar gate whose numbers look precise and are reported
"honestly," but which compares two forecasts against two different answer keys — so the durable record
tells Jay unconstraining *loses* $3.5k when it actually *wins* $1.5k, exactly the "code runs, numbers
look good, conclusion is inverted" failure this review exists to catch.
```
```
