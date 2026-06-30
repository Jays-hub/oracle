---
alwaysApply: true
---
# Process & Comprehension Rules (the gate on every step)

## The Comprehension Contract (Highest Priority — governs all other rules)
- **No code for a new step is written until Gates 1–3 are explicit AND Jay has cleared Gate 4 in his own words.** This operationalizes the PRIME DIRECTIVE in `CLAUDE.md`; the full reasoning lives in `docs/overview_and_method.md` (The Comprehension Contract). When this rule conflicts with an impulse to deliver, this rule wins.
- **Why it's a rule, not prose.** An instruction an agent is merely asked to remember is hope, not enforcement. A standard in the always-applied rules layer is invoked *every time work happens* — not a laminated sheet glanced at occasionally.

## The four gates (clear before writing code for any new step)
- **Gate 1 — Why this, why now.** The problem the step solves, and why it is the right *next* step — the dependency that puts it now, not later. If the sequencing can't be justified, the dependency structure isn't understood yet.
- **Gate 2 — Codebase impact.** The files/modules it touches, what it produces, and what it unlocks downstream.
- **Gate 3 — Practices invoked, in all three domains.** Named explicitly: (a) software/coding craft, (b) data-science/statistical concept, (c) restaurant-domain or consulting standard. A step describable in only one domain is half-understood.
- **Gate 4 — Comprehension check (Jay clears this; the agent never self-certifies it).** Do not proceed until Jay (1) restates the step in his own words, including the failure mode it guards against, and (2) gives the "say it to a chef" one-liner. Capture both in the phase's notebook before the step closes.

## How the agent applies this
- **Present Gates 1–3, then stop and elicit Gate 4.** Writing code before Jay clears Gate 4 violates this rule.
- **One step at a time.** Never batch un-gated steps; each new step re-runs the gate.
- **Name the drift.** Per the Anti-Drift Standing Order (`CLAUDE.md`): if a step reaches for sophistication before the simpler, higher-value step exists and beats the baseline in dollars, say so and redirect to the simplest thing that respects the economics. Comprehension is not a license to deepen.
- **Scope.** "A step" = any new module, model layer, feature group, data transform, or decision-logic change across P0–P8. Mechanical edits already specified and understood (typos, formatting, a rename Jay requested) do not re-trigger the gate.
