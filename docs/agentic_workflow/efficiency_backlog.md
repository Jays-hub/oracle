# Agentic Workflow — efficiency backlog

Prioritized, actionable fixes to the workflow. All 13 items from the second-audit's list are now
closed — 1-7 and 9-13 done, #8 retired by decision (below) — and archived in `current_state.md`'s
2026-07-01 entries (what was built, what was verified, and any known imperfections). Items 14-20
respond to the third audit (`toolbox_audit_2026-07-01.md`). Scope + access rule: `README.md`.

## The robustness doctrine (every fix below must satisfy all three)

This repo's recurring failure is **prose masquerading as mechanism** — "runs in CI" was false; the
comprehension gate self-certified with no artifact. So no item is "done" when a markdown file asserts
it. A fix is done only when it is:

1. **Auto-invoked, not remembered** — it fires on push / on tool-call / on the default code path,
   never depending on an agent or human *choosing* to run it.
2. **Self-proving** — it ships with a *planted-violation test*: a deliberate breach that makes the
   guard fail. A guard you have never watched fail is a guard you do not know works.
3. **Recorded** — a dated `current_state.md` entry + this strike, per `README.md`. An unrecorded
   workflow change is the same drift this project flags everywhere else.

---

## Open

**The autonomous-builder guardrail program** (added 2026-07-07). Full spec + planted-test + sequencing
per item in `autonomous_builder_build_plan_2026-07-07.md`; direction recorded in `current_state.md`
(2026-07-07 `[decided] [plan]`). Each item still owes its own strike + `current_state.md` entry when built.

- [ ] **G1. Close the `_truth` firewall to `Read`/`Grep`/`Glob`** (audit BLOCKER-1). ~S. *Do first.*
- [ ] **G2. Enforced dollar gate** — phase fails if it doesn't beat all 3 baselines in realized cost. M.
- [ ] **G3. Executable "done when"** — per-phase acceptance predicate as a required test. M.
- [ ] **G4. Cold re-review of the fix diff** (unfreeze deliverable #3; closes audit MAJOR-3). M.
- [ ] **G5. Test-adequacy** — planted-mutant check (no heavy dep — mind the conda-lock trap). M.
- [ ] **G6. Facts-are-artifacts** — records quote generated metrics, agents never type numbers. M.
- [ ] **G7. Stop-condition** — escalate, never override (the unattended-safety keystone). M.
- [ ] **G8. Two-reviewer quorum on high blast radius** (unfreeze deliverable #4). M.
- [ ] **C1. `/run-phase` conductor** + structural per-subagent model assignment (folds in #6). L.

Milestones: **M1** = G1+G6+G2+G3 (leakproof + honest) · **M2** = G4+G5+G8 (trusted fixes) · **M3** = C1 ·
**M4** = G7 (unattended). Do not advance an autonomy stage past an un-proven guard.

## Done — 2026-07-07

- [x] **20. Run the loop once for real (third audit's BLOCKER).** Both halves now exist. *(a) Review
      half:* first real `Pn_review.md` via `/review-phase` — produced 2026-07-02 (P2 re-review). *(b)
      Comprehension half:* Jay's `/learn` sessions on 2026-07-06 and 2026-07-07 moved real
      `docs/mastery.md` levels off L0 (topics 1/3/9 → L2, 7/10/13 → L1 on the 6th; topic 2 → L1 on the
      7th). The tutor — not the agent — wrote every grade, as `00-process.md` requires. *Follow-on the
      same feedback surfaced:* the comprehension track was assessment-only, so the acquisition beat
      (`/explain` + `concept-explainer` + `docs/glossary.md`) and level-tiered quizzes were added —
      recorded in `current_state.md` (2026-07-07).

## Done — third-audit response (2026-07-02)

- [x] **14. Close the `_truth` hook substring bypass** (audit M1). Sanctioning is now structural —
      quote-aware comment-strip + segment split; pytest/make-test sanctions only the segment it
      leads. 6 planted bypass tests added to `tests/test_truth_access_hook.py` (13 total).
- [x] **15. Write-scope mechanism for the four scoped subagents** (audit M2).
      `.claude/hooks/enforce_agent_write_scope.py` (keyed on the harness's `agent_type` hook field)
      denies Write/Edit outside each agent's one artifact and Bash-level mutation (redirects,
      `sed -i`, mutating git) of the repo tree; registered in `settings.json` for Bash +
      Write/Edit/NotebookEdit; 28 planted tests in `tests/test_agent_write_scope_hook.py`. *Known
      limit:* hook config snapshots at session start, so the wiring is live from the next session;
      the hook logic itself is CI-proven.
- [x] **16. Relay-from-file** (audit M4). `/review-phase`, `/review-web`, `/audit-toolbox` now
      require the relay be produced by Reading the artifact file (path + shasum printed) — a
      relay-vs-file mismatch is impossible by construction, replacing the never-run manual diff.
- [x] **17. Self-record drift fixed + meta-backlog frozen** (audit MINOR + kill list #1).
      `subagent_workflow_deliverables.md`: #2 struck as built (`62daf42`); #1/3/4/5/6 frozen until
      the loop has run once end-to-end.
- [x] **18. Rules 05/07 narrowed** (audit MINOR) to `onramp/**/web|api/server/routes/**` — pure-
      compute plate-cost Python no longer loads web rules (~1.8k tok/turn on those turns). Note:
      the audit's claim that rule 06 "matches zero files" was stale — `onramp/plate_cost/web/static/
      style.css` exists — but 06 needs no change either way; it fires correctly on real front-end files.
- [x] **19. Rule 99 canary: considered, KEPT** (audit kill list #3 — owner's call). ~143 tok/turn;
      it is Jay's live drift tripwire and fired in the very session that landed this audit. Not waste;
      revisit only if Jay stops using it.

## Retired

- [x] **8. Give the gate teeth + dry-run it before real work.** *Retired 2026-07-01 — the gate itself
      was removed, so there is nothing to give teeth to.* The comprehension exit-gate is gone from the
      whole loop. Reviewers (`phase-reviewer` / `web-reviewer`) keep every adversarial-review duty
      (leakage, splits, dollar-metric verdict, firewall, seam/UI/API hunts) and **review build progress
      only** — no gate of any kind lives inside them. See `current_state.md`'s 2026-07-01 entry.
      **Implemented (same day):** the exit-gate sections were stripped from `phase-reviewer.md` /
      `web-reviewer.md` / `review-phase.md` / `review-web.md` / `reviewer_report_format.md`;
      `00-process.md` was rewritten to make comprehension a parallel track; and
      `tests/test_phase_gate_artifacts.py` (the CI teeth this item wanted to build) was **deleted** —
      there is no closing-artifact to enforce anymore.
      **Comprehension's new home:** a fully parallel spaced-repetition track — the `/learn` command +
      `comprehension-tutor` subagent maintaining `docs/mastery.md`. It never gates a build, review, or
      merge; it grows and re-checks understanding on its own cadence. The ghost-writing / self-certified
      -gate risks this item named are moot: nothing about comprehension can block shipping, so there is
      nothing to fake to unblock it.
