# Overview & Method

## What this project is, in one paragraph
A **prep-demand forecasting engine** whose output is a daily prep sheet — "braise 18 short ribs,
not 22" — committed each morning before demand is known. Underneath is a probabilistic forecast of
per-item demand; on top is a **newsvendor decision layer** that converts each item's demand
*distribution* into a prep *quantity* using that dish's own economics. Waste/spoilage prediction is
a readout of the same distribution, not a separate model. It is sold to operators under the
waste-and-stockout framing (the pain they feel in dollars), built on the prep engine (where the
number is the actual decision). The strategic case for this wedge — and the lanes already closed —
lives in `docs/strategic_context.md`; this document assumes that and focuses on *how the
project is run and built*.

## Why this wedge (the short version)
Three tests from the strategy work decide whether a forecasting target is worth building, and
prep-demand passes the two that matter most:
- **The number is the decision.** "Prep 18" *is* the action; there's no human-judgment layer behind
  it the way covers→staffing has. (See `forecasting/docs/conceptual_spine`.)
- **Dollar-legible.** Error maps to two things operators already feel: the 86'd dish (lost margin +
  angry table) and the end-of-night dumpster (spoiled prep).
- The honest weak spot — **is it unsaturated?** — is the open empirical question. Incumbents forecast
  covers/$, not "braise 18 short ribs." Plausible, unverified, and the thing discovery confirms.

## This is a simulation — and what that does and doesn't prove
The whole build runs on synthetic data (`forecasting/docs/simulated_data`). That buys you two real things: technical
fluency, and a *verifiable* sandbox where you secretly know the ground truth and can check that each
model actually works. It buys you **zero** validation of the business. A model that performs
beautifully on simulated data tells you nothing about whether a real operator has this pain, would
pay, or would adopt. Hold that line. The simulation is the gym; discovery is the match.

---

## THE COMPREHENSION CONTRACT (the operating rule of this project)
This is the rule that makes this project *yours* rather than a thing an agent built while you
watched. It is encoded in `CLAUDE.md` as a hard gate; here is the full reasoning and what each gate
actually requires.

**The principle:** every increment advances on two tracks at once — the **construction** (working
code) and the **comprehension** (the why). The comprehension track is not optional documentation
written after the fact; it is a *precondition* for the code. You do not get to the next step until
the current step's why is solid in your own head.

### The four gates (cleared before any code for a new step)

**Gate 1 — WHY THIS, WHY NOW.**
What problem does this step solve, and why is it the right next step rather than something later?
Sequencing is itself a skill: you build the baseline before the model because you need something to
beat; you unconstrain censored demand before you trust the distribution because otherwise the
distribution is fit to a lie. If you can't say why *now*, you don't understand the dependency
structure yet.

**Gate 2 — CODEBASE IMPACT.**
Which files/modules does this touch, what does it produce, and what does it unlock downstream? This
forces you to hold the architecture in your head, not just the local task. "This adds
`forecasting/src/decision/newsvendor.py`, which consumes the quantile model's output and produces the prep
quantity the report layer renders" — that sentence means you see how the piece fits.

**Gate 3 — PRACTICES INVOKED, in all three domains.**
The discipline that makes you credible is that every step draws on three knowledge bases, and you
name them explicitly:
- **(a) Coding craft** — the software practice (e.g., a reproducible backtest harness; no data
  leakage across the train/test boundary; deterministic seeds; typed config).
- **(b) Data science / statistics** — the concept (e.g., quantile loss; conformal coverage;
  partial pooling; Tweedie likelihood for zero-inflated counts).
- **(c) Restaurant / consulting standard** — the domain truth (e.g., sold-out ≠ low demand; the
  prep decision is committed in the morning; food cost vs. contribution margin; one-time setup or
  it dies on adoption).
A step you can only describe in one of these three domains is a step you half-understand.

**Gate 4 — COMPREHENSION CHECK.**
Two outputs prove it landed: (1) you restate the step in your own words, including the failure mode
it guards against; (2) you produce the **"say it to a chef"** one-liner. If you can explain a
technique to a line cook in one sentence, you understand it; if you can't, you've imported a library,
not a concept. Capture both in the phase's notebook before the code closes.

### Why "say it to a chef" is a technical test, not a soft skill
Your edge is culinary domain knowledge, and your buyers are operators, not ML engineers. Every
modeling choice in this project has a plain-language justification *because the math is built out of
the operation*. The newsvendor critical ratio is literally the dish's P&L. Censoring is literally
"you sold out." If a step has no honest chef-sentence, suspect it's intellectual candy that doesn't
earn its place (see anti-drift, below).

### How the three domains interlock (why this isn't three separate jobs)
The reason this venture is defensible is that the three knowledge bases are the *same* object viewed
three ways. "Prep to the 80th percentile of demand" is simultaneously a statistical statement
(a quantile), a software task (read `F⁻¹(r)` off a calibrated model), and a kitchen policy ("you hate
running out of this cheap dish"). Someone who only has the stats fits a generic forecaster; someone
who only has the domain has intuition they can't scale; you're building the bridge. The contract
exists so you actually build the bridge instead of leaning on one pillar.

---

## Validate before deepening (the discipline that runs through every phase)
The hardest-won lesson from the strategy work was "validate problem value and market saturation
before deepening a solution." The same shape applies *inside the model*: never add a layer until the
simpler version beats the gut baseline **in dollars**. A deep model that doesn't reduce realized
over/under cost over a seasonal-naive baseline has no reason to exist. Every phase in `forecasting/docs/construction_roadmap` has a
dollar-gated "done when." This is what keeps the build honest and keeps you from optimizing an
invisible metric.

## Anti-drift standing order
Your documented pull is toward intellectually rich problems over the highest-value, least-contested
ones. This project is engineered to resist that:
- The **newsvendor reframe** (Phase 4) is the single highest-value move and it is *barely ML* — it's
  an operations-research idea plus a quantile read-off.
- The **moat is data access** (Phases 5–7), which is engineering and sales, not modeling.
- Deep sequence models, full correlated-distribution convolutions, and causal/uplift inference are
  real and mostly *later or candy*. They are flagged as such where they appear.
If a session reaches for sophistication before the per-dish critical-ratio quantile model exists and
beats baseline, that is the drift. Name it and redirect to the simplest thing that respects the
economics.
