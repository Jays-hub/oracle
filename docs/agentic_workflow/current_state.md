# Agentic Workflow — current state

A dated, newest-first record of what the agent-driven workflow *is* and what is verified working vs.
broken. Companion to `efficiency_backlog.md` (what to fix next). Scope + access rule: `README.md`.

---

## 2026-06-30 — Comprehension gate inverted: build is ungated, the review's *exit* is the gate `[change]`

At Jay's direction, removed the pre-code blocking gate and replaced it with a **review-exit
comprehension gate**. Old model: Gates 1–3 presented, agent hard-stops, Jay clears Gate 4 in his own
words *before any code*. New model: **building and implementation are never blocked**; instead, a
phase's **review cannot close** (no sign-off, no merge, no "done") until Jay can **fully explain, in his
own words, the changes made during both the build and the review** — why-this-why-now, codebase impact,
the three-domain practices, and the review delta + the filled-in failure-mode sentence + the chef
one-liner. Agent never self-certifies it.

Files changed in this pass:
- `.claude/rules/00-process.md` — rewritten: gate is on the review's exit, not the build's start.
- `.claude/commands/build-phase.md` — Step 0 no longer presents gates / stops; it orients and builds.
  Decision log leaves the comprehension section blank; handoff is `[built]`, not "done."
- `.claude/commands/review-phase.md` — new "comprehension exit gate" section; review stays open until
  Jay explains the finished work; dropped the stale "fixes re-enter the pre-code gate" framing.
- `.claude/agents/phase-reviewer.md` — sign-off adds a COMPREHENSION HANDOFF and states the verdict
  does not close the phase (cold-context subagent can't elicit/certify it).
- `CLAUDE.md` (standing order #1 + the DuckDB line), `forecasting/CLAUDE.md` (PRIME DIRECTIVE),
  `.claude/rules/05`, `README.md` — reframed from "gates every step / before code" to "review can't
  close until explained."
- `docs/overview_and_method.md` — Comprehension Contract section rewritten (exit, not entrance; added
  "Why the exit, not the entrance").
- `docs/phase_build_review_workflow.md` — per-phase loop + "what changed" section inverted.
- `docs/phase_decisions/_template.md` — "Gate 4 Capture" → "Comprehension Capture (filled when the
  review closes)" with the four-part explanation.

Not done: no built phase has yet exercised the new exit gate; `docs/phase_decisions/` still holds only
the template. The audit's other gaps (no CI, the red lag-7 test, stale memory) are untouched by this
change and remain open in `efficiency_backlog.md`.

---

## 2026-06-30 — Baseline established from an adversarial workflow audit `[audit]`

First full audit of the agentic workflow. Read every governance doc, both memory files, ran the
suite, checked the firewall and git history. Snapshot below is the verified state, not the narrated
one.

### What the workflow consists of (the machinery)
- **The gate.** Comprehension Contract (`.claude/rules/00-process.md`, `alwaysApply:true`) — Gates
  1–3 explicit + Jay clears Gate 4 in his own words before code for any new step.
- **Build/review loop.** `/build-phase` (`.claude/commands/build-phase.md`, Sonnet) builds one gated
  phase; `/review-phase` (`.claude/commands/review-phase.md`) launches the read-only adversarial
  `phase-reviewer` subagent (`.claude/agents/phase-reviewer.md`, Opus) in cold context.
- **Orientation.** `/session-start` (`.claude/commands/session-start.md`) returns a 10-line brief
  from log + memory + git.
- **Rules.** `00` always-on (gate); `01–04` path-scoped to `forecasting/src/**`; `05+07` scoped to
  `onramp/**/*.py`; `06` scoped to front-end assets.
- **Memory.** `~/.claude/.../memory/` — `MEMORY.md` index + `project_status.md` + `user_profile.md`.

### Verified WORKING (ran/grepped, not trusted)
- **The seam firewall holds in code.** No `_truth` reference under
  `forecasting/src/{data,features,models,decision,report}`; no real `forecasting` import in
  `onramp/` (only doc/comment mentions). `tests/test_module_boundaries.py` exists and passes. This
  is the platform's highest-priority law and it is enforced in fact.
- **Anti-Drift honored in practice.** The 2026-06-29 forward-notes entry *declined* to build engine
  ingestion ahead of phase. The on-ramp is genuinely thin; no premature web build.
- **Dollar-metric discipline is real.** Reproducible raw-only baseline floor ($144,789 clean /
  $148,882 dirty) via `python -m forecasting.src.evaluate.baseline_floor`.
- **Path-scoping works.** Engine rules don't load during on-ramp work and vice-versa.
- **Suite:** 164 tests, **163 pass / 1 FAIL** (see below) in the `restaurant-dev` conda env.

### Verified BROKEN / GAPS (the backlog addresses each)
1. **"Runs in CI" is false.** Rules 01 and 02 assert the leakage canary + boundary test "run in CI."
   There is **no `.github/workflows/`, no `.pre-commit-config.yaml`, no git hook.** The most-repeated
   structural guarantee is aspirational prose, not enforcement.
2. **A red test is in the working tree.** `forecasting/tests/test_features.py::`
   `test_lag_7_equals_same_weekday_last_week` fails — a leakage-adjacent lag test, the exact defect
   class the workflow exists to catch — yet P2 was recorded as progressing. (Test comment is itself
   internally inconsistent: "day 8 / index 7 / day 1" — fix the test or the pipeline lag selection.)
3. **Stale memory.** `project_status.md` claims "149 tests pass"; reality is 164 w/ 1 failing. No
   mechanism reconciles memory against file/git state.
4. **No gate artifacts produced.** `docs/phase_decisions/` holds only `_template.md` — no P0/P1/P2
   decision logs. No notebooks exist at all. Gate 4 is recorded only as prose in `progress_log.md`;
   the mandated per-phase artifact was never produced, so the gate is effectively self-certified.
5. **Governance redundancy ~40%.** The firewall law is restated ~11×, dollars-not-accuracy ~6×,
   anti-drift ~6×, the four gates re-listed verbatim in `build-phase.md` despite its own "don't
   restate" instruction. ~9.6k governance tokens on a typical engine-build turn, ~40% avoidable.
6. **Aspirational load paid now.** Rules `05+07` (~2.4k tok) load on any `onramp/*.py` edit despite
   zero web-stack code; rule `04`'s registry/drift machinery targets empty `report/`+`decision/` dirs.

### Git reality vs. narrated process
3 commits, all 2026-06-30; P0+P1 squashed into "Initial commit." The many discrete gated steps +
audit passes (#1–#11) the log narrates have no corresponding granular git trail. The adversarial
`phase-reviewer` has no committed output for any phase — cannot confirm it was run vs. self-reviewed.
