# Agentic Workflow — efficiency backlog

Prioritized, actionable fixes to the workflow. Items 1-7 and 9-13 of the second-audit's 13-item list
are done and archived in `current_state.md`'s 2026-07-01 entries (what was built, what was verified,
and any known imperfections) — only the one incomplete item is kept below so this file doesn't carry
dead weight. When you finish it, strike it here and add a dated entry to `current_state.md`. Scope +
access rule: `README.md`.

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

- [ ] **8. Give the gate teeth + dry-run it before real work.** *Mechanism built + CI-checked
      2026-07-01 (see current_state.md); the live dry-run itself still needs Jay's real, unedited
      comprehension explanation — cannot be done by the agent without recreating the exact
      ghost-writing failure mode this item exists to prevent.*
      **Forecloses:** (a) `build-phase.md:141` mandates a `Pn.md` decision log that P0/P1/P2 produced
      **zero** of → the gate is self-certified; (b) an agent can **ghost-write "Jay's verbatim"
      explanation**, and the inverted exit gate has **never been exercised**.
      **Robust fix:** `/review-phase` refuses the closing `[done]` entry unless
      `docs/phase_decisions/Pn.md` exists with its Comprehension Capture filled; CI checks a merged
      phase carries its `Pn.md`. The capture must be a fenced `JAY-VERBATIM (paste, unedited)` block,
      and the agent must **quote which sentence satisfies each of the four parts**, so a missing
      domain is visibly empty rather than silently completed. **Run one dry-run phase end-to-end
      before P3** — the lag-7 fix (#2) is the vehicle.
      **Done when:** no phase closes without a filled `Pn.md`, and the loop has been run once for real.
