---
description: Run an adversarial, read-only Opus review of a finished on-ramp web phase via the web-reviewer subagent. Usage: /review-web W1
argument-hint: <web phase id, e.g. W0, W1, or 'uncommitted' for current changes>
---

Launch the **`web-reviewer`** subagent (Opus; read-only over the codebase, write-scoped only to
`docs/phase_decisions/**`) to adversarially review the on-ramp web phase:
**`$ARGUMENTS`**. If that is empty, default to reviewing the uncommitted/most-recent changes under
`onramp/` and say so.

Why a subagent and not this thread: the review must run **cold to the build chat** — it never saw the
builder's own narration, rationalizations, or in-thread back-and-forth, which is what "review in a
separate chat" was actually protecting against. It is **deliberately handed the builder's decision log**
(below) so it can tell an intentional tradeoff from a mistake — cold to the conversation, not blind to
the documented reasoning. Do not pre-summarize the code or pre-judge it for the reviewer beyond that; let
it form its own view from the repo.

Before launching, gather two things:

1. **Diff base:** run `git log --oneline -5` and `git status --short`. Include the result so the
   reviewer knows what changed (e.g. "phase landed in commit X" or "changes are uncommitted in these
   paths").
2. **Decision log:** read `docs/phase_decisions/$ARGUMENTS.md` if it exists. If it does, include its
   full contents in the reviewer prompt under a `## Builder's Decision Log` header. If it doesn't
   exist, note that to the reviewer — the absence of a decision log means it must infer intent from
   code alone and should flag unconfirmed assumptions more aggressively.

Prompt to give the subagent:
> Adversarially review on-ramp web phase **$ARGUMENTS** of this repo. Acceptance criteria = that
> phase's entry in `onramp/plate_cost/docs/website_vision.md` section 8, read alongside the on-ramp
> contract in `onramp/README.md`. Obey your full reviewer protocol: ground yourself, **run the on-ramp
> test suite and lint/type-check yourself**, hunt the seam-firewall / architecture-layering / UI-trust
> (false precision, non-reconciling numbers, tenant isolation) / API-boundary / error-handling list, and
> end with the structured findings + honest sign-off. Here is the diff base: {git output}. Before
> reviewing code, read the builder's decision log below — use it to distinguish deliberate choices from
> mistakes, and critique the reasoning where the rationale is weak.
> **Before you return control, write your full findings block + sign-off, verbatim, to
> `docs/phase_decisions/$ARGUMENTS_review.md`** (create it; this is the one path you may use your Write
> tool on — nothing else). This is the durable record Jay reads directly; it is not relayed through the
> builder's thread.
>
> ## Builder's Decision Log
> {contents of docs/phase_decisions/$ARGUMENTS.md, or "No decision log exists — infer intent from
> code and flag unconfirmed assumptions aggressively."}

When the subagent returns, confirm `docs/phase_decisions/$ARGUMENTS_review.md` exists and point Jay at
it directly — that file, not this chat, is the authoritative report. Then relay its contents to Jay
**verbatim in structure** (the findings block, the verdict, the test/lint result, the top-3 fixes, the
single biggest risk) so he doesn't have to leave the conversation to read it. Do not soften or re-grade
it; the file is there specifically so a mismatch between the relay and the artifact is itself visible
and checkable.

Then, **do not auto-fix.** Present the findings and ask Jay how he wants to proceed. When Jay greenlights
fixes, hand them back to a build pass (`/model sonnet`, then apply the reviewer's concrete fixes), re-run
the suite, and record the outcome in `docs/progress_log.md` — the same hardening pattern the log already
uses. Fixing is ordinary build work; it is **not** gated by anything before the keystrokes.

## No comprehension gate — the review closes on code merit

This review closes on the **code**: findings relayed, greenlit fixes landed and re-passed, the closing
`docs/progress_log.md` entry written. It is **not** gated by Jay's comprehension. Understanding is grown
on a **separate, parallel track** — `/learn` + `docs/mastery.md` — which runs on its own
spaced-repetition schedule and never blocks a phase close, a merge, or this sign-off. (The old
comprehension exit gate, with its per-phase `JAY-VERBATIM` capture, was retired 2026-07-01.)

If this phase introduced new techniques worth locking in, the natural follow-up is to run `/learn`
later — but that is Jay's practice cadence, not a precondition here. Once fixes are in and the log entry
is written, the phase is done and mergeable.
