# Phase build/review workflow (CLI)

How to run the build → adversarial-review loop for each phase from the Claude CLI. This replaces the
two paste-into-a-chat prompts (`sonnet_phase_builder_prompt.md`, `opus_phase_review_prompt.md`) with
two repo-native commands and a read-only reviewer subagent. The originals were written for a web chat
that couldn't see this repo; everything they asked you to *paste*, the CLI agent now *reads* and
*runs* itself.

## The three pieces

- **`/build-phase <P>`** — `.claude/commands/build-phase.md`. The builder. Run it in the main thread
  (ideally on Sonnet). It reads the phase spec from `forecasting/docs/construction_roadmap.md`, builds
  only that phase (no pre-code gate), writes real tests, and runs `pytest`/`ruff` before handoff.
  Comprehension is grown separately on the `/learn` + `docs/mastery.md` track and gates nothing here.
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
6. **The review closes on the code.** Once findings are relayed, greenlit fixes have landed and
   re-passed, the agent records the review in the decision log, writes the closing `docs/progress_log.md`
   entry, and merges the branch. Nothing waits on your comprehension. Growing that understanding is a
   separate track — run `/learn` on your own cadence to have the `comprehension-tutor` quiz the new
   techniques and update `docs/mastery.md`.

One phase, one branch, one review that closes on the *code*. The old "keep each phase in its own chat"
becomes "keep each phase on its own branch" — same isolation, with a real diff and rollback instead of
copy-paste.

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

**Retired the comprehension gate entirely (2026-07-01).** It went through two forms — first a *pre-code*
gate (present Gates 1–3, hard-stop until Jay cleared Gate 4 before a line was written), then a
*review-exit* gate (the review couldn't close until Jay explained the finished work). Both coupled two
clocks that move at different speeds: shipping is per-phase and fast, understanding is cumulative and
needs re-testing over time. `00-process.md` now runs comprehension as a fully **parallel track** — the
`/learn` command + `comprehension-tutor` subagent maintaining `docs/mastery.md`, a spaced-repetition
ledger that resurfaces each topic on a schedule set by how well it's understood. Build and review close
on the code; understanding is grown continuously and gates nothing. The project stays *yours* because a
concept is re-checked weeks later, not certified once at a phase boundary.

## Notes

- **Git from the start.** The repo is now under git (initial commit = current P0 state). The reviewer
  prefers `git diff <base>...HEAD`; a branch per phase makes that clean. `data/_truth/` and
  `data/raw/**` stay gitignored, so the oracle is never committed.
- **Model switching.** `/build-phase`'s frontmatter doesn't force a model (a build is multi-turn and
  forcing one model mid-conversation is jarring); use `/model sonnet` for the session. The reviewer
  subagent pins Opus itself.
- **These commands are the canonical home of the prompts now.** Edit the behavior by editing the two
  `.claude/commands/*.md` files and the agent file — not the original uploads, which are superseded.
