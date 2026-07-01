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

## Step 0 — Set up and orient (building is NOT gated — go ahead and build)

**The comprehension gate is on the review's *exit*, not here.** Per `.claude/rules/00-process.md`,
building is never blocked by a pre-code gate. Do **not** present gates and stop. Set up, then build.
Comprehension is tested later, by `/review-phase`, which will not close until Jay can fully explain the
finished work (see Step 3 and the review command).

**Branch pre-check (first).** Run `git branch --show-current`. The working branch for phase `Pn`
must be `phase/Pn` (e.g. `phase/P2` for P2). If it isn't, emit **exactly**:

> You're on `<current-branch>`. Switch first:
> ```
> git switch -c phase/Pn
> ```
> Reply when done and I'll continue.

Then **stop and wait** — this is the one stop in Step 0. Do not build on the wrong branch.

**Exploration pass (orient before building).** Once the branch is confirmed, spawn a subagent
(`subagent_type: Explore`) with `search breadth: thorough` and these instructions:

> Scan the phase `$ARGUMENTS` spec in `forecasting/docs/construction_roadmap.md` (or the on-ramp
> equivalent for W-phases). List: (1) every file the build will create or touch with its current
> state (exists / empty / populated), (2) the immediate upstream and downstream dependencies by
> file path, (3) any naming, dtype, or schema facts the spec assumes that a reader could miss.
> Report findings; do not write code.

Fold those findings into your build plan. The agent does not start from cold.

**Orient yourself, in your own words (not copied from the roadmap), then proceed to build:**

- **Why this, why now.** The problem this phase solves and the dependency that makes it the right
  *next* step rather than later.
- **Codebase impact.** The files/modules you'll create or touch, what they produce, and what they
  unlock downstream. Name the exact paths.
- **Practices invoked, in all three domains, named explicitly:** (a) software/coding craft, (b)
  data-science/statistical concept, (c) restaurant/consulting standard. A step describable in only one
  domain is half-understood — surface all three.

Carry these forward into the decision log (Step 3); they are the material Jay's review-exit explanation
will be checked against. They do **not** require Jay's sign-off before you write code.

**Name the drift.** Per the Anti-Drift Standing Order (`CLAUDE.md` — canonical, not restated here):
if this phase or your plan for it reaches for sophistication before the simpler, higher-dollar step
exists and beats baseline, say so and redirect to the simplest thing that respects the economics.

---

## Step 1 — Surface load-bearing assumptions, then build

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

Then **run them yourself** — `make test` (full-repo and the local suite) and `make lint` — and iterate
until green. Both hard-code the `restaurant-dev` conda env (`Makefile`), so they never silently
degrade to a `base` env missing pytest/ruff. Don't hand Jay code you haven't run.

---

## Step 3 — Write the decision log, self-review, then hand off

Run your own code mentally and on the machine against: **leakage / split integrity / dollar
baseline+metric / reproducibility / shapes+dtypes / meaningful tests / seam firewall.** Confirm *how*
each is handled or flag it as a known gap — never claim "handled" when you only intended to.

**Write `docs/phase_decisions/$ARGUMENTS.md` before handing off.** Copy `_template.md` and fill it
in completely — your why-this-why-now / codebase-impact / three-domain practices from Step 0, every
load-bearing assumption, every non-obvious design decision (chose X over Y because Z), constraints
discovered mid-build, deferred items, and the two spots you're least confident about. This file is the
reviewer's briefing **and** the material Jay's review-exit explanation gets checked against; an
incomplete log means the reviewer audits code without context and will find false positives where your
decisions were deliberate. Leave the comprehension-capture section for the review to fill — Jay's
explanation is recorded there when the review closes, not now.

Hand back, clearly separated:

1. **The code** (paths listed).
2. **The tests** + the `make test`/`make lint` output you actually ran.
3. **Assumptions** (load-bearing marked).
4. **What you deliberately did NOT do** — scope boundaries and anything deferred to a later phase.
5. **Self-review note** + the **1-2 spots you're least confident about**, so the reviewer looks there
   first.
6. **Decision log + progress entry:** `docs/phase_decisions/$ARGUMENTS.md` filled in (comprehension
   section left for the review), and a dated `docs/progress_log.md` entry (tagged `[built]`) naming the
   artifacts, the verified test count, and a pointer to the decision log. The phase is **not** marked
   done here — that happens only when the review's comprehension gate clears.
7. **Plain-English explanation** of the key decisions, for a learner.

Then tell Jay:

> **This phase is ready for `/review-phase $ARGUMENTS`. Do not self-review.**

> **Model note:** the build half of this loop is designed for Sonnet. If you're on another model, that's
> fine — but `/model sonnet` before a build keeps the division of labor (Sonnet builds, Opus reviews).
