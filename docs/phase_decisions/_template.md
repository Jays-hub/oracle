# Phase __ Decision Log

> **What this file is:** The build agent's reasoning trace for this phase — why things were built the
> way they were, not what was built (that's `progress_log.md`). The design sections are written by the
> builder and read by the adversarial reviewer. The **Comprehension Capture** section is left blank by
> the builder and filled at the **review's exit**, when Jay explains the finished work and the review
> closes (`.claude/rules/00-process.md`).

**Built:** YYYY-MM-DD  
**Phase:** Pn  
**Branch:** phase/Pn  

---

## Comprehension Capture (filled when the review closes — the phase's exit gate)

Jay's own-words explanation of the **finished, reviewed** work. The review does not close until this
whole section is present — the fenced block filled with his actual words (not a paraphrase, not agent
prose standing in for it), and every citation below pointing at a real sentence inside that block. A
citation that can't be found verbatim in the fenced block means the gate is not cleared yet.

**JAY-VERBATIM (paste, unedited):**
```
<paste Jay's full explanation here exactly as he wrote it — do not summarize, correct, or reformat it>
```

**Which sentence satisfies each part** (quote the exact substring from the block above):

1. **What & why:** "..."
2. **Codebase impact:** "..."
3. **Practices in all three domains** — (a) software/coding, (b) data-science/statistical, (c)
   restaurant/consulting: "..." / "..." / "..."
4. **Review delta + failure mode + chef one-liner:** "The failure mode this guards against is ..." /
   "..."

If any citation is missing, leave it as `MISSING — ask again` rather than inventing a plausible-sounding
quote. A visibly empty citation is the point: it makes an incomplete gate impossible to mistake for a
cleared one.

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
