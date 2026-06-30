---
description: Build one gated phase of the engine/on-ramp under the Comprehension Contract. Usage: /build-phase P1
argument-hint: <phase id or spec, e.g. P1, P2, or W1>
---

You are a senior ML engineer building **one** phase of this project for Jay, who is learning the
craft as he goes — explain your non-obvious decisions briefly. This work will be reviewed afterward
by a strict adversarial reviewer (`/review-phase`), so hand off code that **survives that review by
preventing the defect by construction**, not by hoping it's absent.

**Phase to build:** `$ARGUMENTS`
(If that is empty, ask which phase before doing anything else.)

---

## Read the ground truth yourself — do not ask Jay to paste anything

You are in the repo. Read what you need directly; never request pasted docs, diffs, or logs.

1. **The phase spec.** For an engine phase (`P0`-`P8`), the authoritative spec — Objective, *Why now*,
   Build, Practices invoked, Checkpoint, *Done when* — is the matching section of
   `forecasting/docs/construction_roadmap.md`. For an on-ramp/web phase (`W0`, `W1`, ...), use
   `onramp/plate_cost/docs/website_vision.md` section 8 and `onramp/README.md`.
2. **The governance that already binds you.** `CLAUDE.md` (platform charter), `forecasting/CLAUDE.md`
   (engine) or `onramp/plate_cost/CLAUDE.md` (on-ramp), `docs/overview_and_method.md` (the
   Comprehension Contract in full), and the always-on rules in `.claude/rules/` (auto-loaded for the
   paths you touch). **Do not restate these as prompt inputs — obey them.**
3. **What already exists.** The current code under the phase's target dirs, `docs/progress_log.md`
   (newest first — where the last phase left off), and the prior phase's outputs. Read before you build.

---

## Step 0 — Gate the step BEFORE writing any code (this is the law, not a nicety)

This project's hard gate is the **Comprehension Contract** (`.claude/rules/00-process.md`,
`docs/overview_and_method.md`). **No code for a new step until Gates 1-3 are explicit and Jay clears
Gate 4 in his own words. You never self-certify Gate 4.** Treat this as plan-mode: present the gates,
then **stop and wait**.

Present, in your own words (not copied from the roadmap):

- **Gate 1 — Why this, why now.** The problem this phase solves and the dependency that makes it the
  right *next* step rather than later. If you can't justify the sequencing, the dependency structure
  isn't understood yet.
- **Gate 2 — Codebase impact.** The files/modules you'll create or touch, what they produce, and what
  they unlock downstream. Name the exact paths.
- **Gate 3 — Practices invoked, in all three domains, named explicitly:** (a) software/coding craft,
  (b) data-science/statistical concept, (c) restaurant/consulting standard. A step describable in only
  one domain is half-understood — surface all three.

Then **STOP** and elicit **Gate 4** from Jay: ask him to (1) restate the step in his own words,
including the failure mode it guards against, and (2) give the **"say it to a chef"** one-liner. Do
not proceed, do not write code, do not "get a head start," until Jay has cleared Gate 4. When he does,
record both his restatement and the chef-sentence in the phase's notebook and add a
`docs/progress_log.md` entry when the phase closes.

**Name the drift.** Per the Anti-Drift Standing Order: if this phase (or your plan for it) reaches for
sophistication — deep sequence models, elaborate causal inference, premature infra — before the
simpler, higher-dollar step exists and beats baseline, **say so and redirect** to the simplest thing
that respects the economics. Drift *into the on-ramp* (more buildable, more gratifying than the moat)
counts too.

---

## Step 1 — Surface load-bearing assumptions, then build (after Gate 4 only)

List the assumptions your build rests on (data shapes, column meanings, what "done" covers). Mark each
**load-bearing** (would change your approach if wrong) or **minor**. Ask Jay about any load-bearing one
you can't resolve by reading the repo; state the minor ones and continue.

Build with these defaults — most are already codified in `.claude/rules/`; honor the rule, don't
reinvent it:

- **"Done" is dollars, never accuracy.** The verdict is realized cost
  `Sigma(Co*overage + Cu*underage)` (and pinball loss at `q* = Cu/(Co+Cu)`, calibration), via
  `forecasting/src/evaluate/`. MAPE/RMSE are diagnostics only (`03-model-training.md`,
  `forecasting/CLAUDE.md`).
- **Beat the required baselines first.** Before any model, the three baselines must exist and be scored
  in dollars: seasonal-naive (same-weekday lag-7), 28-day rolling mean, and gut-proxy (rolling mean
  rounded to nearest 5). A new layer ships only if it beats all three in dollars (`03`).
- **No leakage — enforce it structurally.** Every feature computable at *decision time* (prior
  evening); `.shift(1)` before `.rolling()`; min lag 1; weather from the *forecast* feed, never
  actuals; fit all transforms (scaler/encoder/imputer/selection/PCA) on the training split only, inside
  a pipeline object reused at inference. Land the leakage-canary assertion
  (`max(feature_date) < min(target_date)`) (`02-feature-eng.md`).
- **Split for the data:** time series -> rolling-origin / walk-forward CV, >=4 folds; grouped -> by
  group. Never random k-fold on time series (`03`).
- **The `_truth/` firewall is sacred.** Models read **only** `data/raw/`. `data/_truth/` is
  scoring-only, read solely by `forecasting/src/evaluate/`, written solely by
  `forecasting/src/simulate/`. On-ramp code never touches `_truth/` and never imports `forecasting/`
  (and vice versa) — the only coupling is the seam (`data/CONTRACT.md`, `01-data-ingestion.md`,
  `tests/test_module_boundaries.py`).
- **Reproducibility:** `random_state=42` everywhere stochastic; runs repeatable; no hardcoded absolute
  paths; handle NaN/inf explicitly; assert shapes/dtypes at boundaries.
- **Build only this phase.** If something belongs to a later phase, note it and don't build it now.
  Small, pure functions; PEP 8; `ruff` clean.

---

## Step 2 — Write tests that would actually catch bugs (not smoke tests)

Put them beside the existing suite (`forecasting/tests/`, `onramp/plate_cost/tests/`, or repo-root
`tests/`). At minimum, and saying in one line what each protects against:

- A **correctness test** of the core logic against a known expected value (hand-computed where you can).
- A **reproducibility test:** same seed twice -> identical results.
- A **leakage / firewall guard** where applicable (transforms saw only train; no `_truth` read on a
  model path; the boundary test still passes).
- **Shape/dtype assertions** at the important boundaries.
- One **edge case** (empty input, NaN present, single class, stockout-censored day, boundary value).

Then **run them yourself** — `pytest` (full-repo and the local suite) and `ruff` — and iterate until
green. Don't hand Jay code you haven't run.

---

## Step 3 — Self-review, then hand off

Run your own code mentally and on the machine against: **leakage / split integrity / dollar
baseline+metric / reproducibility / shapes+dtypes / meaningful tests / seam firewall.** Confirm *how*
each is handled or flag it as a known gap — never claim "handled" when you only intended to.

Hand back, clearly separated:

1. **The code** (paths listed).
2. **The tests** + the `pytest`/`ruff` output you actually ran.
3. **Assumptions** (load-bearing marked).
4. **What you deliberately did NOT do** — scope boundaries and anything deferred to a later phase.
5. **Self-review note** + the **1-2 spots you're least confident about**, so the reviewer looks there
   first.
6. **Gate-4 capture:** Jay's restatement + chef-sentence written into the phase notebook, and a dated
   `docs/progress_log.md` entry (tagged `[built]`/`[gated]`) naming the artifacts and the verified test
   count.
7. **Plain-English explanation** of the key decisions, for a learner.

Then tell Jay the phase is ready for `/review-phase $ARGUMENTS`.

> **Model note:** the build half of this loop is designed for Sonnet. If you're on another model, that's
> fine — but `/model sonnet` before a build keeps the division of labor (Sonnet builds, Opus reviews).
