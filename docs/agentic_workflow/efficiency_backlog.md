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

- [x] **8. Give the gate teeth + dry-run it before real work.** *Retired 2026-07-01 — by decision, not
      completion.* Jay is changing the reviewer subagent's duties: it keeps every original
      adversarial-review duty (leakage, splits, dollar-metric verdict, firewall, seam/UI/API hunts)
      but drops comprehension-checking entirely — **no gate of any kind lives inside the reviewer**
      going forward. See `current_state.md`'s 2026-07-01 decision entry.
      **Why the dry-run is moot:** the live dry-run this item called for existed to exercise the
      reviewer's refuse-to-close-without-a-filled-`Pn.md` behavior (Jay pastes a real, unedited
      comprehension explanation; the reviewer quote-checks it against the four parts). If that
      behavior no longer lives in the reviewer, there is nothing gate-shaped left on the reviewer side
      to dry-run — running it would be exercising a mechanism about to be removed.
      **Not yet done:** the actual file edits (stripping the comprehension-exit-gate sections from
      `phase-reviewer.md` / `web-reviewer.md` / `review-phase.md` / `review-web.md`) are Jay's to make
      separately — this entry records the decision and its consequence, not the implementation. Until
      those edits land, the files still describe the old gate-in-reviewer behavior; don't assume they
      already match this decision.
      **Original forecloses (superseded, not resolved):** the ghost-writing risk and the self-certified
      gate this item named are no longer addressed by a reviewer-side mechanism — if comprehension
      checking is meant to happen at all going forward, it needs a new home outside the reviewer
      (`.claude/rules/00-process.md` still describes the old model as of this note; reconciling it is
      outside this backlog item's scope).
