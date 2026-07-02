# P2 Adversarial Review — Clean the polluted signal + per-item point model

Reviewer: `phase-reviewer` (Opus). Date: 2026-07-02. Read-only over code; this file is the one
artifact written. Base reviewed: P2 target dirs under `forecasting/src/{data,features,models,evaluate}`
+ the P2 progress-log backfill entries (working tree had only agent-toolbox edits, no P2 code — matches
the launch note). Data regenerated locally via `python -m forecasting.src.simulate.generator` (seed 42).

## What P2 had to deliver (restated)

- **Clean the polluted signal:** strip observable comps/voids/staff meals, reconcile drifting
  `item_name` → canonical `item_id` (including config `items.yaml` names against the seam), tag menu
  eras, tag censored (86'd) day-items. (`forecasting/src/data/cleaner.py`)
- **Features:** calendar, lags t-1/t-7(/t-14), rolling stats, leakage canary. (`features/pipeline.py`)
- **Point model:** one global LightGBM (Poisson), `item_id` as a native categorical, across all items.
  (`models/point.py`)
- **Dollar-gated "done when":** *the point model beats the Phase-1 baselines in dollars on the
  backtest, **after cleaning verified against `_truth/`.***

The bar is dollars (`Σ Co·overage + Cu·underage`), not MAPE/RMSE. The three required baselines
(lag-7, 28-day rolling mean, gut-proxy-rounded-to-5) must exist and be beaten.

---

## Step 2 — Hunt list verdicts

- **Data leakage (fit-before-split / rolling without shift / lag<1 / weather actuals):** PASS
  (verified by running). Lags use `.shift(1)` before `.rolling()`; training self-transform uses only
  prior-day values; inference `transform()` defaults to `check_leakage=True`; backtest runs
  `leakage_canary(max feature_date < min target_date)` per fold. No weather actuals in P2. I traced the
  training feature build by hand and confirmed no future demand enters a training row's features.
- **Target/label leakage (censored days as clean):** CONCERN (by-design for P2). 130 censored
  day-items are fed as clean observations into the point-model target; the roadmap explicitly defers
  unconstraining to P3, so this is acceptable *for P2* but see MINOR-4 (the censored tag itself is
  mis-scoped).
- **Split integrity (rolling-origin, ≥4 folds, disjoint):** PASS. `RollingOriginBacktest` enforces
  `n_folds ≥ 4`, expanding window, test strictly after train, hard-fails on constructed leakage.
- **The dollar verdict:** FAIL as committed (see BLOCKER-1). All three baselines exist and are scored
  in dollars; the point model is **not** wired into any committed backtest/test, and one clause of the
  "done when" (cleaning verified vs `_truth/`) has no artifact at all. When I supplied the missing
  harness the model *does* beat the floor — but nothing in the repo shows it.
- **Reproducibility:** PASS. `seed=42`/`random_state=42` on LightGBM; I ran the point backtest twice
  → identical `128,467.93`. Deterministic.
- **Data integrity / dtypes:** CONCERN (MINOR-5, MINOR-6). No missingness report; no `qty==0`
  quarantine; dates are Python `date` objects (not `datetime64[ns]`), ids are object (not Categorical)
  vs rule 01's letter.
- **Seam firewall:** PASS (verified). No `_truth` read in any P2 source file (only a doc-comment
  mention in `cleaner.py`); `cleaner`/`loader` guard `data/raw/` via `_assert_raw_only`; the truth-access
  hook is live (it blocked a stray `ls`); `make test` (which runs `test_module_boundaries.py`) is green.
- **ML implementation correctness:** PASS on the objective (`Co·overage + Cu·underage` correct);
  Poisson objective + `item_id` categorical + global model match the spec; no silent broadcasting found
  in `dollar_loss`. But see MAJOR-3 (train/serve feature skew).
- **Anti-drift:** PASS. GBM-first, no deep sequence models — obeys the candy warning.

---

## Step 3 — Riskiest spots I looked at deliberately

1. **`features/pipeline.py::_add_lag_features` at inference** — the highest-risk file. Found the
   train/serve skew (MAJOR-3): verified empirically that over a 28-day test block `lag_1` is 96.4% NaN,
   `lag_7` 75% NaN, `rolling_mean_7` 75% NaN.
2. **The wiring between `point.py` and the dollar gate** — found BLOCKER-1: `GlobalLGBMModel` is
   imported by nothing (no test, no script, no backtest). The dollar verdict is undemonstrated.
3. **`cleaner.py` censored tagging** — found MINOR-4: the 86 tag is keyed on `(date, item)` only,
   ignoring `time_86d`/`service_period`, so a dinner 86 wrongly marks that day's lunch censored.

---

## Step 4 — Findings

```
[BLOCKER] P2's dollar-gated "done when" is not demonstrated by any committed code
Location:       forecasting/src/models/point.py (GlobalLGBMModel) + forecasting/src/evaluate/baseline_floor.py
What's wrong:   The phase's exit is "the point model beats Phase-1 baselines in dollars on the backtest,
                after cleaning verified against _truth/." Neither half is shown by committed code:
                (1) GlobalLGBMModel is imported by nothing — `grep -rn` finds zero references outside its
                    own file. baseline_floor.py runs ONLY the three baselines. There is no point_floor
                    script and no test_point.py. The headline P2 deliverable has zero test coverage and
                    is never scored against the baselines it must beat.
                (2) "cleaning verified against _truth/" has NO artifact: nothing under evaluate/ reads
                    truth to compare cleaned demand to truth_demand, and notebooks/ is empty (.gitkeep).
                I supplied the missing harness (run the GBM through the same RollingOriginBacktest on the
                cleaned series): it DOES beat the floor — 128,467.93 vs rolling28's 144,789.25
                (−16,321.32, ~11%), reproducible across two runs. So the model works; the *evidence* is
                absent from the repo.
Why it matters: A phase whose entire point is a dollar gate cannot be signed "done" when no committed,
                runnable artifact reproduces the number, and one full clause of the gate was never built.
                The dollar comparison is the product; leaving it un-committed means a future regression in
                point.py (or a cleaning change) is caught by nothing. This is the classic "the model is
                fine but the acceptance evidence doesn't exist" gap — cheap to close, invisible until asked.
Fix:            (a) Add a committed `point_floor`-style entry point (mirror baseline_floor.py) that runs
                GlobalLGBMModel + the three baselines through RollingOriginBacktest and prints/asserts the
                point model beats the best baseline in total dollars; (b) add test_point.py that fits/
                predicts on a small window and asserts the win (or at least non-regression); (c) build the
                cleaning-vs-_truth check inside evaluate/ (the only sanctioned truth reader): confirm
                stripping comps/staff moves observed demand toward truth_demand.
Confidence:     High (ran the grep; ran the harness; reproduced the numbers twice)
```

```
[MAJOR] Status docs describe a superseded point.py (baselines), not the actual GBM
Location:       CLAUDE.md "Current status" (P2 bullet); docs/progress_log.md line ~78
What's wrong:   Both say `forecasting/src/models/point.py` = "point-forecast baselines (lag-7, rolling-28,
                gut-proxy)." The actual file is `GlobalLGBMModel`, a LightGBM Poisson global model. The
                three baselines live in models/baselines.py. The docs describe a version that no longer
                exists.
Why it matters: Code is truth; the docs are stale. This mismatch is *why* BLOCKER-1 stayed invisible —
                a reader of the status believes point.py merely re-wraps baselines (nothing to test/wire),
                so no one notices the real GBM is untested and unscored. Stale status on a phase's headline
                deliverable actively hides the gap.
Fix:            Correct both docs to state point.py is the global LightGBM Poisson model, and note its
                dollar result once the point_floor harness (BLOCKER-1) exists.
Confidence:     High (read the file and both docs)
```

```
[MAJOR] Train/serve feature skew — lag features are ~96% NaN at inference
Location:       forecasting/src/features/pipeline.py::_add_lag_features; consumed by point.py predict
What's wrong:   The pipeline builds lags from stored training history only and does NOT recursively feed
                predicted demand. When forecasting a 28-day test block, each test day's look-back lands on
                other test days, which are NaN in the history series. Measured on a real 112-day-train /
                28-day-test split: lag_1 96.4% NaN, lag_7 75% NaN, lag_14 50% NaN, rolling_mean_7 75% NaN,
                rolling_std_7 78.6% NaN (rolling_mean_28 survives only via min_periods=1, increasingly
                stale). The model is TRAINED with lag_1 always populated (real prior-day demand — the
                single strongest count predictor) but SERVED almost entirely NaN lags. With
                lead_time_days=1 (a day-ahead prep decision) the backtest is scoring a 1-to-28-day-ahead
                block forecast, a horizon the product never operates at.
Why it matters: The flagship P2 lag features barely fire at decision time, so the "feature engineering >
                architecture" thesis isn't actually exercised — the win comes from calendar/era/stale
                rolling means. IMPORTANT NUANCE: the handicap is symmetric (the baselines also degrade to
                training-only info deep in the window), so the P2 *comparison stays fair* and the win is if
                anything conservative — this does NOT invalidate the dollar verdict. But the reported number
                understates a properly-served day-ahead model, and this skew will bite in production/P4+.
Fix:            Either (a) score the backtest at the real decision horizon (day-ahead: predict each test day
                with lags fed from the prior day's actual/held demand, i.e. recursive or per-day refit), or
                (b) at minimum document that P2 lags are inert in the block backtest and add a per-day-ahead
                evaluation. Do NOT "fix" by feeding future test actuals into lags — that would be leakage.
Confidence:     High (measured the NaN rates directly; script in scratchpad)
```

```
[MINOR] Censored tag ignores service_period and time_86d — over-tags the wrong daypart
Location:       forecasting/src/data/cleaner.py (censored_keys built from (business_date, item_id))
What's wrong:   The 86 log carries time_86d, and the data contains both lunch (e.g. 12:20) and dinner
                (20:30) 86 events. The cleaner keys censored on (date, item) only and applies it to BOTH
                the lunch and dinner rows of that day. A dinner 86 (service 17:00–22:00) therefore marks
                that day's lunch row (service 11:00–15:00, long finished) as censored.
Why it matters: censored is a P2 deliverable that P3 unconstraining consumes as a lower-bound flag. P3
                will inflate demand on daypart-rows that were never sold out, biasing exactly the
                high-Cu items P3 exists to protect. No P2 dollar impact (censored is unused in P2 scoring),
                so MINOR — but it is a latent P3 bug seeded now. test_86d_day_tagged_censored uses .any()
                and does not catch the over-tag.
Fix:            Derive the 86 event's service_period from time_86d (reuse the 16:00 lunch/dinner cutoff) and
                key censored on (date, item_id, service_period). Add a test asserting a dinner 86 leaves the
                lunch row censored=False.
Confidence:     High (read the code; confirmed a lunch 86 exists in the generated eightysix_log)
```

```
[MINOR] Cleaner skips two rule-01 ingestion requirements
Location:       forecasting/src/data/cleaner.py::clean_demand
What's wrong:   Rule 01 requires (a) "always print a missingness report (count + % per column) first" and
                (b) quarantine rows where qty==0 with no void/comp flag as a data-quality anomaly. The
                cleaner prints only exclusion counts and does neither.
Why it matters: The missingness report is the standing habit that catches an export glitch before it
                silently becomes demand=0; the qty==0 quarantine is how a dropped void/comp flag is caught
                (rule 01 is explicit that qty==0-with-no-flag is an anomaly, NOT censored demand).
Fix:            Add a per-column null count/% print at load, and a quarantine-and-log of qty==0 rows lacking
                a void/comp flag.
Confidence:     Medium (rule-cited; verified the code path prints only exclusion counts)
```

```
[MINOR] Rule-03 model-training diagnostics absent for the Poisson point model
Location:       forecasting/src/models/point.py::GlobalLGBMModel.fit
What's wrong:   Rule 03 asks for: per-item predicted-mean vs actual-mean check after Poisson training
                ("large per-item bias = missing era features or censored-demand contamination"), a
                feature-importance pass, and MLflow run logging. The model does none — it prints a single
                summary line.
Why it matters: The per-item mean check is the exact diagnostic that would surface the 130 censored rows
                contaminating the target (systematic negative bias on high-Cu items). Its absence means P2
                ships without the sanity check that motivates P3.
Fix:            Add a per-item predicted-vs-actual mean table after fit; log feature_importances_. MLflow
                may be parked as premature infra, but the mean/importance checks are cheap and in-scope.
Confidence:     Medium (rule-cited; read the fit path)
```

```
[NIT] dtype contract deviates from rule 01's letter
Location:       forecasting/src/data/{cleaner.py,loader.py}, features/pipeline.py
What's wrong:   Rule 01 specifies dates→datetime64[ns], item/category cols→pd.Categorical, quantities→
                int64. The code uses Python date objects and object-dtype ids (cast to category only inside
                the model). It is consistent across the codebase and tests assert date objects.
Why it matters: Low — it works and is internally consistent, but a Python-date column is slower and can
                surprise a future join; object ids defer categorical handling to each consumer.
Fix:            Optional: standardize on datetime64[ns] + Categorical, or record the date-object choice as
                a deliberate convention so it stops reading as a deviation.
Confidence:     Low (style/convention; not run-verified as harmful)
```

---

## Step 5 — Sign-off

**Rules:** No praise padding. Genuinely good: the seam firewall and leakage discipline are real and hold
under running — no truth leak, canaries fire, training uses only prior-day lags, and the model is
deterministic.

- **VERDICT — meets its dollar-gated acceptance criteria?** **No, as committed.** The point model, when
  I supply the missing harness, *does* beat the baseline in dollars (128,467.93 vs 144,789.25,
  reproducible) — so the substance is achievable. But the repo commits **no** artifact that demonstrates
  it (the GBM is imported by nothing, has no test, and is never scored against the baselines), and the
  "cleaning verified against `_truth/`" clause was never built. A phase whose exit is a dollar gate is
  not "done" until a committed, runnable artifact reproduces the number and the cleaning-vs-truth check
  exists.
- **TEST + LINT (observed):** `make test` → **209 passed, 4 warnings** (pandas str-dtype deprecation,
  cosmetic). `make lint` → **All checks passed!** Note: `point.py` and `cleaner`'s censored-granularity
  are green only because no test exercises them at those points.
- **TOP 3 FIXES (priority order):**
  1. Commit a `point_floor` entry point + `test_point.py` that run the GBM through the backtest and assert
     the dollar win over the best baseline; build the cleaning-vs-`_truth/` check in `evaluate/`. (BLOCKER-1)
  2. Correct CLAUDE.md + progress_log to describe point.py as the LightGBM Poisson model. (MAJOR-2)
  3. Resolve the train/serve lag skew: evaluate at the real day-ahead horizon (no future actuals) so the
     lag features actually fire. (MAJOR-3)
- **WHAT I COULD NOT VERIFY:**
  - Whether the cleaning genuinely moves observed demand toward `truth_demand` — the sanctioned check
    lives in `evaluate/` and does not exist; I did not open `_truth/` directly (firewall + hook), so the
    second clause of the "done when" is unverified *by design of the gap*, not by my choice.
  - Long-horizon/production behavior of the point model once lags are served live (P4+ territory).
- **SINGLE BIGGEST RISK:** The headline P2 deliverable — the point model beating the baselines in
  dollars — is real but exists nowhere in committed, tested code, so a future change to `point.py` or the
  cleaner can silently break the one number this phase is graded on, and nothing would fail.
