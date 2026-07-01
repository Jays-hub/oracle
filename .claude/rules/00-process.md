---
alwaysApply: true
---
# Process Rules — building and review are ungated by comprehension

## Comprehension is a parallel track, not a gate (Highest Priority — governs all other rules)
- **Nothing about Jay's understanding blocks work.** Building is never gated; the agent may explore,
  plan, and write code freely. **Review is not gated either** — a phase's review closes on the **code**
  (findings relayed, greenlit fixes landed and re-passed, the closing `docs/progress_log.md` entry
  written). There is no comprehension exit gate, no per-phase verbatim capture, no "the review can't
  close until Jay explains it." That coupling was removed 2026-07-01.
- **Where comprehension lives now.** Understanding is grown and *re-checked over time* on a separate,
  parallel track: the **`/learn`** command drives the **`comprehension-tutor`** subagent, which quizzes
  due topics grounded in the real code and maintains **`docs/mastery.md`** — a spaced-repetition ledger
  of what Jay understands, per topic, at a mastery level that sets when each topic resurfaces. This runs
  on its own cadence and **never** blocks a build, a review, a merge, or a phase close.
- **Why decouple them.** Shipping is fast and per-phase; understanding is slow, cumulative, and needs
  *re-testing over time* to confirm it stuck. Gating the review on comprehension forced one clock to
  wait on the other and pre-certified understanding against a single moment. The parallel ledger lets a
  concept learned in P1 resurface in P4 on its own schedule, while code ships on its merits.
- **The agent never self-certifies comprehension, and never fabricates it.** Only the
  `comprehension-tutor` (through `/learn`) grades and writes `docs/mastery.md`. No other command,
  reviewer, or thread marks a topic understood. Reviewers (`phase-reviewer`, `web-reviewer`) review
  build progress only — they do not test, elicit, or hand off Jay's understanding.

## How the agent applies this
- **Build freely; close on code.** Write code, run tests, hand off to review, apply greenlit fixes,
  write the log entry. None of it waits on a comprehension step. If a phase introduced techniques worth
  locking in, running `/learn` afterward is the natural follow-up — but it is Jay's practice cadence,
  never a precondition.
- **Name the drift.** Per the Anti-Drift Standing Order (`CLAUDE.md`): if a step reaches for
  sophistication before the simpler, higher-value step exists and beats the baseline in dollars, say so
  and redirect to the simplest thing that respects the economics — at any point, build or review.
- **Scope of "a phase."** Any new module, model layer, feature group, data transform, or decision-logic
  change across P0–P8 (and the on-ramp Wn phases) is a phase and gets an adversarial review. Mechanical
  edits already specified and understood (typos, formatting, a rename Jay requested) do not trigger a
  review.
