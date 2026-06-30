# Construction Roadmap (start → finish)

This is the phase-by-phase **build plan**: concrete code, in order, each phase gated on understanding
(the Comprehension Contract, `docs/overview_and_method`) and on beating the prior baseline **in dollars**. The conceptual
"textbook" is distributed across `docs/overview_and_method` (method) plus the engine chapters in
`forecasting/docs/` (the spine, the data spec, the hard truths, the mastery curriculum); this is the
build sequence that operationalizes it.

Every phase carries the same block:
- **Objective** — what exists when it's done.
- **Why now** — the dependency that makes this the right next step (Gate 1).
- **Build** — the code deliverables (Gate 2).
- **Practices invoked** — (a) coding, (b) data science, (c) restaurant/consulting (Gate 3).
- **Checkpoint** — what you must be able to explain + the chef-sentence (Gate 4).
- **Done when** — the dollar-gated exit.

---

## Phase 0 — Repo, config, and the decision frame
**Objective.** Project skeleton + the newsvendor frame written down before any model: per-item `Cu`
and `Co`, the unit of decision (batch vs. made-to-order), the lead time, and the dollar objective.

**Why now.** "Good" is undefined until the economics are. Most forecasting projects die here
invisibly — they optimize accuracy on a target whose errors don't cost what was assumed.

**Build.** Repo tree (per `CLAUDE.md`); `config/items.yaml` with `Cu`/`Co`/`prep_type`/lead-time per
item; `forecasting/src/evaluate/objective.py` implementing realized cost `Σ(Co·overage + Cu·underage)`.

**Practices.** (a) typed YAML config, reproducible project layout; (b) defining a loss that matches
the decision, not a default metric; (c) food cost vs. contribution margin; the morning-commit nature
of prep; the batch/made-to-order fork.

**Checkpoint.** You can explain why the optimal prep quantity is a *quantile* and not the mean, and
say it to a chef ("cheap stuff you hate running out of, prep high; expensive stuff that hurts to dump,
prep lean").

**Done when.** The objective function runs on a dummy forecast and returns a dollar number.

---

## Phase 1 — Simulated data + honest baselines + backtest harness
**Objective.** The synthetic world (`forecasting/docs/simulated_data`) generated, plus the dumbest forecasters and a leakage-
free backtest harness, with stockout capture wired in.

**Why now.** You cannot evaluate anything without (1) data and (2) a baseline to beat and a *correct*
way to measure beating it. Build the measuring stick before the thing being measured.

**Build.** `forecasting/src/simulate/` (the generator → `data/raw/` + `data/_truth/`); baselines in
`forecasting/src/models/baselines.py` (seasonal-naive, same-weekday rolling mean, Croston for intermittent);
`forecasting/src/evaluate/backtest.py` (rolling-origin CV); ensure `eightysix_log` capture exists.

**Practices.** (a) deterministic seeds, separation of raw vs. truth, a reusable backtest harness; (b)
rolling-origin (not k-fold) CV, expanding vs. sliding windows, MASE and why MAPE is broken for counts,
Croston/Syntetos–Boylan for intermittent demand; (c) the gut baseline is "same as last Thursday";
sold-out ≠ low demand, so capture 86s from day one (physically unrecoverable later).

**Checkpoint.** You can explain *decision-time leakage* (why you backtest on the weather forecast, not
actuals) and why random k-fold leaks the future. Chef-sentence: "my first version is 'same as last
Thursday' — if I can't beat that, nothing fancy matters."

**Done when.** Baselines score in dollars on a rolling backtest; the harness refuses future
information.

---

## Phase 2 — Clean the polluted signal + per-item point model
**Objective.** A cleaned, menu-era-tagged dataset and one decent conditional-mean demand model per
item per daypart.

**Why now.** A model is only as honest as its target. Comps/staff/voids aren't organic demand; menu
eras are structural breaks. Clean first, then fit. Point model precedes distribution because the mean
is the scaffold the quantiles refine.

**Build.** `forecasting/src/data/clean.py` (strip/flag pollution, reconcile item-name drift, tag menu eras);
`forecasting/src/features/` (calendar, lags t-1/t-7, rolling stats); `forecasting/src/models/point.py` (LightGBM with
Poisson/Tweedie, item id as a feature, global model across items).

**Practices.** (a) idempotent cleaning, feature pipelines, train-across-items design; (b) count
likelihoods (Poisson/NegBin/Tweedie) and *why* OLS is wrong; feature engineering > architecture;
why GBMs beat per-series ARIMA in the many-short-related-series regime; (c) which POS rows are real
demand; menu changes invalidate old history.

**Checkpoint.** You can explain why demand is modeled as overdispersed counts and what cleaning you
did that `truth_params` says you should have. Chef-sentence: "I'm teaching it the patterns you already
feel — Fridays run hot, first of the month is busy — but precise per dish."

**Done when.** The point model beats Phase-1 baselines in dollars on the backtest, *after* cleaning
verified against `_truth/`.

> **Reconcile across the seam, not just within it (review issue #4).** `clean.py`'s item-name
> reconciliation must also reconcile the engine's `config/items.yaml` item `name` against the seam's
> `dish_name` — today the only join key shared by the engine config and `data/raw/`. Assert every
> configured item resolves to a seam dish under a normalized key (reuse the local trim+casefold in
> `forecasting/src/config.py`; do **not** import the on-ramp's `normalize_name` — the peer boundary
> holds) and fail loud on drift, the same discipline the on-ramp enforces on its covers join. The
> durable fix is a stable `item_id` carried across the seam so the join is never name-based; that is
> a seam-contract change, recorded in `data/CONTRACT.md` (Forward notes).

> **Candy warning:** resist deep sequence models (TFT/N-BEATS/DeepAR) here. For one restaurant and a
> few dozen items, a well-featured GBM wins and is faster to value. Park them for Phase 6 scale.

> **Open bug (found 2026-06-30, unfixed):** `forecasting/tests/test_features.py::`
> `test_lag_7_equals_same_weekday_last_week` is red — a leakage-adjacent lag test, the exact defect
> class Phase 2 exists to guard against. Decide whether the lag-7 selection in
> `forecasting/src/features/pipeline.py` is wrong or the test's day-index arithmetic is (its comment
> is internally inconsistent: "day 8 / index 7 / day 1"). Do not record further Phase 2 progress over
> this red test. Logged in `docs/progress_log.md` (2026-06-30 audit entry).

---

## Phase 3 — Censored-demand unconstraining
**Objective.** Recover true demand on sold-out item-days, so popularity stops being systematically
under-estimated.

**Why now.** This must come *before* you trust the distribution (Phase 4). If you fit quantiles to
censored sales, you fit them to a lie — and the lie is worst on your highest-`Cu`, highest-margin
dishes, the exact ones you can least afford to under-prep.

**Build.** `forecasting/src/models/unconstrain.py` (treat sold-out days as lower bounds: censored regression /
Tobit or a survival-style approach); fold corrected demand back into the modeling target.

**Practices.** (a) careful target construction without leakage, treating observations as bounds; (b)
right-censoring, Tobit/censored regression, demand unconstraining from revenue management; (c) the
86-board reality — the data evaporates nightly, which is why capture (Phase 1) had to come first.

**Checkpoint.** You can explain the self-reinforcing under-forecasting loop censoring creates.
Verify: does recovered demand match `truth_demand` on `truth_stockouts` days? Chef-sentence: "when you
sold out at 8, you didn't sell 22 — you'd have sold 30; the model now knows the difference."

**Done when.** On the go-forward window, recovered demand tracks `truth_demand` on capped days, and
popular-item dollar cost improves vs. Phase 2.

---

## Phase 4 — Distribution + the newsvendor turn (THE PRODUCT IN MINIATURE)
**Objective.** A calibrated predictive *distribution* per item, converted to a prep *quantity* via
each item's critical ratio. Plus waste and stockout as integrals of that distribution.

**Why now.** This is the step where a forecast becomes a prep sheet. Everything before was scaffolding
for it. It is the highest-value move in the whole project and is *barely ML* — an OR idea plus a
quantile read-off.

**Build.** `forecasting/src/models/quantile.py` (GBM quantile/pinball objective, multiple quantiles);
`forecasting/src/evaluate/calibration.py` (PIT histograms, empirical coverage) + conformal wrapper (MAPIE);
`forecasting/src/decision/newsvendor.py` (`r = Cu/(Cu+Co)` → `Q* = F⁻¹(r)`; `E[max(Q−D,0)]` waste,
`E[max(D−Q,0)]` stockout).

**Practices.** (a) model-agnostic calibration wrapper, clean separation of model (delivers quantile)
from policy (picks which quantile); (b) quantile regression, pinball loss, conformal prediction and
finite-sample coverage, the newsvendor→quantile bridge; (c) the chef's per-dish policy *is* the
critical ratio; calibration is a credibility instrument ("90% sure → right 90% of the time").

**Checkpoint.** You can derive expected waste/stockout from the distribution (a five-line argument)
and explain why a point forecast can't produce the right prep quantity. Chef-sentence: "instead of one
number, the whole range of how the night could go — then I dial each dish by what running out vs.
dumping costs you; the leftover is the waste forecast, free."

**Done when.** Quantiles are calibrated against `_truth/` AND realized newsvendor dollar cost beats
the Phase-2/3 point-model-as-mean baseline. **This is the milestone to be able to demo.**

---

## Phase 5 — Exogenous signal fusion (the differentiation layer)
**Objective.** Fuse in signal the POS structurally can't see — weather (forecast-at-decision-time),
events, day-before reservation depth — and show it improves the prep decision.

**Why now.** The base demand signal is POS-ownable; the *edge* lives outside the register. But you add
it only after the core engine works, so you can measure its marginal dollar contribution honestly.

**Build.** `forecasting/src/features/exogenous.py` (join `weather_forecast` — never actuals — events, and forward
reservation depth; engineer weather as a *delta*; vary the book's weight by day-of-week for the
walk-in ratio); graceful degradation when a feed is missing.

**Practices.** (a) time-aligned joins, missing-feed handling, decision-time discipline enforced in
code; (b) correlation vs. causation for a recommendation; feature relevance > feature volume; (c)
the amphitheater/first-warm-Saturday/forward-book reality — these are POS-blind and gettable.

**Checkpoint.** You can explain why exogenous data *neutralizes* the incumbent's data edge but doesn't
*create* yours (the moat is the combination, not "I use weather"). Chef-sentence: "it knows about the
concert down the street and the first warm Saturday — the stuff that wrecks a prep guess that your
register has no idea about."

**Done when.** Adding exogenous features reduces dollar cost over Phase 4, *and* you've confirmed the
weather feature uses only forecast-at-decision-time (no actuals leak).

---

## Phase 6 — Hierarchy & pooling (cold-start + the moat) + reconciliation
**Objective.** Borrow strength across items (a new special works), and — once you simulate multiple
restaurants — across restaurants (a new location works day one). Reconcile forecasts across the
ingredient ← dish ← category ← covers ladder.

**Why now.** Cold-start and thin per-item history are real limits the single-restaurant model can't
fix. This is also where the structural moat lives — but the moat is *data access*, not the algorithm.

**Build.** extend `forecasting/src/simulate/` to a small population of restaurants; `forecasting/src/models/hierarchical.py`
(partial pooling via hierarchical Bayes / mixed effects, or item/restaurant embeddings);
`forecasting/src/models/reconcile.py` (bottom-up / top-down / MinT).

**Practices.** (a) multi-entity data handling, shared-vs-specific parameterization; (b) partial
pooling/shrinkage, hierarchical Bayes or mixed-effects, embeddings, MinT reconciliation; (c) the
cross-platform pool is a real asymmetry a single POS can't replicate — but assembling it is the
distribution grind, not a modeling win.

**Checkpoint.** You can explain why partial pooling helps a data-poor item/restaurant and why the
*math* is copyable but the *pool* isn't. Chef-sentence: "a brand-new dish leans on similar dishes and
similar kitchens until yours builds its own track record."

**Done when.** A held-out "new" item/restaurant forecasts better with pooling than cold; reconciled
bottom-level forecasts are no worse (usually better) than unreconciled.

> **Candy warning:** this is the only place deep sequence models *might* earn their keep, and only
> sometimes. Justify them against a pooled GBM in dollars before adopting.

---

## Phase 7 — Recipe → ingredient → waste close (the dollar close, bounded)
**Objective.** Map dish demand to ingredient depletion via the big-item BOM, close the inventory
identity, and surface waste/over-order as a residual — matched against injected spoilage.

**Why now.** This converts the demand engine into the *dollar-legible waste story* you sell on, and it
closes the second waste channel (over-ordering perishables). Bounded scope: ~15–25 items only; do NOT
rebuild full recipe deconvolution.

**Build.** `forecasting/src/decision/ingredients.py` (ingredient demand = Σ dishes of demand × recipe qty, summing
*distributions* with co-movement, not as independent); `forecasting/src/decision/waste.py` (inventory identity
`Purchased + StartInv − EndInv = TheoreticalDepletion + Loss`; residual = spoilage signal); yield/shrink
coefficients from culinary tables as priors.

**Practices.** (a) bounded scope discipline, one-time vs. recurring setup separation; (b) summing
correlated distributions (independence under-buffers shared ingredients), the inventory identity,
yield coefficients as priors; (c) recipes drift (stated vs. inferred = over-portioning, a *feature*);
shelf life turns single-period into multi-period for carryover items; setup must stay one-time or it
dies on adoption.

**Checkpoint.** You can explain why ingredient demand variance is *more* than the sum of independent
dish variances, and why stated-vs-inferred recipe gaps measure over-portioning. Verify residual vs.
`truth_spoilage`. Chef-sentence: "compare what you'll use to what you bought — the gap that doesn't get
used up is your waste; I'm not measuring it separately, the math tells on itself."

**Done when.** The waste residual recovers injected `truth_spoilage` within tolerance, on data the
model never saw labeled.

---

## Phase 8 — The prep sheet + the MLOps reality (where projects actually die)
**Objective.** The single operator-facing output (the prep sheet) plus the unglamorous machinery:
retraining, drift/calibration monitoring, and the feedback loop that compounds the data.

**Why now.** A correct model that's a busy dashboard, or that silently decalibrates, doesn't get
adopted and doesn't improve. This is the least intellectually rich and most decisive phase.

**Build.** `forecasting/src/report/prep_sheet.py` (one sheet: "make this much of each thing," the dollar *why* one
tap away, nothing else); `forecasting/src/evaluate/monitor.py` (coverage + pinball over time, drift triggers);
the feedback loop that ingests each day's actuals — including unconstrained 86 events — back into the
model.

**Practices.** (a) production reproducibility, drift triggers over fixed schedules, instrumenting the
feedback capture; (b) calibration monitoring, retraining-on-drift, the compounding data loop; (c)
sell the decision not the dashboard; report money saved vs. baseline, not MAPE; one extra column is
adoption risk.

**Checkpoint.** You can explain why a confidently *miscalibrated* distribution is worse than an honest
point estimate, and what the feedback loop must capture for the moat to grow. Chef-sentence: "one sheet
in the morning — make this much; tap any line for why in dollars; and it checks itself against what
really happened, including the nights you ran out."

**Done when.** End-to-end, the system produces a daily prep sheet whose realized dollar cost beats the
gut baseline on a held-out period, and the monitor flags a deliberately injected drift.

---

## The throughline
Each phase beats the last in **dollars**, on data where you secretly know the truth, with the *why*
solid before the code. By Phase 4 you have the product in miniature; Phases 5–8 are where the edge
(exogenous + pooling + the dollar close + adoption) actually gets built. None of it validates the
business — that's discovery's job — but all of it makes you fast, fluent, and credible when discovery
says go.
