# Phase build/review workflow (CLI)

How to run the build → adversarial-review loop for each phase from the Claude CLI. This replaces the
two paste-into-a-chat prompts (`sonnet_phase_builder_prompt.md`, `opus_phase_review_prompt.md`) with
two repo-native commands and a read-only reviewer subagent. The originals were written for a web chat
that couldn't see this repo; everything they asked you to *paste*, the CLI agent now *reads* and
*runs* itself.

## The three pieces

- **`/build-phase <P>`** — `.claude/commands/build-phase.md`. The builder. Run it in the main thread
  (ideally on Sonnet). It reads the phase spec from `forecasting/docs/construction_roadmap.md`, builds
  only that phase (no pre-code gate), writes real tests, and runs `pytest`/`ruff` before handoff. The
  Comprehension Contract is enforced later, at the review's exit, not here.
- **`/review-phase <P>`** — `.claude/commands/review-phase.md`. The reviewer's launcher. It gathers a
  git diff base and dispatches the `phase-reviewer` subagent, then relays the findings verbatim.
- **`phase-reviewer`** — `.claude/agents/phase-reviewer.md`. A **read-only, Opus** subagent (tools:
  Read/Grep/Glob/Bash — no Edit/Write). It reviews in a fresh context, *runs* the tests and the dollar
  metric itself, checks against `data/_truth/`, and reports in the structured finding format. It cannot
  change code — it reports; the builder fixes.

## The per-phase loop

1. `git switch -c phase/P1` (a branch per phase gives the reviewer a clean diff base and you a rollback).
2. `/model sonnet`, then `/build-phase P1`. The agent orients, then **builds** — no pre-code gate, no
   stop-and-wait for your sign-off. (This is the inversion — see below.)
3. The build finishes green, writes the decision log, and logs a `docs/progress_log.md` `[built]` entry.
   `git commit`.
4. `/review-phase P1`. The Opus subagent runs the suite, hunts the leakage/seam/dollar list, and hands
   back findings + an honest verdict.
5. You decide what to fix. Fixes go back to a Sonnet build pass and re-run — fixing is ordinary build
   work, not gated.
6. **The comprehension exit gate.** The review does **not** close until you can explain, in your own
   words, the finished, reviewed work: why-this-why-now, codebase impact, the three-domain practices,
   and the review delta + the failure mode it guards + the "say it to a chef" one-liner. Only when that
   lands does the agent record it in the decision log, write the closing log entry, and merge the branch.

One phase, one branch, one review that closes on *your* understanding. The old "keep each phase in its
own chat" becomes "keep each phase on its own branch" — same isolation, with a real diff and rollback
instead of copy-paste.

## Why a reviewer *subagent* (not a second chat, not this thread)

Adversarial review only works if the reviewer didn't write the code. A subagent runs in a **fresh
context that never saw the builder's rationalizations** — exactly what "review in a separate Opus chat"
was reaching for, achieved natively and without pasting. Making it **read-only** is the structural
guarantee that the adversary can only *find* problems, never quietly "fix" (and hide) them. Pinning it
to **Opus** keeps the Sonnet-builds / Opus-reviews division of labor the filenames implied.

## What changed from the chat prompts, and why

**Removed the paste inputs.** `{{ paste the project doc }}`, `{{ paste the phase spec }}`, `{{ paste
the diff }}`, `{{ paste the metrics }}`, `{{ paste requirements }}` — all gone. The agent reads
`construction_roadmap.md`, `CLAUDE.md`, the `.claude/rules/`, `git diff`, and `requirements*.txt`
directly. You pass one thing: the phase id.

**The reviewer now runs things.** The chat reviewer's whole "⬜ can't-verify-without-running" category
mostly collapses: the subagent executes `pytest`, `ruff`, the pipeline, and the `_truth/` comparison,
so findings come back marked *verified* (High confidence) instead of *inferred*. Its sign-off now
reports the actual test/lint result it observed.

**Specialized the generic checklist to this repo's law.** The originals carried generic DS/MLE advice
("don't use raw accuracy on imbalanced data"). That's replaced with this project's actual discipline,
cited by rule number: the dollar verdict `Σ(Co·overage + Cu·underage)` and pinball at `q*` (not
MAPE/RMSE); the **three required baselines** that must be beaten; rolling-origin CV ≥4 folds; the
decision-time leakage rules (`.shift(1)` before `.rolling()`, weather-forecast-not-actuals, the
leakage canary); `random_state=42`; and the **seam firewall** (`_truth/` read only by `evaluate/`,
`onramp/` never imports `forecasting/`, the boundary test). Anti-drift is now a review finding:
over-engineering ahead of the dollar-beating step gets flagged, not rewarded.

**Inverted the comprehension gate (the important one).** This used to be a *pre-code* gate: the agent
presented Gates 1–3 and hard-stopped until Jay cleared Gate 4 before a line was written. That stalled
delivery and let understanding be certified against code that didn't exist yet. `00-process.md` now puts
the gate at the **review's exit** instead: the agent builds freely, and the **review** is what can't
close until Jay can fully explain the finished work in his own words. The agent never self-certifies it.
Same contract — the project stays *yours* — but the explanation is now tested against real, reviewed
code instead of a plan.

## Notes

- **Git from the start.** The repo is now under git (initial commit = current P0 state). The reviewer
  prefers `git diff <base>...HEAD`; a branch per phase makes that clean. `data/_truth/` and
  `data/raw/**` stay gitignored, so the oracle is never committed.
- **Model switching.** `/build-phase`'s frontmatter doesn't force a model (a build is multi-turn and
  forcing one model mid-conversation is jarring); use `/model sonnet` for the session. The reviewer
  subagent pins Opus itself.
- **These commands are the canonical home of the prompts now.** Edit the behavior by editing the two
  `.claude/commands/*.md` files and the agent file — not the original uploads, which are superseded.
