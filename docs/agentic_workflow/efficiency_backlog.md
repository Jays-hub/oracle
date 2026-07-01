# Agentic Workflow — efficiency backlog

Prioritized, actionable fixes to the workflow. All 13 items from the second-audit's list are now
closed — 1-7 and 9-13 done, #8 retired by decision (below) — and archived in `current_state.md`'s
2026-07-01 entries (what was built, what was verified, and any known imperfections). Kept as a
pointer rather than deleted so a future audit has somewhere to append. Scope + access rule:
`README.md`.

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

(none)

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
