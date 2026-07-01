---
description: Run an adversarial, read-only Opus review of a finished phase via the phase-reviewer subagent. Usage: /review-phase P1
argument-hint: <phase id, e.g. P1, or 'uncommitted' for current changes>
---

Launch the **`phase-reviewer`** subagent (Opus; read-only over the codebase, write-scoped only to
`docs/phase_decisions/**`) to adversarially review the phase:
**`$ARGUMENTS`**. If that is empty, default to reviewing the uncommitted/most-recent changes and say so.

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
> Adversarially review phase **$ARGUMENTS** of this repo. Acceptance criteria = that phase's section in
> `forecasting/docs/construction_roadmap.md` (engine) or `onramp/plate_cost/docs/website_vision.md`
> section 8 (on-ramp), with the dollar-gated "done when" as the bar. Obey your full reviewer protocol:
> ground yourself, **run `make test` and `make lint` and the phase's own metric yourself**, hunt the leakage /
> seam-firewall / dollar-verdict / split / reproducibility list, check against `data/_truth/` where the
> phase scores against the oracle, and end with the structured findings + honest sign-off. Here is the
> diff base: {git output}. Before reviewing code, read the builder's decision log below — use it to
> distinguish deliberate choices from mistakes, and critique the reasoning where the rationale is weak.
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

## The comprehension exit gate — the review does not close until Jay can explain the work

This is the project's one hard gate, defined once — the four-part explanation Jay must give, and the
"you never self-certify this" rule — in `.claude/rules/00-process.md` (`alwaysApply: true`, so it's
already loaded; **don't restate it here**). It lives **at the review's exit**, not before the build:
after the findings are relayed and any greenlit fixes have landed and re-passed, the review is **still
open** until Jay demonstrates comprehension of the **finished, reviewed** code in his own words. Do
**not** declare the phase done, merge, or write the closing `docs/progress_log.md` entry before that.
If his explanation is missing any of the rule's four parts, say which one and ask again.

What's specific to this command — not in rule 00 — is how that explanation gets captured and enforced
once it lands:

**The gate has teeth — you cannot skip this by writing prose instead of the artifact.** When Jay's
explanation lands:

1. Paste his message **unedited, in full**, into `docs/phase_decisions/$ARGUMENTS.md`'s Comprehension
   Capture section, inside the fenced `JAY-VERBATIM (paste, unedited)` block (see `_template.md`). Do
   not clean it up, reorder it, or fix his typos — the raw paste is the record.
2. Under it, quote the exact substring from that pasted block that satisfies each of the four parts.
   If you cannot find a real sentence for one, write `MISSING — ask again` for that line and go back
   to asking Jay — **never invent a plausible-sounding quote to fill the slot.** A fabricated citation
   here is worse than an empty one: it makes an ungated phase look gated.
3. **Refuse to write the closing `docs/progress_log.md` entry** (`[reviewed]`/`[done]`) until
   `docs/phase_decisions/$ARGUMENTS.md` exists on disk with that block filled and all four citations
   present and non-`MISSING`. This is a hard stop, not a reminder — if the file or the block is
   missing, say so and go fill it before doing anything else. The closing heading itself **must name
   the bare phase token** next to the tag, e.g. a heading reading "2026-07-01 — P3 reviewed:
   censored-demand unconstraining `[reviewed]`", so `tests/test_phase_gate_artifacts.py` can find and
   check it — this same invariant runs in CI, so a phase marked done in the log without a matching
   filled `Pn.md` fails the build, not just the honor system.

Only once the artifact is written and checked is the phase done and mergeable.
