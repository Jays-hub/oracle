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

Before launching, gather two things:

1. **Diff base:** run `git log --oneline -5` and `git status --short`. Include the result so the
   reviewer knows what changed (e.g. "phase landed in commit X" or "changes are uncommitted in these
   paths").
2. **Decision log:** read `docs/phase_decisions/$ARGUMENTS.md` if it exists. If it does, include its
   full contents in the reviewer prompt under a `## Builder's Decision Log` header. If it doesn't
   exist, note that to the reviewer — the absence of a decision log means it must infer intent from
   code alone and should flag unconfirmed assumptions more aggressively.

Prompt to give the subagent:
> Adversarially review phase **$ARGUMENTS** of this repo. Acceptance criteria = that phase's section in
> `forecasting/docs/construction_roadmap.md` (engine) or `onramp/plate_cost/docs/website_vision.md`
> section 8 (on-ramp), with the dollar-gated "done when" as the bar. Obey your full reviewer protocol:
> ground yourself, **run `pytest` and `ruff` and the phase's own metric yourself**, hunt the leakage /
> seam-firewall / dollar-verdict / split / reproducibility list, check against `data/_truth/` where the
> phase scores against the oracle, and end with the structured findings + honest sign-off. Here is the
> diff base: {git output}. Before reviewing code, read the builder's decision log below — use it to
> distinguish deliberate choices from mistakes, and critique the reasoning where the rationale is weak.
>
> ## Builder's Decision Log
> {contents of docs/phase_decisions/$ARGUMENTS.md, or "No decision log exists — infer intent from
> code and flag unconfirmed assumptions aggressively."}

When the subagent returns, relay its report to Jay **verbatim in structure** (the findings block, the
verdict, the test/lint result, the top-3 fixes, the single biggest risk). Do not soften or re-grade it.

Then, **do not auto-fix.** Present the findings and ask Jay how he wants to proceed. When Jay greenlights
fixes, hand them back to a build pass (`/model sonnet`, then apply the reviewer's concrete fixes), re-run
the suite, and record the outcome in `docs/progress_log.md` — the same hardening pattern the log already
uses. Fixing is ordinary build work; it is **not** gated by anything before the keystrokes.

## The comprehension exit gate — the review does not close until Jay can explain the work

This is the project's one hard gate (`.claude/rules/00-process.md`), and it lives **here, at the review's
exit** — not before the build. After the findings are relayed and any greenlit fixes have landed and
re-passed, the review is **still open**. Do **not** declare the phase done, do **not** merge, and do
**not** write the closing `docs/progress_log.md` entry until Jay demonstrates comprehension of the
**finished, reviewed** code.

Ask Jay to explain, **in his own words**, all four:

1. **What & why** — what this phase built and why it was the right step now (the dependency that placed it
   here).
2. **Codebase impact** — the files/modules it created or touched, what they produce, what they unlock.
3. **Practices invoked, in all three domains** — (a) software/coding craft, (b) data-science/statistical
   concept, (c) restaurant/consulting standard.
4. **The review delta + the failure mode** — what the review found and changed (or why it changed
   nothing), the **"say it to a chef"** one-liner, and the sentence **"The failure mode this guards
   against is ___."** (filled in, not blank).

**You never self-certify this — Jay clears it.** If his explanation is missing any of the four (including
the filled-in failure-mode sentence and the chef one-liner), the gate is **not** cleared: say which part
is missing and ask again. Keep the review open until it lands.

When it lands: record Jay's explanation **verbatim** in the comprehension-capture section of
`docs/phase_decisions/$ARGUMENTS.md`, then write the closing `docs/progress_log.md` entry (tagged
`[reviewed]`/`[done]`) and only then is the phase done and mergeable.
