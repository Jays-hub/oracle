# Phase build/review workflow (CLI)

How to run the build → adversarial-review loop for each phase from the Claude CLI. This replaces the
two paste-into-a-chat prompts (`sonnet_phase_builder_prompt.md`, `opus_phase_review_prompt.md`) with
two repo-native commands and a read-only reviewer subagent. The originals were written for a web chat
that couldn't see this repo; everything they asked you to *paste*, the CLI agent now *reads* and
*runs* itself.

## The three pieces

- **`/build-phase <P>`** — `.claude/commands/build-phase.md`. The builder. Run it in the main thread
  (ideally on Sonnet). It reads the phase spec from `forecasting/docs/construction_roadmap.md`, runs
  the Comprehension-Contract gate, builds only that phase, writes real tests, and runs `pytest`/`ruff`
  before handoff.
- **`/review-phase <P>`** — `.claude/commands/review-phase.md`. The reviewer's launcher. It gathers a
  git diff base and dispatches the `phase-reviewer` subagent, then relays the findings verbatim.
- **`phase-reviewer`** — `.claude/agents/phase-reviewer.md`. A **read-only, Opus** subagent (tools:
  Read/Grep/Glob/Bash — no Edit/Write). It reviews in a fresh context, *runs* the tests and the dollar
  metric itself, checks against `data/_truth/`, and reports in the structured finding format. It cannot
  change code — it reports; the builder fixes.

## The per-phase loop

1. `git switch -c phase/P1` (a branch per phase gives the reviewer a clean diff base and you a rollback).
2. `/model sonnet`, then `/build-phase P1`. The agent presents **Gates 1–3** and **stops**.
3. You clear **Gate 4** in your own words: restate the step + the failure mode it guards, and give the
   "say it to a chef" one-liner. Only then does code get written. (This is the one rule the original
   builder prompt got wrong — see below.)
4. The build finishes green and logs a `docs/progress_log.md` entry. `git commit`.
5. `/review-phase P1`. The Opus subagent runs the suite, hunts the leakage/seam/dollar list, and hands
   back findings + an honest verdict.
6. You decide what to fix. Mechanical fixes go straight back to a Sonnet build pass; a fix that changes
   decision logic re-enters the gate. Re-run, re-commit, then merge the branch.

One phase, one branch, one review. The old "keep each phase in its own chat" becomes "keep each phase
on its own branch" — same isolation, but with a real diff and rollback instead of copy-paste.

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

**Reconciled the Gate-4 conflict (the important one).** The original builder prompt had the agent
self-plan and proceed after asking about assumptions. This project's `00-process.md` says the opposite:
the agent presents Gates 1–3 and **never self-certifies Gate 4** — *Jay* clears it in his own words
first. `/build-phase` now hard-stops for that, so the build loop can't silently bypass the contract
that makes the project yours.

## Notes

- **Git from the start.** The repo is now under git (initial commit = current P0 state). The reviewer
  prefers `git diff <base>...HEAD`; a branch per phase makes that clean. `data/_truth/` and
  `data/raw/**` stay gitignored, so the oracle is never committed.
- **Model switching.** `/build-phase`'s frontmatter doesn't force a model (a build is multi-turn and
  forcing one model mid-conversation is jarring); use `/model sonnet` for the session. The reviewer
  subagent pins Opus itself.
- **These commands are the canonical home of the prompts now.** Edit the behavior by editing the two
  `.claude/commands/*.md` files and the agent file — not the original uploads, which are superseded.
