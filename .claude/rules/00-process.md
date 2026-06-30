---
alwaysApply: true
---
# Process & Comprehension Rules (the gate on every phase's *exit*, not its start)

## The Comprehension Contract (Highest Priority — governs all other rules)
- **Building is never gated. The *review* is.** The agent may explore, plan, and write code for a step
  without waiting for any comprehension clearance. There is no "present gates and stop before coding"
  step. What is gated is the **close of the review**: a phase's review may **not** be signed off and the
  phase may **not** be marked done until Jay can **fully explain, in his own words, the changes made
  during both the build and the review.** This operationalizes the PRIME DIRECTIVE in `CLAUDE.md`; full
  reasoning lives in `docs/overview_and_method.md` (The Comprehension Contract). When this rule
  conflicts with an impulse to *close out* a phase, this rule wins.
- **Why the exit, not the entrance.** Gating the build stalls delivery and lets comprehension be
  pre-certified against code that doesn't exist yet. Gating the review exit means the explanation is
  tested against the **real, finished, reviewed code** — what was actually built and what the review
  actually changed — which is the only thing worth understanding.
- **Why it's a rule, not prose.** An instruction an agent is merely asked to remember is hope, not
  enforcement. A standard in the always-applied rules layer is invoked *every time work happens* — not a
  laminated sheet glanced at occasionally.

## The comprehension gate (clear before the review closes)
The review is not finished — no final sign-off, no "phase done" — until Jay demonstrates comprehension
of the completed work. His explanation, **in his own words**, must cover all four:
- **What & why.** What this phase built and why it was the right step — the dependency that placed it
  here. If he can't justify the sequencing, the work isn't understood yet.
- **Codebase impact.** The files/modules it created or touched, what they produce, and what they unlock
  downstream.
- **Practices invoked, in all three domains, named explicitly:** (a) software/coding craft, (b)
  data-science/statistical concept, (c) restaurant-domain or consulting standard. Work describable in
  only one domain is half-understood.
- **The review delta + the failure mode.** What the adversarial review found and what it changed (or
  why it changed nothing), and — stated as the sentence **"The failure mode this guards against is
  ___."** (filled in) — the defect class the build-and-review guarded against. He must also give the
  **"say it to a chef"** one-liner.

**Jay clears this; the agent never self-certifies it.** Until his explanation contains all four
(including the filled-in failure-mode sentence and the chef one-liner), the gate is **not** cleared —
keep the review open and ask again. Capture his explanation verbatim in the phase's decision log before
the phase closes.

## How the agent applies this
- **Build freely; close carefully.** Write code, run tests, and hand off to review without waiting on a
  comprehension step. Then hold the review open until Jay's explanation lands.
- **One phase's review at a time.** Don't batch closes; each phase re-runs the exit gate against its own
  completed, reviewed code.
- **Name the drift.** Per the Anti-Drift Standing Order (`CLAUDE.md`): if a step reaches for
  sophistication before the simpler, higher-value step exists and beats the baseline in dollars, say so
  and redirect to the simplest thing that respects the economics — at any point, build or review.
  Comprehension is not a license to deepen.
- **Scope.** "A phase" = any new module, model layer, feature group, data transform, or decision-logic
  change across P0–P8 (and the on-ramp Wn phases). Mechanical edits already specified and understood
  (typos, formatting, a rename Jay requested) do not trigger the review or its exit gate.
