# Agentic workflow — subagent-loop deliverables

Remediation for the 2026-06-30 "Third pass: subagent/multi-agent mechanics" entry in
`current_state.md`. That entry is the record of what's wrong; this file is the plan to fix it — six
deliverables, one per gap found, each with a concrete solution and a done-when test. None of these are
built yet. Strike an item here and add a dated `current_state.md` entry when it lands, same convention
as `efficiency_backlog.md`.

Two of these (2, 3) sharpen/compound existing `efficiency_backlog.md` items (#7, #8) rather than
duplicate them — noted per item.

---

## 1. Verification-integrity check for the reviewer

**Problem:** `phase-reviewer.md`/`web-reviewer.md` Step 1 mandates "run pytest/ruff yourself, don't
trust by reading," but nothing forces the reviewer to notice when its own verification command errors
(e.g., wrong conda env — `efficiency_backlog.md` #1) instead of running. A cold-context reviewer can
report "TEST + LINT: passed" when the command it ran actually failed to execute at all.

**Deliverable:** A mandatory verification ledger in the reviewer's report — the literal command plus
literal exit code/output for every check it claims to have run, not just the conclusion.

**Solution:** Edit `.claude/agents/phase-reviewer.md` and `web-reviewer.md` Step 1 to require: (a) run
via `make test` / `make lint` once those targets exist (ties to `efficiency_backlog.md` #1's Makefile,
so the reviewer can't accidentally invoke the wrong env); (b) the Step 5 report includes a fenced
"Verification Ledger" block with each command run and its literal result; (c) if any command errors,
the VERDICT line must read `Can't determine — verification tool failed: <error>`, never a silent pass.
Add a planted-failure self-test: point the reviewer at a deliberately broken env (or rename the conda
env in a scratch copy) and confirm it reports "can't verify" rather than a false green.

**Done when:** A reviewer run against a broken verification environment reports "can't verify" in its
VERDICT line, never a silent pass, and this has been observed once for real.

---

## 2. Durable, un-relayed review artifact

**Problem:** The reviewer's independent opinion reaches Jay only after passing back through the same
main thread that orchestrated the build — "relay verbatim" is a prose instruction with nothing to check
it against. Sharpens `efficiency_backlog.md` #7 by naming it a subagent-trust failure specifically: the
value of a cold-context second opinion is destroyed if its only path to Jay is through the
non-independent party.

**Deliverable:** `docs/phase_decisions/Pn_review.md`, written directly by the reviewer subagent, read
by Jay directly.

**Solution:** Grant `phase-reviewer`/`web-reviewer` the `Write` tool, scoped by instruction to only
`docs/phase_decisions/**`. Update Step 4/5 of each agent spec so the subagent writes its full findings
block + sign-off to `docs/phase_decisions/Pn_review.md` before returning control. Update
`/review-phase` and `/review-web` to point Jay at the file path and to note that the in-chat relay can
be diffed against it — any mismatch is itself a finding about the relay, not the code.

**Done when:** Every review produces a committed `Pn_review.md`; the in-chat relay is checkable
word-for-word against a file Jay can open himself.

---

## 3. Independent re-review of BLOCKER fixes

**Problem:** A greenlit BLOCKER fix goes back to "a build pass" — the same builder/context that wrote
the original bug — which re-runs the suite itself and calls it resolved. No independent check that the
fix addresses the finding rather than just the symptom. Compounds `efficiency_backlog.md` #8 (the gate
having no teeth).

**Deliverable:** A mandatory fresh reviewer pass scoped to the fix diff before a BLOCKER can be marked
resolved.

**Solution:** Add to `/review-phase`'s post-fix step: for any finding tagged BLOCKER, re-invoke
`phase-reviewer` (fresh cold-context subagent, not the same thread) scoped to `git diff` of just the
fix, before that finding is marked resolved in `Pn_review.md`. MAJOR/MINOR/NIT fixes stay self-verified
by the builder — proportionate, not blanket.

**Done when:** No BLOCKER finding is ever marked resolved without a second, independent reviewer pass
over its specific fix, verified on the next phase that produces a BLOCKER.

---

## 4. Blast-radius-scaled review depth

**Problem:** Every phase gets exactly one reviewer pass at fixed depth, whether it's a mechanical
feature or a change to `data/CONTRACT.md` / `schemas/` / the seam boundary. No escalation path for
higher-stakes changes.

**Deliverable:** A blast-radius rubric plus a two-pass escalation tier in `/review-phase` and
`/review-web`.

**Solution:** Add a short classifier to both review commands: a phase is "high blast radius" if its
diff touches `data/CONTRACT.md`, `schemas/**`, anything under `forecasting/src/evaluate/` that reads
`_truth/`, or crosses the on-ramp/engine seam. For those, require **two independent reviewer passes**
(two separate cold-context subagent invocations, findings reconciled by Jay) instead of one, or a
pre-build design note before code lands. Standard phases keep the single-pass default.

**Done when:** The next high-blast-radius change (a `data/CONTRACT.md` or `schemas/` edit) actually
receives two independent passes, not one — confirmed by two distinct `Pn_review.md`-equivalent
artifacts.

---

## 5. Findings-to-rules feedback loop

**Problem:** Each `phase-reviewer` invocation starts cold with zero institutional memory beyond what
`.claude/rules/` currently states. A bug class caught in one phase's review doesn't structurally
propagate into the next phase's checklist — only a human hand-editing the rule file makes that happen.

**Deliverable:** A "graduate the finding" step appended to the review-close protocol.

**Solution:** When a review's comprehension gate closes (`/review-phase`'s closing step), add one
explicit question before the phase is marked done: "does this finding's failure mode generalize beyond
this phase?" If yes, require a one-line addition to the relevant `.claude/rules/0N-*.md` hunt list (or
the reviewer agent's own hunt list) in the same commit that closes the phase, so the check is
structural rather than a hoped-for memory.

**Done when:** At least one real review finding has demonstrably graduated into a rule file, traceable
via `git blame` back to the phase that produced it.

---

## 6. Effort-scaled orientation subagent

**Problem:** The `Explore` subagent in `build-phase.md` Step 0 always runs at fixed
`search breadth: thorough`, regardless of whether the phase is a two-file tweak or a new module — no
effort-scaling dial. Lowest-severity of the six; flagged for completeness.

**Deliverable:** A breadth selector keyed to phase size.

**Solution:** In `build-phase.md` Step 0, before spawning `Explore`, estimate phase size from the
roadmap section's "Build" bullet count (or line count) for `$ARGUMENTS`. Pass `search breadth: quick`
for phases with a small, single-module footprint; `thorough` for phases touching more than one module
or introducing a new seam artifact.

**Done when:** A small phase's orientation pass measurably uses fewer tool calls than a large one's,
without missing a load-bearing dependency (spot-check against a phase already built, e.g. re-run
orientation for P0 at `quick` and confirm nothing load-bearing was missed).

---

## Sequencing

**1 → 2 → 3, then 4 and 5 in parallel, then 6.** 1 and 2 fix trust in the loop itself (a review you
can't tell succeeded, and an opinion you can't verify was relayed intact, undermine everything built on
top of them) — do those first. 3 depends on 2 (you need the durable artifact to know what a BLOCKER
fix is being re-reviewed against). 4 and 5 are independent of each other and of 1-3. 6 is a minor
efficiency tweak with no dependency on the others — lowest priority.
