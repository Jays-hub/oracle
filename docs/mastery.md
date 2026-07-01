# mastery.md — the comprehension ledger (parallel track, not a gate)

This file is the **single source of truth for what Jay actually understands** about this codebase.
It is maintained by the `/learn` command and its `comprehension-tutor` subagent, and by nobody else's
self-certification. It is a **parallel practice track**: it runs on its own cadence and **never gates a
build, a review, or a phase close.** Reviews close on code quality; comprehension is trained here,
continuously, by spaced repetition.

> **Why this replaced the old gate.** Comprehension used to sit on the *exit* of every phase review —
> a phase couldn't close until Jay explained it, captured verbatim in a `Pn.md`. That coupled two
> unlike clocks: shipping (fast, per-phase) and understanding (slow, cumulative, needs re-testing over
> time). This ledger decouples them. Building and review proceed on code merit; understanding is grown
> and *re-checked on a rolling basis* here, so a concept learned in P1 is re-surfaced in P4 to confirm
> it actually stuck.

---

## The mastery scale (and its spaced-repetition interval)

Each topic carries a **level**. The level sets **when the tutor will next quiz it** — higher mastery =
longer interval before it resurfaces (classic spaced repetition; getting an answer right pushes the
topic further out, getting it wrong pulls it back in).

| Level | Name | Meaning | Re-test interval |
|-------|------|---------|------------------|
| **L0** | Unseen | Seeded from the code/roadmap, never quizzed | next session |
| **L1** | Shaky | Answered, but gaps or wrong framing | ~1 day (next session) |
| **L2** | Familiar | Correct with prompting; can't yet teach it | ~3 days |
| **L3** | Solid | Correct unprompted, in own words, across all three domains | ~7 days |
| **L4** | Mastered | Explains *and* connects it to the why-here-why-now and the failure mode | ~21 days |

**Setting the level.** The tutor sets a topic's level to **match the quality the answer actually
demonstrates**, per the descriptions above — not a fixed step. From **L0 (Unseen)** a strong first
answer can land directly at L2 or L3; L0 means "not yet tested," not "known to be weak." For a topic
already at a level, treat **±1 as the normal move** (a clean answer up one, a shaky/wrong one down one,
floor L1 once seen) and reserve bigger jumps for answers that clearly overshoot or collapse. `Next due`
is always recomputed from the *new* level's interval. The tutor decides from the answer's quality across
the three domains below; it never rubber-stamps.

**The three domains a topic is tested across** (an answer describable in only one domain is
half-understood):
- **`code`** — software/coding craft & hygiene (the *how it's built well*).
- **`ds`** — data-science / statistical concept (the *what technique and why it's right*).
- **`seq`** — sequencing / why-this-was-built-when (the *dependency that placed it here*).

There is **no "say it to a chef" one-liner** in this system. It was retired with the gate.

---

## How a `/learn` session works (the rolling review)

1. The tutor reads this ledger, picks the topics whose **`Next due` ≤ today** (plus any L0), and
   caps the batch (~4–6 topics) so a session stays short.
2. For each, it generates a question **grounded in the actual code/commit** — testing technique
   understanding, *why this progress was made at that point in the sequence*, and the coding
   techniques/hygiene used.
3. Jay answers in his own words (relayed through the main thread — the subagent is one-shot).
4. The tutor grades each answer across the three domains, updates the topic's **Level**, **Last
   reviewed**, and **Next due**, and appends a one-line note. It writes the updated table back here.

If no topic is due and no L0 remains, the tutor says so rather than inventing filler.

---

## Topic ledger

Seeded from P0–P2 (the built engine work) at **L0 / Unseen**. `Origin` points at the phase/commit the
topic comes from. `Next due` = `today` for all L0 seeds until first quizzed.

| # | Topic | Domain(s) | Origin | Level | Last reviewed | Next due | Notes |
|---|-------|-----------|--------|-------|---------------|----------|-------|
| 1 | The dollar objective `Σ(Co·overage + Cu·underage)` — why cost, not MAPE/RMSE | ds, seq | P0 | L0 | — | due | seed |
| 2 | Critical ratio `q* = Cu/(Co+Cu)` — what it is and why it sets the prep target | ds | P0 | L0 | — | due | seed |
| 3 | Why P0 (decision frame + measuring stick) had to come *before* any model | seq | P0 | L0 | — | due | seed |
| 4 | The head-chef gate: schema-validated `load_items()` config load | code | P0 | L0 | — | due | seed |
| 5 | The three honest baselines (seasonal-naive / same-weekday rolling / Croston) and why a floor first | ds, seq | P1 | L0 | — | due | seed |
| 6 | Rolling-origin (walk-forward) cross-validation vs. a random split | ds | P1 | L0 | — | due | seed |
| 7 | The raw/_truth firewall — who writes/reads each, and why truth is never a model input | code, seq | P1 | L0 | — | due | seed |
| 8 | Ground-truth generator: why simulate true demand at all (verification you can't get from real data) | ds, seq | P1 | L0 | — | due | seed |
| 9 | Censored demand: `sold == capacity` days are stockouts, not true demand | ds | P1→P2 | L0 | — | due | seed |
| 10 | The leakage canary + `.shift(1)` — how a lag feature avoids using the future | code, ds | P2 | L0 | — | due | seed |
| 11 | Fit the feature pipeline on train only (no fit on the full frame) — leakage hygiene | code | P2 | L0 | — | due | seed |
| 12 | Menu-era tagging — why pollution stripping precedes the point model | ds, seq | P2 | L0 | — | due | seed |
| 13 | GBM with Poisson/Tweedie objective — why that family for count/low-volume demand | ds | P2 | L0 | — | due | seed |
| 14 | `random_state=42` / reproducibility & `make test`/`make lint` env discipline | code | P0–P2 | L0 | — | due | seed |

---

## Change log

- **2026-07-01** — File created. Comprehension moved off the review exit-gate onto this parallel
  spaced-repetition track (`/learn` + `comprehension-tutor`). Seeded 14 topics from P0–P2 at L0.
