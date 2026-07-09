# Orchestration Analysis — 2026-07-07

**A different question than the toolbox audit.** The audit asked *is the apparatus clean and honest*
(hooks, tokens, ceremony). This asks the question Jay actually values: **as a *manager of agents*, where
is my orchestration falling short of the frontier — parallel fan-out, long-horizon self-prompting,
hierarchical orchestrators (the "First Mate / Kun" class) — and where am I still doing by hand what a
command could do?** Concrete test case Jay posed: *I run build, then review, then greenlight fixes by
hand — why not one agent that does all three?*

This document does not touch `.claude/**`. It is analysis, not a change. Acting on any recommendation
here is a workflow change that would then owe a `current_state.md` entry + an `efficiency_backlog.md`
item, per this folder's convention.

---

## 0. The one-paragraph answer

You are not behind on *capability primitives* — you already delegate to cold-context specialist
subagents, which is L2 orchestration and above the median engineer. You are behind on **chaining**: every
hand-off between your agents passes through *you* as the message bus, and you assign models by hand. The
highest-leverage orchestration upgrade is a **conductor command** that runs builder → cold reviewer →
your single greenlight → fix pass → cold re-review → ship as one pipeline, collapsing ~5 manual pulls to
**1 decision**. But the specific thing you proposed — *one agent that builds, reviews, and greenlights
itself* — is the one design to reject: it destroys the adversarial separation that is the entire value of
your review. And the deeper finding: most of the frontier patterns you're benchmarking against
(parallel fan-out, autonomous long-horizon build) optimize **throughput**, while your project's declared
objective is **your own mastery**. Past the greenlight gate, more autonomy actively works *against* your
goal. A learning project's optimal orchestration is deliberately *less* autonomous than a shipping
project's.

---

## 1. Where you actually sit — the orchestration-maturity ladder

Grounded in your real files, not a generic scale.

| Rung | What it is | You? | Evidence in your repo |
|---|---|---|---|
| **L0** | One agent, one turn, human does the rest | past it | — |
| **L1** | Slash-commands encapsulate repeatable workflows | ✅ | `/build-phase`, `/review-phase`, `/ship`, `/learn`, `/explain` |
| **L2** | Commands spawn **specialist subagents** for sub-tasks | ✅ **you are here** | `build-phase.md:54` spawns an `Explore` subagent to orient; `review-phase.md` spawns cold `phase-reviewer`; write-scope hook keys on `agent_type` |
| **L3** | An **orchestrator** runs a multi-step pipeline (build→review→triage→fix→re-review) autonomously; human only at decision gates | ❌ **the gap** | You are the orchestrator. Every hop is a manual `/command`; you hand-carry findings between agents |
| **L4** | **Parallel fan-out** — N workers concurrently, results reconciled | ❌ (mostly N/A — see §4) | Only the single `Explore` pass fans out, and it's one worker |
| **L5** | **Long-horizon self-prompting** — agent maintains a task queue across turns, schedules its own next step | ❌ (mostly anti-goal — see §4) | Every turn is Jay-initiated; no `/loop`, no scheduled wakeups |
| **L6** | **Deep hierarchy** — a lead decomposes and spawns sub-leads that spawn workers over a shared blackboard | ❌ (overkill — see §4) | 2 levels max: main thread → one subagent |

**Read:** you're solidly at L2, with two frozen deliverables (#3 re-review, #4 blast-radius) that are
*already-designed* pieces of L3/L4 waiting to be built. The jump that matters is **L2 → L3**. L4–L6 are
frontier rungs whose fit to *this* repo is weak (§4).

---

## 2. The direct answer to "why not one agent for build + review + greenlight?"

Because three different things are bundled inside those three manual pulls, and they have opposite
requirements:

| Bundled thing | What it needs | Automate it? |
|---|---|---|
| **Orchestration / hand-offs** (run build, then invoke reviewer, then pass findings to a fix pass, then re-run) | Nothing — it's pure mechanical relay through you | **Yes.** This is the toil. A conductor eliminates it. |
| **Independence** (builder ≠ reviewer, cold context) | *Separation.* The reviewer's value is that it never saw the builder's rationalizations | **Preserve.** Collapsing agents destroys it. |
| **The greenlight** (which findings to fix; accept a tradeoff) | Human judgment with real leverage | **Keep, but reduce to one structured decision** instead of 5 interspersed pulls |

So "one agent that builds **and** reviews **and** greenlights itself" is the wrong target — it merges
row 1 (good to automate) with row 2 (must stay separate). A self-reviewing builder is exactly the
failure your whole governance is built to prevent, and today's audit already caught a *milder* version of
it: **MAJOR-3 — greenlit fixes re-enter as builder self-attestation; 2 of 2 engine reviews overturned the
builder's headline dollar number, and both corrected figures are outputs of remediation code no reviewer
ever saw.** A single build-review-greenlight agent doesn't shrink that hole; it makes the hole the whole
system.

**The right target:** not *one agent doing everything* — **one command orchestrating separate agents and
asking you once.** That is the "First Mate / lead-agent" pattern applied correctly: a persistent
*conductor* that delegates to independent workers and keeps the human at exactly the decision that needs a
human.

---

## 3. Your current loop, and every place it passes through you by hand

Traced from `build-phase.md` + `review-phase.md` + `ship.md`. ✋ = a manual human action that carries no
epistemic value (pure orchestration); 🧠 = a genuine judgment worth keeping.

1. ✋ `/model sonnet` — you switch models by hand. `build-phase.md:169-170` *literally reminds you to*.
2. ✋ `/build-phase Pn` — invoke build.
3. ✋ `/model opus` + ✋ `/review-phase Pn` — switch back, invoke review.
4. 🧠 Read `Pn_review.md`, decide **greenlight** — real judgment. Keep.
5. ✋ Tell the agent to apply fixes; ✋ `/model sonnet` again for the fix pass.
6. ⚠️ Fix pass **self-verifies** — no independent re-review (this is the frozen deliverable #3 / audit
   MAJOR-3). A correctness hole, not just toil.
7. ✋ `/ship`.

**Six of seven steps are ✋ mechanical.** The single 🧠 is step 4. That ratio *is* the finding: you are
spending manager-attention as a message bus and a model-selector, not as a decision-maker.

**Two of these are worth calling out specifically:**

- **Manual model assignment (steps 1, 3, 5) is a solved problem you're solving by hand.** The `Agent`
  tool takes a per-subagent `model` override (it's how this very analysis was run on Fable). A conductor
  spawns `builder(model: sonnet)` and `phase-reviewer(model: opus)` *structurally* — the Sonnet-builds /
  Opus-reviews division becomes a property of the pipeline instead of a sticky note you have to
  remember. Today it's prose ("`/model sonnet` keeps the division of labor"); it should be mechanism.
- **The self-verified fix pass (step 6) is where automation and correctness point the same way.**
  Deliverable #3 (a fresh cold re-review scoped to the fix diff) is *already designed and frozen*. A
  conductor is the natural place to force it: after fixes, auto-spawn a cold re-reviewer over `git diff`.
  This is the rare upgrade that both cuts your toil **and** closes an open correctness hole.

---

## 4. The frontier patterns you named — honest fit against *this* repo

You're benchmarking against the most robust workflows out there. Three of the four don't transfer,
and the reasons are specific to your work graph and your goal — not a knock on the patterns.

### Parallel fan-out (L4) — *weak fit here*
Where it would apply: (a) N candidate implementations of a phase, pick the best; (b) parallel *review
dimensions* (a leakage-reviewer, a dollar-reviewer, a seam-reviewer running concurrently); (c) two
independent reviews for high-blast-radius changes (= your frozen deliverable #4).
- (a) is low value: your phases are small and have hard sequential data dependencies (P4 needs P3's
  unconstrained demand), and for a *learning* project the goal is you understanding *one* clean solution,
  not diffing three.
- (b) is real but marginal — one reviewer already covers those hunts on small diffs; parallel reviewers
  buy depth only when a diff is big enough to overflow one context. That's exactly deliverable #4's
  trigger (touching `data/CONTRACT.md`, `schemas/**`, `_truth`-reading evaluate code).
- **Verdict:** the only fan-out worth building is the *conditional* two-reviewer escalation you already
  designed (#4), gated on blast radius. Broad parallelism has little surface area in a small,
  sequential, single-author work graph.

### Long-horizon self-prompting (L5) — *mostly anti-goal here*
The tools exist (scheduled wakeups, `/loop`, crons). An autonomous "build the next phase overnight,
review it, leave findings for morning" loop is buildable. But:
- It removes you from the build — and the build is where you learn. Your `CLAUDE.md` standing order #1
  makes **your understanding the point of the project**; today's audit names it the *actual bottleneck*.
  Automating yourself out of the build optimizes the wrong variable.
- It amplifies MAJOR-3: unattended self-fixes with no human at the greenlight is the self-attestation
  hole running unsupervised.
- **The one place L5 fits your goal instead of fighting it: the comprehension track.** Spaced repetition
  *is* a scheduling problem. A scheduled `/learn` nudge (or a `/loop` that resurfaces due `docs/mastery.md`
  topics) is long-horizon self-prompting aimed at the variable you actually want to move. That's the
  L5 investment that pays.

### Deep hierarchy (L6, "First Mate / Kun" in full) — *overkill here*
A lead spawning sub-leads spawning workers over a shared blackboard earns its complexity when a task
decomposes into many independent parallel subtrees with contention over shared state. Your unit of work
is one small phase, one author, one reviewer. The *entry-level* version of this pattern — a single
persistent conductor delegating to independent workers (§5) — captures ~all the value at ~none of the
coordination cost. Building past it now is the exact "sophistication before the simpler step" the
Anti-Drift order warns about.

---

## 5. The recommended build: a `/run-phase` conductor (the L2 → L3 jump)

One command whose **main thread is the orchestrator** (not a worker). It never writes code or reviews;
it *delegates and gates*.

```
/run-phase Pn
  │
  ├─ 1. spawn  builder         (subagent, model: sonnet)   → code + tests + decision log; runs make test/lint
  ├─ 2. spawn  phase-reviewer  (subagent, model: opus, cold) → writes docs/phase_decisions/Pn_review.md
  ├─ 3. relay from the artifact  →  present Jay ONE greenlight decision  🧠  ← the only human touch
  ├─ 4. on greenlight: spawn fix pass (model: sonnet) scoped to greenlit findings; re-run suite
  ├─ 5. for each BLOCKER/MAJOR: spawn a FRESH cold re-reviewer over the fix diff   (= deliverable #3)
  └─ 6. spawn /ship
```

**What it changes:**
- Human touches: **~5 ✋ → 1 🧠** (the greenlight). Everything else is delegation the conductor does.
- Model assignment becomes **structural** (per-subagent `model` overrides), retiring the manual
  `/model` dance and the prose reminder in `build-phase.md`.
- It **forces the frozen deliverable #3** (cold re-review of fixes) — closing audit MAJOR-3 by
  construction instead of by hope.
- **Independence is preserved at every stage** — builder, reviewer, fix-pass, and re-reviewer are each a
  separate cold subagent under the write-scope hook. The conductor coordinates; it does not merge them.

**What it explicitly must NOT do:** auto-greenlight, or let the reviewer be the same context as the
builder. The greenlight stays human; the review stays cold. Automate the transport, never the judgment or
the independence.

**Cost/risk:** this is real tooling-building, and both the Anti-Drift order and today's audit say *stop
building tooling, go do reps*. So the honest framing: the conductor is a **convenience multiplier on a
loop whose binding constraint is your understanding, not your click-count.** It makes each lap cheaper; it
does **not** move you toward #1-of-100. Build it if the manual hand-offs are genuinely costing you focus
— but don't mistake a smoother pipeline for a stronger engineer.

---

## 6. Ranked — if you build orchestration at all, in this order

1. **Structural model assignment inside a conductor.** Highest ratio of toil-removed to code. Retires
   three manual `/model` switches and a prose reminder; pure mechanism.
2. **The `/run-phase` conductor (§5), folding in deliverable #3.** The L2→L3 jump. Cuts touches 5→1 *and*
   closes the self-attestation hole. If you build one thing, build this.
3. **Conditional two-reviewer escalation on blast radius (deliverable #4).** The only fan-out that fits;
   fires only on `CONTRACT.md`/`schemas/`/`_truth`-path diffs. Cheap, targeted.
4. **Scheduled/`/loop` comprehension nudges (the L5 that fits).** Long-horizon self-prompting pointed at
   the variable that is actually your bottleneck — your mastery — instead of at build throughput.
5. **Effort-scaled orientation (deliverable #6).** Minor; the conductor can pass `Explore` a
   breadth keyed to phase size. Lowest priority.

**Do NOT build:** a single build-review-greenlight agent (§2); autonomous overnight phase-building
(§4); deep multi-agent hierarchy (§4). The first destroys your review's independence; the second and
third optimize throughput at the expense of the mastery that is your stated objective.

---

## 7. Bottom line

Your management of the current system is **not** primarily bottlenecked by missing frontier primitives —
it's bottlenecked by **chaining and model-assignment done by hand**, and by one genuine correctness gap
(self-verified fixes) that a conductor would close as a side effect. Build the conductor if the manual
relay is costing you focus; it's the correct, non-drifting version of your "one agent does it all"
instinct — *orchestrate separate agents, don't collapse them.*

But the reason the frontier patterns mostly don't transfer is the most useful thing on this page: you are
benchmarking a **learning** project against **shipping**-optimized workflows. Their objective is
throughput; yours is your own capability. Parallel fan-out and autonomous long-horizon loops maximize
laps-per-hour — and past the greenlight gate, every lap you don't personally think through is mastery you
don't gain. The frontier move *for your objective* is not more autonomy; it's the minimum orchestration
that keeps you at the one decision that teaches you something, and a scheduler pointed at `/learn`. The
toolbox can make the reps cheap. It cannot take them for you — and it *shouldn't* try to.
