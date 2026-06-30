---
description: Run an adversarial, read-only Opus review of a finished phase via the phase-reviewer subagent. Usage: /review-phase P1
argument-hint: <phase id, e.g. P1, or 'uncommitted' for current changes>
---

Launch the **`phase-reviewer`** subagent (read-only, Opus) to adversarially review the phase:
**`$ARGUMENTS`**. If that is empty, default to reviewing the uncommitted/most-recent changes and say so.

Why a subagent and not this thread: the review must run in a **fresh context that never saw the
builder's justifications** — that is the whole point of the original "review in a separate chat"
instruction, achieved natively. Do not pre-summarize the code or pre-judge it for the reviewer; hand it
the phase id and let it form its own view from the repo.

Before launching, gather a one-line **diff base** to pass along so the reviewer knows what changed:
run `git log --oneline -5` and `git status --short` and include the result in the prompt (e.g. "the
phase landed in commit X" or "changes are uncommitted in these paths"). If git has no useful base, tell
the reviewer to scope by the phase's target dirs and the newest `docs/progress_log.md` entry.

Prompt to give the subagent:
> Adversarially review phase **$ARGUMENTS** of this repo. Acceptance criteria = that phase's section in
> `forecasting/docs/construction_roadmap.md` (engine) or `onramp/plate_cost/docs/website_vision.md`
> section 8 (on-ramp), with the dollar-gated "done when" as the bar. Obey your full reviewer protocol:
> ground yourself, **run `pytest` and `ruff` and the phase's own metric yourself**, hunt the leakage /
> seam-firewall / dollar-verdict / split / reproducibility list, check against `data/_truth/` where the
> phase scores against the oracle, and end with the structured findings + honest sign-off. Here is the
> diff base: {paste the git output you just gathered}.

When the subagent returns, relay its report to Jay **verbatim in structure** (the findings block, the
verdict, the test/lint result, the top-3 fixes, the single biggest risk). Do not soften or re-grade it.

Then, **do not auto-fix.** Present the findings and ask Jay how he wants to proceed. Fixing a BLOCKER or
MAJOR that changes decision logic is itself a new step and re-enters the Comprehension Contract gate
(`00-process.md`); mechanical fixes already specified do not. When Jay greenlights fixes, hand them back
to a build pass (`/model sonnet`, then apply the reviewer's concrete fixes), re-run the suite, and
record the outcome in `docs/progress_log.md` — the same hardening pattern the log already uses.
