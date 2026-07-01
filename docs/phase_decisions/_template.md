# Phase __ Decision Log

> **What this file is:** The build agent's reasoning trace for this phase — why things were built the
> way they were, not what was built (that's `progress_log.md`). The design sections are written by the
> builder and read by the adversarial reviewer. There is **no comprehension section here** — as of
> 2026-07-01 comprehension runs on a parallel track (`/learn` + `docs/mastery.md`) that gates nothing;
> this file is purely the builder's briefing for the reviewer.

**Built:** YYYY-MM-DD  
**Phase:** Pn  
**Branch:** phase/Pn  

---

## Load-Bearing Assumptions

Assumptions the build rests on that would change the approach if wrong.

| Assumption | How confirmed | Status |
|---|---|---|
| ... | read `path/to/file` | confirmed |
| ... | inferred from schema | **unconfirmed — risk** |

---

## Key Design Decisions

For each non-obvious choice: what was picked, what was the alternative, and why.

### Decision: [short name]
- **Chose:** ...
- **Over:** ...
- **Because:** ...
- **Risk if this was wrong:** ...

---

## Constraints Encountered Mid-Build

Things discovered during the build that were not visible in the spec — schema mismatches, boundary
rule conflicts, upstream gaps, naming drift.

- ...

---

## Explicitly Deferred

Items in scope for this phase that were deliberately not built, and where they are recorded.

| Item | Deferred to | Recorded in |
|---|---|---|
| ... | Phase X | `forecasting/docs/construction_roadmap.md` |

---

## Reviewer Focus Areas

The builder's honest assessment of the two weakest spots. The reviewer should look here first.

1. **[area]** — reason for low confidence
2. **[area]** — reason for low confidence
