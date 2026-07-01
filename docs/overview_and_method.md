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

## HOW COMPREHENSION WORKS (the operating rule of this project)
This is the rule that makes this project *yours* rather than a thing an agent built while you
watched. It used to be a hard gate on every phase's review exit; as of 2026-07-01 it is a **parallel
practice track** — encoded in `CLAUDE.md` and `.claude/rules/00-process.md`. Here is the full reasoning
and what it actually requires.

**The principle:** every increment advances on two tracks at once — the **construction** (working code)
and the **comprehension** (the why) — but the two tracks run on **independent clocks.** Construction is
never blocked, and a phase's **review closes on the code** (findings relayed, greenlit fixes landed, log
entry written). Comprehension is not a checkpoint you clear once at phase-close; it is grown and
**re-checked over time** on a spaced-repetition track that never blocks a build, a review, or a merge.

### Why a parallel track, not a gate on the exit
Shipping is fast and per-phase; understanding is slow, cumulative, and only proves durable when it's
**re-tested weeks later.** A one-shot gate at phase-close certified understanding against a single
moment — and coupled two clocks that move at different speeds, so either shipping waited on a quiz or the
quiz got rubber-stamped to unblock shipping. Decoupling them fixes both: code ships on its merits, and a
concept learned in P1 resurfaces on its own schedule in P4 to confirm it actually stuck. The mechanism
is the **`/learn`** command driving the **`comprehension-tutor`** subagent, which reads the real code and
git history, quizzes whatever topics are **due**, grades your answers, and maintains **`docs/mastery.md`**
— a ledger of every topic at a mastery level (L0 Unseen → L4 Mastered) whose level sets when it next
resurfaces.

### What the tutor tests you on
The tutor grounds every question in the actual code/commit and probes across **three domains** — an
answer describable in only one domain is half-understood:

**WHY THIS, WHY NOW (`seq`).**
What problem did this phase solve, and why was it the right step rather than something later?
Sequencing is itself a skill: you build the baseline before the model because you need something to
beat; you unconstrain censored demand before you trust the distribution because otherwise the
distribution is fit to a lie. If you can't say why *now*, you don't understand the dependency
structure yet.

**CODEBASE IMPACT & CODING CRAFT (`code`).**
Which files/modules did this touch, what does it produce, and what does it unlock downstream — and the
software practice that keeps it correct (a reproducible backtest harness; no leakage across the
train/test boundary; the leakage canary and `.shift(1)`; deterministic seeds; typed config). "This added
`forecasting/src/decision/newsvendor.py`, which consumes the quantile model's output and produces the prep
quantity the report layer renders" — that sentence means you see how the piece fits.

**THE DATA-SCIENCE CONCEPT (`ds`).**
The statistical technique and *why it's the right tool here*: quantile loss; conformal coverage; partial
pooling; Tweedie likelihood for zero-inflated counts; the newsvendor critical ratio. Prefer answers that
connect the technique to the dollar objective and to the failure mode it guards against — a topic only
reaches **L4 (Mastered)** when you both explain it and connect it to the why-here-why-now and that
failure mode.

There is **no "say it to a chef" one-liner** in this system — it was retired with the gate. The three
domains still matter for the same reason they always did:

### How the three domains interlock (why this isn't three separate jobs)
The reason this venture is defensible is that the three knowledge bases are the *same* object viewed
three ways. "Prep to the 80th percentile of demand" is simultaneously a statistical statement
(a quantile), a software task (read `F⁻¹(r)` off a calibrated model), and a kitchen policy ("you hate
running out of this cheap dish"). Someone who only has the stats fits a generic forecaster; someone
who only has the domain has intuition they can't scale; you're building the bridge. The comprehension
track exists so you actually build the bridge instead of leaning on one pillar.

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
