# Autonomous Builder — Build Plan (G1–G8 + Conductor) — 2026-07-07

The executable plan for the decision recorded this session: **a fully automated building system with
minimal user input**, gated on **rigorous, self-proving guardrails**. This is the *how and in what order*;
the *why and what* live in the two companion docs and are not repeated here:

- `guardrail_architecture_2026-07-07.md` — the principle (verify by mechanism, not prose), the three
  guarantee classes, the guardrail catalog G1–G8, the autonomy ladder A0–A4, the honest limits.
- `orchestration_analysis_2026-07-07.md` — the conductor design (C1) and why "one agent does it all" is
  the wrong target.

This is a plan, not a change to `.claude/**`. Each work packet below, **when built**, owes its own
`current_state.md` entry + `efficiency_backlog.md` strike per this folder's convention.

---

## 0. The invariant every packet must satisfy (non-negotiable)

Copied forward from `efficiency_backlog.md`'s robustness doctrine, because it is the acceptance test for
this entire program:

1. **Auto-invoked, not remembered** — fires on push / on tool-call / on the default code path.
2. **Self-proving** — ships with a *planted-violation test*: a deliberate breach that makes the guard
   fail. **A guard you have never watched fail is a guard you do not know works.**
3. **Recorded** — dated `current_state.md` entry + backlog strike.

And the program-level rule from the architecture doc: **prove the guard before you remove the human it
replaces.** No autonomy-stage advance (§4) until *every* guard it depends on has a green planted-violation
test. Autonomy is the residue of proven guardrails, never a switch flipped ahead of them.

---

## 1. Dependency graph

```
                 ┌──────────────────────────── MILESTONE 1: leakproof + honest ────────────────────────────┐
  G1 close _truth Read/Grep ─┐
  G6 facts-as-artifacts ─────┼─→ (metrics/test-count come from build artifacts, not keystrokes)
  G2 dollar gate ────────────┤        │
  G3 executable done-when ───┘        │
                                      ▼
                 ┌──────────────── MILESTONE 2: trusted fixes ────────────────┐
  G4 cold re-review of fix diff (unfreeze deliverable #3) ──┐
  G5 test-adequacy (planted-mutant) ───────────────────────┤
  G8 two-reviewer quorum (unfreeze deliverable #4) ─────────┘
                                      ▼
                 ┌──────────────── MILESTONE 3: the conductor ────────────────┐
  C1 /run-phase conductor  +  structural per-subagent model assignment
  (effort-scaled orientation = unfreeze deliverable #6, folded in)
                                      ▼
                 ┌──────────────── MILESTONE 4: unattended ───────────────────┐
  G7 stop-condition / escalate-never-override  (hardens C1 into an unattended loop)
```

**Why this order:** M1 makes the record *honest and leakproof* (you cannot trust an autonomous number you
can't recompute, or a build that can peek at the oracle). M2 makes *fixes and high-stakes changes*
independently checked (the current self-attestation hole). M3 chains it into one command with the human
at one gate. M4 hardens that command to run with the human *out* of the inner loop and only escalated to.
Each milestone is shippable and useful on its own; you are never mid-air.

---

## 2. The work packets

Format per packet: **Goal · Mechanism (files) · Planted-violation test · Retires · Depends on · Effort ·
Done-when.** Effort is rough: S ≈ hours, M ≈ half-day, L ≈ multi-day.

### G1 — Close the `_truth` firewall to `Read`/`Grep`/`Glob`
- **Goal:** the oracle is unreadable by *any* tool an autonomous agent can reach, not just `Bash`.
- **Mechanism:** register a hook on the `Read|Grep|Glob` matcher in `.claude/settings.json` (today only
  `Bash` is covered — audit BLOCKER-1). Reuse `deny_truth_access.py`'s logic against the
  `file_path`/`path`/`pattern` field; simplest correct policy: **deny always** and let Jay/evaluate code
  read `_truth` via the sanctioned `Bash` path only. `forecasting/src/evaluate/` reads `_truth` in
  process, not via the agent's Read tool, so nothing legitimate breaks.
- **Planted-violation test:** extend `tests/test_truth_access_hook.py` — a simulated `Read` of
  `data/_truth/x` returns *deny*; a `Read` of `data/raw/x` returns *allow*. Confirm both.
- **Retires:** the human as the only thing watching for an oracle peek (load-bearing the instant nobody
  watches).
- **Depends on:** nothing. **Effort:** S. **Done-when:** a planted `Read`/`Grep` of `_truth` is denied and
  the test proves it; recorded.

### G2 — Enforced dollar gate
- **Goal:** a new model layer **cannot merge** unless it beats all three baselines in realized cost —
  drift-into-sophistication becomes economically impossible, not merely discouraged.
- **Mechanism:** (a) a canonical `make evaluate` target that runs `forecasting/src/evaluate/` and **emits a
  metrics artifact** (e.g. `data/processed/metrics_<phase>.json`: realized cost of the candidate + each of
  seasonal-naive / 28-day-rolling / gut-proxy, pinball at `q*`, calibration). (b) a suite test
  `forecasting/tests/test_dollar_gate.py` that loads that artifact and asserts
  `candidate_cost <= min(baseline_costs)`; failure fails CI.
- **Planted-violation test:** feed the gate a metrics artifact where the candidate loses to a baseline;
  assert the gate test *fails*. (A guard watched to bite.)
- **Retires:** the human judgment "is this sophistication worth the dollars" (autonomy stage A3).
- **Depends on:** none structurally; pairs with G6 (the artifact is the single source of the number).
- **Effort:** M. **Done-when:** a losing candidate red-fails the gate in a planted run; a real phase's
  win is read from the artifact, not typed; recorded.

### G3 — Executable "done when"
- **Goal:** a phase cannot be marked done on an agent's say-so; it closes only when a test encoding *that
  phase's* acceptance criterion exists and passes. This is the upfront-input trade — the one job that
  stays human (author the predicate).
- **Mechanism:** each `Pn`/`Wn` section of `construction_roadmap.md` has a "Done when" clause. Translate
  each into a tagged test (`test_done_when_<phase>`), living beside the phase's suite. Add a meta-check
  (`make test` collector, or a `conftest` assertion) that the phase being closed **has** a non-trivial
  `done_when` test. The conductor (C1) refuses to close a phase whose `done_when` test is missing or
  skipped.
- **Planted-violation test:** a phase with a missing `done_when` test, or one asserting `True`, is
  rejected by the meta-check.
- **Retires:** the human judgment "is it actually done" (autonomy stage A3).
- **Depends on:** none. **Effort:** M (per-phase authoring is ongoing; the *mechanism* is one-time).
- **Done-when:** closing a phase without a real `done_when` test is blocked, proven by a planted missing
  test; recorded.

### G4 — Cold re-review of the fix diff (unfreeze deliverable #3)
- **Goal:** close audit MAJOR-3 — greenlit fixes stop being builder self-attestation. Under automation
  this is mandatory: an unattended fix is otherwise an ungoverned write to the exact code review flagged.
- **Mechanism:** implement `subagent_workflow_deliverables.md` #3. After a fix pass, for every
  BLOCKER/MAJOR finding, the conductor spawns a **fresh cold `phase-reviewer`** scoped to `git diff` of
  just the fix, which must clear the finding in a re-review artifact before it's marked resolved.
  MINOR/NIT stay self-verified (proportionate).
- **Planted-violation test:** a fix that does *not* address its finding (a symptom-only patch on a
  scratch fixture) is *not* cleared by the re-reviewer. Verify on the next real BLOCKER, and once on a
  synthetic.
- **Retires:** the human re-checking the fix (autonomy stage A2).
- **Depends on:** the durable review artifact (already built, #2). **Effort:** M.
- **Done-when:** no BLOCKER/MAJOR is marked resolved without an independent re-review artifact over its
  fix diff; recorded. *(Unfreezes deliverable #3 — the audit already greenlit this one specifically.)*

### G5 — Test-adequacy check (planted-mutant, not a heavy dep)
- **Goal:** stop self-authored tests from self-passing — the builder writes its own tests, so their
  adequacy must be checked by something the builder didn't write.
- **Mechanism:** reuse the repo's existing planted-violation muscle rather than adding a mutation-testing
  dependency (avoids the `requirements.lock` conda-path trap). At review time the cold reviewer injects a
  **known bug** into a *scratch copy* of the phase's core function (e.g. flip a `<` to `<=`, drop a
  `.shift(1)`) and confirms the builder's tests **fail** on the mutant. If the suite still passes, the
  tests are inadequate → a finding. (Optional later: a `mutmut`/`cosmic-ray` CI job if the manual pattern
  proves too coarse — deferred, not first.)
- **Planted-violation test:** a deliberately weak smoke-test suite over a known function does *not* catch
  a planted mutant → the check reports "inadequate," proven once.
- **Retires:** the human's "these look like smoke tests" instinct (autonomy stage A3).
- **Depends on:** the write-scope hook already lets scoped agents `cp` *out* to scratch (verified). 
- **Effort:** M. **Done-when:** an inadequate suite is flagged by a caught-mutant check; recorded.

### G6 — Facts-are-artifacts (generated, not narrated)
- **Goal:** kill the hallucinated/stale-number class (the audit's "353 tests" vs. real 358; the builder's
  "$15.6k" vs. reviewed $610.58). Any number in a record comes from a build step, never a keystroke.
- **Mechanism:** (a) a `make report` target that regenerates a canonical "current numbers" block (test
  count from `pytest --collect-only -q | wc -l`, dollar figures from the G2 metrics artifact) into a
  generated fragment. (b) a CI check that the committed fragment matches a fresh regeneration — drift
  fails the build. Docs quote the fragment; agents don't type the figures.
- **Planted-violation test:** hand-edit a number in the committed fragment to disagree with the
  regenerated one; the CI check fails.
- **Retires:** the human spotting a fabricated/stale figure (autonomy stage A4).
- **Depends on:** G2 (for the dollar numbers' source of truth). **Effort:** M.
- **Done-when:** a doctored number red-fails the match check; the progress-log figures trace to generated
  artifacts; recorded.

### G7 — Stop-condition: escalate, never override (the safety keystone)
- **Goal:** the unattended loop's failure mode is **"halt and surface to Jay,"** never "declare success"
  or "weaken a bar to pass." This is the property that makes M4 safe.
- **Mechanism:** in the conductor (C1): a bounded retry counter per gate (N attempts), then a **hard halt
  that emits the artifact + the failing check to Jay**. The agent may never edit a guard, lower a
  threshold, or `--no-verify` — and it structurally *cannot*, because `enforce_agent_write_scope.py`
  already denies scoped agents any write to `.claude/**`, the hooks, or test files outside their artifact.
  So "escalate, never override" is enforced at the tool boundary, not merely instructed.
- **Planted-violation test:** point the loop at a permanently-failing gate; confirm it halts and escalates
  after N, and that an attempt to edit the guard is denied by the write-scope hook (already tested — reuse).
- **Retires:** the human deciding "stop / retry / it's stuck" (autonomy stage A4 — the last touchpoint out).
- **Depends on:** C1 exists; write-scope hook (built). **Effort:** M.
- **Done-when:** a forced-failing loop escalates instead of thrashing or faking green, proven once;
  recorded.

### G8 — Two-reviewer quorum on high blast radius (unfreeze deliverable #4)
- **Goal:** remove the single-reviewer single-point-of-failure for the changes that can do the most
  damage — a lone reviewer's hallucinated green on a seam/contract change is unacceptable unattended.
- **Mechanism:** implement `subagent_workflow_deliverables.md` #4. The conductor classifies a diff as
  high-blast-radius if it touches `data/CONTRACT.md`, `schemas/**`, `forecasting/src/evaluate/` `_truth`
  paths, or crosses the on-ramp/engine seam. For those, spawn **two independent cold reviewers** (ideally
  different model *families* — see the decorrelation note in the architecture doc); the phase closes only
  on agreement, else it escalates (G7).
- **Planted-violation test:** a high-blast-radius diff triggers exactly two review artifacts; a forced
  reviewer disagreement escalates rather than auto-closing.
- **Retires:** the human giving big changes extra scrutiny (autonomy stage A4).
- **Depends on:** G4's re-review plumbing; G7's escalation. **Effort:** M.
- **Done-when:** the next `CONTRACT.md`/`schemas/` change gets two independent passes; a synthetic
  disagreement escalates; recorded. *(Unfreezes deliverable #4 — justified now by the automation goal;
  the audit's "keep frozen" was conditioned on there being no need yet, and the need now exists.)*

### C1 — The `/run-phase` conductor + structural model assignment
- **Goal:** chain builder → reviewer → one greenlight → fix → re-review → ship as a single command; retire
  the manual `/model` dance by assigning models per-subagent structurally.
- **Mechanism:** a new `/run-phase` command whose main thread orchestrates (never builds/reviews itself):
  spawns `builder(model: sonnet)`, `phase-reviewer(model: opus, cold)`, presents **one** greenlight
  decision, then on greenlight spawns the fix pass + G4 re-review + `/ship`. Folds in **deliverable #6**
  (effort-scaled orientation: pass `Explore` a breadth keyed to phase size). Per-subagent `model`
  overrides replace the `/model sonnet` reminder in `build-phase.md`.
- **Planted-violation test:** orchestration is command prose, so it is the *least* structurally provable
  piece — its safety is borrowed from the guards it invokes (G1–G8) plus the write-scope hook that stops
  it editing its own guards. Test: a dry run confirms it spawns *separate* cold subagents (not one merged
  context) and stops at the greenlight.
- **Retires:** the model-switch + invoke-build + invoke-review + invoke-fix + invoke-ship touchpoints
  (autonomy stage A1).
- **Depends on:** nothing to build A1; but must **not** advance to A2+ until G4/G8 (fixes) and G1–G3/G6
  (honest, leakproof, gated) are proven.
- **Effort:** L. **Done-when:** one command runs a full phase to a single greenlight; recorded.

---

## 3. Autonomy stage gates (which packets unlock which stage)

Straight from the architecture doc's ladder — this is the acceptance test for "minimal user input":

| Stage | Human still does | Gated on (all planted-tested) |
|---|---|---|
| **A1** conductor | greenlight only | C1 + structural model assignment |
| **A2** trusted fixes | greenlight only (fixes auto-re-reviewed) | **G4**, **G8** |
| **A3** auto-close on green | *author the `done_when` test*; greenlight only on BLOCKER/MAJOR | **G2**, **G3**, **G5** |
| **A4** unattended | *author the `done_when` test*; read escalations only | **G1**, **G6**, **G7** |

**Do not advance a stage with an un-proven dependency.** A4 with a leaky `_truth` (G1) or no stop-condition
(G7) is not "automated," it's unsupervised — the exact thing the guardrails exist to prevent.

---

## 4. Milestones (each independently shippable)

- **M1 — Leakproof + honest** (G1, G6, G2, G3). The record can't lie and the build can't peek or drift on
  dollars. *Start here — highest judgment-to-mechanism conversion, all load-bearing the moment a human
  stops watching.* Within M1, do **G1 first** (smallest, a confirmed live hole, and the clean template for
  the self-proving pattern every later packet reuses).
- **M2 — Trusted fixes** (G4, G5, G8). Fixes and high-stakes changes are independently checked; unfreezes
  deliverables #3 and #4.
- **M3 — The conductor** (C1 + deliverable #6). One command, one greenlight. Stage A1/A2.
- **M4 — Unattended** (G7 hardening). The human leaves the inner loop; escalation is the only inbound.
  Stage A3→A4.

---

## 5. Non-goals (explicit — these are the drift traps)

- **No single build-review-greenlight agent.** Ever. It collapses the adversarial independence that is the
  whole value (architecture doc §2).
- **No autonomy advance ahead of its proven guard.** The plan is guard-first by construction; a stage
  flipped early is unsupervised, not automated.
- **No heavy new dependencies for G5** without checking the `requirements.lock` conda-path trap first
  (known prior CI break). Prefer the repo's existing planted-mutant pattern.
- **No agent editing its own guardrails.** Enforced structurally by the write-scope hook; the plan relies
  on that, doesn't re-litigate it.

---

## 6. Definition of done for the whole program

The autonomous builder is "done" when: a phase can be initiated by authoring its `done_when` test and
running one command; the builder, reviewer, fix-pass, and re-reviewer are separate cold agents; every
number in the closing record is generated, not typed; a losing model or an oracle peek or an inadequate
test suite each **red-fails a planted-tested guard**; and on any failure the loop **halts and escalates
to Jay rather than declaring success** — with each of those guarantees having been *watched to fail on
purpose at least once.* At that point "minimal user input" is real, and it is safe because every human
check that was removed was replaced by a guard you have seen bite.
