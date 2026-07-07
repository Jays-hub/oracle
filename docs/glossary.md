# glossary.md — the plain-language term bank

A quick-reference bank of the vocabulary this codebase uses, each defined in **one or two plain
sentences tied to the restaurant reality** (Marco, the daily prep sheet, dollars of waste vs. dollars
of stockout). It exists because the *words* — quantile, censored, leakage, objective — are usually the
barrier, not the ideas underneath them.

- **Who maintains it.** The `concept-explainer` subagent (via **`/explain`**) appends new terms as it
  teaches. It is the *only* thing that writes this file, and it writes *nothing* else — it never grades
  or touches the mastery ledger. This is a **reference**, not a test and not a gate.
- **Companion files.** `/explain` teaches a concept top-down; `/learn` (the `comprehension-tutor` +
  `docs/mastery.md`) tests whether it stuck. Glossary = the words; mastery ledger = what Jay can
  actually retrieve.
- **Convention.** Alphabetical by term. Keep each entry terse; if a term has a symbol, give the word,
  the symbol, and the gloss together.

---

- **Backtest** — Replay history as if you were forecasting each past day live, then score those
  decisions against what actually happened. How a model earns trust *before* it touches a real prep
  sheet.
- **Baseline** — A deliberately simple forecasting rule a fancy model must beat before it earns its
  place. Three honest ones here: seasonal-naive, same-weekday rolling average, and Croston.
- **CDF — cumulative distribution function (`F`)** — For a demand amount `x`, `F(x)` is the probability
  demand lands at or below `x`. Reads as "how likely is demand no bigger than this?"
- **Censored demand** — When a dish sells out, the sales figure is capped at how much you prepped, so
  you never saw true demand. A `sold == capacity` day is a *stockout*, not real demand, and must be
  corrected before modeling.
- **Critical ratio (`q*`)** — The single fraction `Cu / (Co + Cu)` that says how far up the range of
  possible demand to prep. It is a target *probability*, not an amount of food. With `Cu=6.5, Co=1.5`,
  `q* = 0.8125`.
- **Croston's method** — A baseline built for items that sell in occasional bursts with many zero days
  (intermittent demand), where a plain average misleads.
- **Dollar objective (realized cost)** — The one number this project optimizes:
  `Σ(Co·overage + Cu·underage)` — total dollars lost to waste plus dollars lost to stockouts. "Done"
  means beating the prior baseline on *this*, never on accuracy.
- **GBM — gradient-boosted machine** — The prediction model used here: many small decision trees added
  up, each correcting the last one's mistakes. Strong on messy tabular data like daily dish sales.
- **Ground truth (`_truth`)** — The *real* demand the simulator secretly knows. Used only to score
  models after the fact — never fed in as an input, or the test would be rigged. See raw/_truth
  firewall.
- **Inverse CDF / quantile function (`F⁻¹`)** — The CDF read backwards: hand it a probability `q*` and
  it returns the demand amount at that point. The prep quantity is `F⁻¹(q*)`.
- **Lag feature** — A past value used as a clue for today (e.g. yesterday's sales). Built with
  `.shift(1)` so a row can only ever see earlier days, never its own day.
- **Leakage (data leakage)** — When a model accidentally trains on information it would not have in real
  life (the future, or the answer itself). It looks brilliant in testing and fails in production. Two
  distinct kinds are guarded here.
- **Leakage canary** — A cheap automatic check that fails loudly if the training and test data overlap
  in time (`max(feature_date) < min(target_date)`). A tripwire for the train/test-overlap kind of
  leakage.
- **MAPE / RMSE** — Standard *accuracy* error scores. This project deliberately does **not** optimize
  them: two forecasts with identical RMSE can lose very different dollars, and dollars are what we
  score.
- **Menu-era tagging** — Marking which stretch of history used which menu/recipe, so old,
  no-longer-relevant sales don't pollute the model. Done before the point model runs.
- **Newsvendor model** — The classic "how much perishable stock to prep for uncertain demand" problem.
  Its answer: prep up to the `q*`-quantile of demand. The core reframe the whole project is built on.
- **Objective (loss function)** — The formula a model tries to minimize while training. Choosing the
  *right* one (see Poisson) matters more than model complexity.
- **Overage cost (`Co`)** — The dollars lost per portion you prep but don't sell (wasted food). The
  "too much" side of the trade-off.
- **Overdispersion** — When counts vary more wildly than a plain Poisson assumes. The signal to upgrade
  the objective to Tweedie.
- **Point model** — A model that predicts a single best-guess demand number per dish per day (as
  opposed to a full range of possible outcomes). P2's deliverable.
- **Poisson objective** — A loss function built for counts (0, 1, 2, … dishes) that can never predict
  negative demand, unlike plain squared error. The right family for low-volume dish counts.
- **Prep quantity** — How many portions to make today: the demand amount at the `q*`-quantile, i.e.
  `F⁻¹(q*)`. The concrete thing the product outputs onto the prep sheet.
- **Quantile** — The demand amount below which a given fraction of days fall. The "0.81 quantile" is the
  level demand stays under 81% of the time. Prep targets a quantile, not the average.
- **raw/_truth firewall** — The rule that models read inputs only from `data/raw/` and never from
  `data/_truth/`. Keeps the exam honest: a model that peeks at truth produces a backtest that no longer
  predicts real-world performance.
- **Rolling-origin (walk-forward) cross-validation** — Testing by stepping forward through time — train
  on the past, predict the next slice, repeat — instead of a random split, because for forecasting the
  time order is the whole point.
- **Seasonal-naive** — A baseline that forecasts "same as the equivalent day last cycle" (e.g. last
  Monday). Simple, and surprisingly hard to beat.
- **`.shift(1)`** — The pandas operation that slides a column down one row, so "today's" feature is
  actually yesterday's value — the guard against a row cheating with its own same-day demand.
- **Tweedie objective** — A count-friendly loss (like Poisson) that also handles overdispersion and
  lots of zero days. The P3+ upgrade for when Poisson isn't flexible enough.
- **Underage cost (`Cu`)** — The dollars lost per portion of demand you *couldn't* fill (a stockout:
  lost sale, unhappy customer). The "too little" side of the trade-off.
