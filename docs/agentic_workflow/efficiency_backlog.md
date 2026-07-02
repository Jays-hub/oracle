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

- [ ] **20. Run the loop once for real (third audit's BLOCKER).** Two halves. *(a) Review half:*
      first real `Pn_review.md` via `/review-phase` — produced 2026-07-02 (P2 re-review). *(b)
      Comprehension half:* **Jay runs `/learn` once** and a `docs/mastery.md` level actually moves.
      The agent cannot close (b) — only the tutor grading Jay's live answers writes the ledger;
      anything else would fabricate comprehension (`00-process.md`). Strike when both halves exist.

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
