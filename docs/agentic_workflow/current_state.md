# Agentic Workflow — current state

A dated, newest-first record of what the agent-driven workflow *is* and what is verified working vs.
broken. Companion to `efficiency_backlog.md` (what to fix next). Scope + access rule: `README.md`.

---

## 2026-06-30 — Added a full-stack-flavored reviewer: `web-reviewer` + `/review-web` `[change]`

At Jay's request, split the adversarial reviewer in two rather than overload the ML-flavored one.
`phase-reviewer`/`/review-phase` stays the engine reviewer (DS/MLE leakage, splits, dollar-metric
verdict — P0–P8). New peer pair for the on-ramp web stack:

- `.claude/agents/web-reviewer.md` (new) — read-only, Opus, frames itself as a senior full-stack
  engineer. Hunt list is the web-stack equivalent of the ML one: seam firewall (same law, `onramp/`
  side), `05` architecture layering (pure compute vs. API vs. presentation, durable-chrome-vs-
  provisional-product), `06` UI trust (false precision, cost/margin reconciling on the *displayed*
  number, tenant isolation, firewall leakage to the browser), `07` API/backend correctness (schema
  validation gate, idempotent seam writes, typed/friendly error handling, authN/Z). Same report
  format, severity tiers, and COMPREHENSION HANDOFF sign-off as `phase-reviewer`; verdict still
  doesn't self-close the phase.
- `.claude/commands/review-web.md` (new) — `/review-web Wn`, scoped to
  `onramp/plate_cost/docs/website_vision.md` §8 acceptance criteria instead of
  `forecasting/docs/construction_roadmap.md`. Same diff-base + decision-log gathering, same
  comprehension-exit-gate section as `/review-phase`, copied verbatim where the gate logic doesn't
  differ by domain.

Why split rather than extend: the ML reviewer's hunt list (leakage, splits, dollar baselines) doesn't
transfer to web code, and folding both into one prompt would dilute either checklist. Naming makes the
split legible — `phase-reviewer` keeps the original name since `P0`-`P8` is where it has always
applied; `web-reviewer` and `/review-web` are the new, on-ramp-scoped names. `build-phase` was left
untouched — it already branches by phase id (`Pn` vs `Wn`) reading the matching spec, so it didn't need
a `build-web` counterpart.

Not done: `web-reviewer` has not yet been run against a real `Wn` phase (none built yet — `onramp/`
is still Phase-0-only per `CLAUDE.md` Current status). The efficiency-backlog item "record reviewer
output" (below) applies to this new reviewer too once a web phase exists to review.

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
the template. The audit's other gaps (no CI, stale memory) are untouched by this change and remain
open in `efficiency_backlog.md`.

---

## 2026-06-30 — Baseline established from an adversarial workflow audit `[audit]`

First full audit of the agentic workflow. Read every governance doc, both memory files, ran the
suite, checked the firewall and git history. Snapshot below is the verified state, not the narrated
one. (Project-state facts this audit turned up — test counts, the firewall check, the dollar
baseline figure, a red test found in `forecasting/` — are logged in `docs/progress_log.md`, not
here; this file stays scoped to the workflow machinery itself.)

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
- **Anti-Drift honored in practice.** The 2026-06-29 forward-notes entry *declined* to build engine
  ingestion ahead of phase. The on-ramp is genuinely thin; no premature web build.
- **Path-scoping works.** Engine rules don't load during on-ramp work and vice-versa.

### Verified BROKEN / GAPS (the backlog addresses each)
1. **"Runs in CI" is false.** Rules 01 and 02 assert the leakage canary + boundary test "run in CI."
   There is **no `.github/workflows/`, no `.pre-commit-config.yaml`, no git hook.** The most-repeated
   structural guarantee is aspirational prose, not enforcement.
2. **Stale memory.** `project_status.md` drifted from the file/git reality (wrong test count) with no
   mechanism to reconcile memory against actual state.
3. **No gate artifacts produced.** `docs/phase_decisions/` holds only `_template.md` — no P0/P1/P2
   decision logs. No notebooks exist at all. Gate 4 is recorded only as prose in `progress_log.md`;
   the mandated per-phase artifact was never produced, so the gate is effectively self-certified.
4. **Governance redundancy ~40%.** The firewall law is restated ~11×, dollars-not-accuracy ~6×,
   anti-drift ~6×, the four gates re-listed verbatim in `build-phase.md` despite its own "don't
   restate" instruction. ~9.6k governance tokens on a typical engine-build turn, ~40% avoidable.
5. **Aspirational load paid now.** Rules `05+07` (~2.4k tok) load on any `onramp/*.py` edit despite
   zero web-stack code; rule `04`'s registry/drift machinery targets empty `report/`+`decision/` dirs.

### Git reality vs. narrated process
3 commits, all 2026-06-30; multiple build phases squashed into single commits. The many discrete
gated steps + audit passes (#1–#11) the log narrates have no corresponding granular git trail. The
adversarial `phase-reviewer` has no committed output for any phase — cannot confirm it was run vs.
self-reviewed.
