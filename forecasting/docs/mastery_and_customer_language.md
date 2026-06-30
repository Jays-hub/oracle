# Mastery Curriculum & Customer Language

Two things in one place: the concepts you actually need to *own* (with where to learn them), and the
plain-language translations that make you credible to operators. The Comprehension Contract (`docs/overview_and_method`)
requires both for every step — the concept *and* the chef-sentence — so this doc is the reference you
pull from to satisfy Gates 3 and 4.

## Concepts to master, sequenced by when the phases need them
Free/primary sources favored. You don't need all of this before starting — learn each rung as its phase
arrives.

**Forecasting foundations (Phases 1–2, + reconciliation for Phase 6)**
- Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* (free online). The canonical text:
  evaluation, time-series cross-validation, intermittent demand, and a full chapter on
  hierarchical/grouped forecasting and reconciliation.
- Intermittent demand: **Croston's method** and the **Syntetos–Boylan approximation** (short reads).

**The decision layer — newsvendor / operations (Phases 0, 4)**
- Any operations-management treatment of the **newsvendor model** and **critical fractile** (Cachon &
  Terwiesch, *Matching Supply with Demand*, is standard). The most important non-ML thing on the list;
  it's a short read and it's the spine of the whole product (`forecasting/docs/conceptual_spine`).

**Probabilistic & calibrated forecasting (Phase 4)**
- **Quantile regression** and the **pinball loss** (gradient-boosting docs cover the mechanics).
- **Conformal prediction:** Angelopoulos & Bates, *A Gentle Introduction to Conformal Prediction* —
  clearest modern intro. Apply with the **MAPIE** library.

**Censored / unconstrained demand (Phase 3)**
- Revenue-management literature on **demand unconstraining**; **Tobit / censored regression** for the
  statistical framing. Even a survey-level read puts you ahead of most practitioners on the popular-item
  problem.

**Hierarchical / Bayesian / pooling (Phase 6)**
- McElreath, *Statistical Rethinking* (book + lectures) — the best on-ramp to **partial pooling** and
  multilevel models, intuition first.
- Gelman et al., *Bayesian Data Analysis* — the deep reference when you want rigor.

**Practical modeling stack (throughout)**
- **LightGBM / XGBoost** with Poisson/Tweedie and quantile objectives — the Phase 2–4 workhorse.
- **statsmodels / sktime** — classical baselines and time-series CV scaffolding.
- **PyMC / NumPyro** — Bayesian hierarchical (Phase 6); mixed-effects (statsmodels) for the frequentist
  version.
- **NeuralForecast / GluonTS** — know they exist; only at Phase-6 scale and only with a dollar
  justification. Not where you start.

**A realistic learning order:** *Forecasting: Principles & Practice* → the newsvendor chapter →
quantile + conformal → unconstraining (as you hit the censoring wall) → *Statistical Rethinking* (for
pooling). This matches the phase order, so learning and building stay in lockstep — which is the whole
point of the contract.

## What "mastery" means here (so you can self-check)
You own a concept when you can: (1) say what failure it prevents, (2) name the practice in each of the
three domains (code / stats / kitchen), and (3) give the chef-sentence. If you can import the library
but can't do (1)–(3), you've borrowed the tool, not the understanding — and against an incumbent who
has more data, borrowed tools lose. The understanding is the edge.

---

## Customer-explanation cheat sheet
Each line does real technical work underneath; none of it requires an equation. Practice these aloud —
fluency here is most of your credibility in the room.

- **What it is:** "A morning prep sheet that tells you how much of each thing to make — tuned per dish to
  whether running out or throwing out costs you more."
- **Why it's not just 'busier/slower':** "The big tools stop at 'Thursday will do $8,400.' This goes the
  next step: braise eighteen short ribs, not twenty-two."
- **Why the number is already the decision:** "You don't interpret a forecast. It's the quantity. You
  prep it."
- **Where waste comes in:** "Waste isn't a separate feature — once I know how much you'll sell, the
  leftover falls out of the same math."
- **Why it gets the dish-by-dish call right:** "Cheap stuff you hate running out of, it preps high.
  Expensive stuff that hurts to dump, it preps lean. Your own instinct, made exact and consistent across
  every cook."
- **Why it's not extra work:** "It rides on the sales data you already have. One sitdown to confirm
  recipes on your big items, then it's just the sheet — nothing new to do during service."
- **Why it sees what the POS can't:** "It knows about the concert down the street and the first warm
  Saturday — the stuff that blows up a prep guess that your register has no idea about."
- **Why it's trustworthy:** "When it says it's ninety percent sure you won't run out, I can show you
  that's been right ninety percent of the time."

## The bridge line (ties the math to the business in one breath)
"Prep to the eightieth percentile of demand" is, at the same time, a statistic (a quantile), a line of
code (read `F⁻¹(0.8)` off a calibrated model), and a kitchen policy ("you hate running out of this cheap
dish"). That those are one object — not three — is why this is defensible and why the contract makes you
hold all three. Lose any one and you're either a generic forecaster or an operator with intuition you
can't scale.

## Honest caveat, kept in front of you
None of this curriculum validates the wedge. It makes you fluent and fast. Whether prep-level
forecasting is *unsaturated and wanted* is the empirical question only the discovery interviews answer
(see `docs/discovery_and_validation`). Build the skill now; let the operators tell you whether to build
the company.
