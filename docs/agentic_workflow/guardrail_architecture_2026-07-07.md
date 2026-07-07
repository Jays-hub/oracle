# Guardrail Architecture for an Autonomous Builder — 2026-07-07

**The decision (Jay, this session):** mastery is decoupled and lives on the `/learn` track. The build
track should be a **fully automated building system with minimal user input**. The precondition Jay named:
**rigorous, accurate guardrails** so that automation does not admit **drift, bad coding practices, or
hallucinations**.

This document is the guardrail architecture that makes that safe. It changes no `.claude/**` yet — acting
on it is a workflow change that then owes a `current_state.md` + `efficiency_backlog.md` entry. Companion
to `orchestration_analysis_2026-07-07.md` (which specced the *conductor*); this speccs the *guardrails
the conductor needs before the human can step out*.

---

## 0. The reframe: minimal *ongoing* input is bought with heavier *upfront* input

You cannot remove the human from the **definition** of correct. You can only remove them from the
**execution** of checking it. So "minimal user input" does not mean zero input — it means moving your
judgment from *per-phase greenlighting* (reactive, every lap) to *per-phase authoring of the acceptance
predicate* (declarative, once, up front). You write the machine-checkable "done when"; the machine runs
against it unattended. That is the actual frontier practice for autonomous agents, and it's the only
version of "minimal input" that is also safe.

**The one irreducible human job that remains:** author the executable acceptance test and the guardrail
tests. Everything downstream of that can be automated. Everything upstream of it cannot — a machine that
also gets to define its own success criterion is not automated, it's unsupervised.

---

## 1. The core principle, and the three classes of guarantee

> **Every claim that matters must be verified by a mechanism the builder cannot influence.**

A claim verified by prose the agent is *asked* to honor is not verified — today's audit is the proof:
the mechanical hooks held (denied the auditor live); the one prose-not-mechanism promise ("fixes re-enter
and are self-verified") leaked, and 2 of 2 engine reviews overturned the builder's own headline number.
Trust tracks mechanism, not intention. Three kinds of mechanism, strongest first:

| Class | What it guarantees | The builder can't influence it because… | Your assets today |
|---|---|---|---|
| **Structural** | A violation is *impossible*, not just detected | it's enforced at the tool/import boundary, below the agent | import-linter seam contracts; `_truth` deny hook; write-scope hook; ruff; pinned-env `make` |
| **Recomputational** | A claimed result is *re-derived independently* | a different cold agent recomputes it and overwrites the claim | the reviewer running `make test` + the metric itself |
| **Economic** | Sophistication that doesn't pay *cannot merge* | the dollar comparison is objective and code-produced | the three baselines + realized-cost metric exist… as a *norm*, not a gate |

Plus one cross-cutting discipline that kills the most common hallucination:

> **Facts in records must be generated, not narrated.** Any number an agent *types* into a doc is a
> hallucination surface (the audit found "353 tests" in a doc while the tree had 358; the builder's
> "$15.6k win" that review corrected to $610.58). Any number a *build step emits into an artifact* and the
> record *quotes* is not. Take away the agent's opportunity to author a metric at all.

---

## 2. The precondition rule: guardrails before autonomy, each proven before it earns a touchpoint

You do not get to remove a human check until the mechanism that replaces it **has been watched to fail on
purpose and caught it** — your own "self-proving" doctrine. So the build order is not "write the
autonomous loop, then add guards." It is: **close each verification gap, plant a violation test that
proves the guard bites, and only then delete the human touchpoint that guard makes redundant.** Autonomy
is the *residue* of proven guardrails, not a feature you switch on.

This is also what keeps this whole effort on the right side of the Anti-Drift order: you are not "building
a big autonomous system" (sophistication ahead of need). You are closing specific, named verification
holes — each self-proving, each recorded — and full automation falls out as the human touchpoints become
provably redundant.

---

## 3. Your three named failure modes → the mechanism for each

### Bad coding practices — *your strongest surface; mostly READY*
Leakage, wrong splits, non-reproducibility, seam violations, style. These are already **structural** and
CI-enforced: import-linter contracts + boundary tests (seam), the leakage canary default-on
(`pipeline.py` `check_leakage=True`) with its planted test, `random_state=42`, ruff, `make test` on a
pinned env. An autonomous builder can lean on these **today** — they don't care whether a human is
watching. **One gap that graduates to load-bearing under automation:** the audit's BLOCKER — the `_truth`
firewall is enforced for `Bash` but **open to the `Read`/`Grep` tools**. With a human watching that's
minor; with an unattended agent that could `Read` the oracle to "check" its own output and silently
contaminate its reasoning, it is the single most dangerous open hole. **Close it first.**

### Hallucinations — *partly ready; needs two disciplines*
Two sub-kinds:
- *Hallucinated code* (nonexistent function, wrong API) — caught **structurally** by `make test` / `make
  lint` / import errors. Ready.
- *Hallucinated results* ("beats baseline", a dollar figure, a test count, "done") — caught **only** by
  recomputation. The reviewer already re-derives the number and overwrites the builder's — keep that,
  and add the *facts-are-artifacts* discipline (§1) so the recorded number comes from a build step, never
  a keystroke. **The hole:** the *fix* pass currently escapes recomputation (self-verified — audit
  MAJOR-3 / frozen deliverable #3). Under automation with no human backstop, an unreviewed fix is an
  ungoverned write to the exact code the review just flagged. **Non-negotiable to close.**

### Drift — *your weakest surface; this is where automation is currently unsafe*
"Reaching for sophistication before the simpler dollar step," and drift into the on-ramp. Today this is
defended by **prose** ("Name the drift") — hope, not mechanism, and hope is what fails when no human is
reading. Two mechanizations:
- **Economic gate (primary):** a build step (`make evaluate`-style) that computes realized cost
  `Σ(Co·overage + Cu·underage)` against the three baselines (seasonal-naive, 28-day rolling, gut-proxy)
  and **fails the phase** if the new layer doesn't beat all three. Drift-into-sophistication becomes
  *economically unmergeable*, not merely discouraged.
- **Scope-diff check (secondary):** fail if the diff touches files outside the phase's declared target
  dirs — catches "built later phases' work now" scope creep, the on-ramp-drift vector included.

---

## 4. The guardrail catalog — what to lean on, what to build

**READY — the autonomous loop can trust these today** (all structural, all CI/hook-enforced):
import-linter seam contracts · leakage canary default-on + planted test · write-scope hook (`agent_type`)
· ruff · pinned-env `make test` · reproducibility seed · module-boundary tests · `_truth` Bash deny.

**BUILD — the gap between "a human does this" and "a mechanism does this":**

| # | Guardrail | Replaces which human job | Failure mode it stops | Maps to |
|---|---|---|---|---|
| G1 | **Close `_truth` to `Read`/`Grep`/`Glob`** (+ planted tests) | human noticing an oracle peek | silent leakage into the agent's own reasoning | audit BLOCKER-1 |
| G2 | **Enforced dollar gate** — phase fails if it doesn't beat all 3 baselines in realized cost | human judging "is this worth it" | drift into unpaid sophistication | new; makes the norm a test |
| G3 | **Executable "done when"** — each phase's acceptance criterion encoded as a test that must exist and pass to close | human judging "is it actually done" | hallucinated completion | new; the upfront-input trade (§0) |
| G4 | **Cold re-review of the fix diff** | human re-checking the fix | a fix that treats the symptom / adds a new bug | deliverable #3 (frozen) |
| G5 | **Test-adequacy check** (mutation-style: inject a known bug, confirm the builder's own tests catch it) | human sensing "these are smoke tests" | self-authored tests that self-pass | new; extends your planted-test philosophy |
| G6 | **Facts-are-artifacts** — records quote code-emitted metrics, agents never type numbers | human spotting a fabricated figure | hallucinated results / stale counts | new discipline; kills the "353 vs 358" class |
| G7 | **Bounded-retry + escalate-to-human stop condition** | human deciding "stop / try again / it's stuck" | thrashing, or declaring false success | new; the safety keystone (§6) |
| G8 | **Two-reviewer quorum on high blast radius** (`CONTRACT.md`, `schemas/`, `_truth`-path) | human giving big changes extra scrutiny | a single reviewer's hallucinated green | deliverable #4 (frozen) |

Note how much of the "BUILD" column is **already designed and frozen** in
`subagent_workflow_deliverables.md` (#3=G4, #4=G8) — you specced these; automation is the reason to
unfreeze them. The genuinely new ones are the *drift* and *stop-condition* mechanisms (G2, G3, G7),
which is consistent with drift being the weakest surface (§3).

---

## 5. The autonomy ladder — remove human touchpoints in the order their guardrails come online

Full automation is not a leap; it's the removal of the §3-analysis's seven ✋ touchpoints one at a time,
each unlocked by a proven guard. Trust is earned incrementally.

| Stage | Human still does | Unlocked once these are proven |
|---|---|---|
| **A0 (today)** | model-switch, invoke build, invoke review, greenlight, invoke fix, invoke ship | — |
| **A1 conductor** | greenlight only | conductor chains stages; per-subagent model overrides (structural) |
| **A2 trusted fixes** | greenlight only (fixes now auto-re-reviewed) | G4 cold re-review + G8 quorum proven |
| **A3 auto-close on green** | *author the acceptance test up front*; greenlight only on BLOCKER/MAJOR or on a raised flag | G2 dollar gate + G3 executable done-when + G5 test-adequacy proven |
| **A4 unattended** | *author the acceptance test*; get pinged only when the system escalates | G6 facts-as-artifacts + G7 stop-condition + G1 closed, all planted-tested |

At **A4** your ongoing input per phase is: write the "done when" test, then read an escalation only if one
fires. That is "fully automated with minimal user input" — and every ✋ you removed was replaced by a
guard you watched bite, not by trust.

---

## 6. The safety keystone: the failure mode must be "stop and ask," never "declare success"

The single most important property of an unattended builder is what it does when a guard *fails*. A
system that thrashes, or worse, rationalizes a red into a green to finish the loop, is more dangerous than
no automation. So G7 is not optional polish — it is the property that makes the rest safe to trust:

- **Bounded retries.** N attempts at a failing gate, then **hard stop**.
- **Escalate, never override.** On repeated failure, or any guard the agent cannot satisfy, the loop
  **halts and surfaces to Jay** with the artifact and the failing check. It may never lower a bar,
  weaken a test, or edit a guard to pass. (Your write-scope hook already blocks the agent editing its own
  guards — that structural fact is what makes "escalate, never override" enforceable rather than hoped.)
- **Loud failure > silent success**, always.

---

## 7. The honest limit

Two things no mechanism fully removes, worth stating plainly so the automation isn't over-trusted:

1. **Correlated blind spots.** If the same model both writes code and writes the check, a hallucination it
   makes is one it may also rationalize. Your **Sonnet-builds / Opus-reviews** split is not just a cost
   choice — it's *epistemic decorrelation*, and for full automation it's worth pushing further: make the
   reviewer a different model *family* from the builder so their blind spots don't line up. Quorum (G8)
   mitigates; it never fully eliminates.
2. **The acceptance predicate itself.** If your machine-checkable "done when" is wrong or shallow, the
   system will faithfully, autonomously satisfy the wrong thing. This is the residuum from §0 — it is why
   the human authoring the test is the one job that can't be delegated, and why the guardrail effort's
   real payoff is proportional to how good *that* artifact is.

---

## 8. Bottom line + where to start

A fully automated builder is achievable here, and — unusually — the path is *anti-drift-safe*, because
it's not "build a big autonomous system," it's "close eight named verification gaps, each self-proving,
and delete a human touchpoint only after its replacement is proven." Autonomy is the residue.

**Start with the three that convert the most human-judgment into mechanism and are load-bearing the moment
a human stops watching:**

1. **G1 — close the `_truth` `Read`/`Grep` hole.** ~20 lines + planted tests. The one open leakage vector
   that a human is currently the only thing guarding.
2. **G2 + G3 — the dollar gate and executable "done when."** These mechanize the two judgments (is it
   worth it / is it done) that automation removes the human from — i.e. they attack *drift* and
   *hallucinated completion*, your two weakest surfaces.
3. **G4 — unfreeze deliverable #3, the cold re-review of fixes.** Closes the self-attestation hole before
   an unattended loop starts writing fixes nobody sees.

Only after those bite would I build the conductor (A1) and start removing touchpoints. The conductor is
the easy part; it's the guardrails that earn the right to run it unattended.
