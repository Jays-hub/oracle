# CLAUDE.md — Platform Charter (the company)

This repo is **one company with two durable parts** feeding a **common data store**. This file is
the thin platform charter: the shape of the whole, the standing orders that span both parts, and the
shared seam. Each part has its own governance; this file does not duplicate it.

## The two parts (peers, not parent/child)

- **`forecasting/` — the core engine.** Prep-demand forecasting sold under a waste framing: a daily
  prep sheet. The moat and the *end*. Governed by `forecasting/CLAUDE.md` + `.claude/rules/`.
- **`onramp/` — the on-ramp service.** The durable acquisition + data-capture bridge that delivers
  instant, dollar-legible value and, in the same act, captures the data the engine needs. The
  *means*. Governed by `onramp/README.md`; its current implementation is `onramp/plate_cost/`
  (`onramp/plate_cost/CLAUDE.md`).

**Durable function vs. provisional product.** The on-ramp *function* is **not disposable** — there is
no path onto the engine that doesn't cross some instant-value bridge. The current *product*
(plate-cost) **is** provisional: discovery may keep, reshape, or replace it. Build the product thin;
treat the slot as first-class. (`onramp/README.md` carries this in full.) Elevating the on-ramp's
importance does **not** move the moat — defensibility still lives in `forecasting/`.

## The common data store (the seam — read `data/CONTRACT.md`)

`data/` is **platform infrastructure owned by neither code peer.** It is the single interface between
the two parts:

- `data/raw/` — the messy "restaurant export." The on-ramp **writes** its data legs here; the engine
  **reads** model inputs **only** from here.
- `data/_truth/` — hidden ground truth. Written **only** by `forecasting/src/simulate/`, read **only**
  by `forecasting/src/evaluate/`. **Never** a model input, **never** touched by `onramp/`.
- `data/interim/`, `data/processed/` — engine-internal working layers.

The authoritative who-writes-what + the raw/truth law: **`data/CONTRACT.md`**. Shared schemas both
peers validate against: **`schemas/`**. The direction for turning this folder into a queryable
common database (DuckDB over Parquet) and what that does to the raw/truth firewall:
**`docs/common_base_reconciliation.md`** (a forward record for the session that builds the DB).

**One-way data flow, no code coupling:** `onramp/` → `data/raw/` → `forecasting/`. Neither peer may
import the other; the only thing they share is the seam.

## Standing orders that span BOTH parts

1. **Comprehension is a parallel track, not a gate.** Nothing about Jay's understanding blocks work:
   building is free and a phase's **review closes on the code** (findings, fixes, log entry) — no
   comprehension sign-off, no verbatim capture. Understanding is grown and re-checked over time on its
   own spaced-repetition track — the **`/learn`** command + **`comprehension-tutor`** subagent
   maintaining **`docs/mastery.md`** — which never blocks a build, review, merge, or phase close.
   Applies to engine and on-ramp alike. Defined in `.claude/rules/00-process.md`; reasoning in
   `docs/overview_and_method.md`. (The old review-exit gate was retired 2026-07-01.)
2. **Anti-Drift Standing Order.** The highest-value work is barely ML (the newsvendor reframe + the
   data-access grind). Name the drift if a session reaches for sophistication before the simpler,
   higher-dollar step exists — **including drift *into* the on-ramp**, which is more buildable and
   more gratifying than the moat and so a comfortable place to hide.
3. **Dollars, not accuracy.** "Done" = beating the prior baseline in realized cost
   `Σ(Co·overage + Cu·underage)`, never MAPE/RMSE. (Engine specifics in `forecasting/CLAUDE.md`.)

## Repo structure
```
.
├── CLAUDE.md                 # this file — platform charter
├── README.md                 # platform overview + docs index
├── .claude/rules/            # 00 process (platform gate) · 01 ingestion (the raw/truth seam law)
│                             #   · 02 features · 03 training · 04 deployment (engine rules; paths → forecasting/src/**)
│                             #   · 05 fullstack-arch · 06 frontend-ux · 07 backend-api (on-ramp web rules; paths → onramp/**)
├── docs/                     # platform encyclopedia: method, strategy, discovery + common-base record
│                             #   · agentic_workflow/ = the agent workflow's own record (read ONLY when changing .claude/** or workflow efficiency)
├── data/                     # ⟵ THE COMMON STORE (platform-owned): raw/ interim/ processed/ _truth/ + CONTRACT.md
├── config/                   # shared generative + model config (YAML)
├── schemas/                  # shared schemas both peers import (pydantic/pandera)
├── forecasting/              # PEER 1 — the core engine (CLAUDE.md, docs/ = engine theory, src/, notebooks/, tests/)
└── onramp/                   # PEER 2 — the durable on-ramp service (README.md)
    └── plate_cost/           #   current implementation (CLAUDE.md, docs/, src/)
```

## Current status
The **on-ramp** (`onramp/plate_cost/`) has its **Phase-0 tool built and running**: BOM + plate-cost
compute, the popularity×margin grid, and a schema-validated export of the sales + BOM legs into the
seam (`data/raw/`). Shared seam schemas (`schemas/`) and a test suite — including the cross-module
boundary test — are in place. The **forecasting engine** (`forecasting/`) has **P0–P2 built**: the
decision frame, the simulated-data generator + baselines + backtest harness, and the data-cleaning +
feature pipeline + point model. See `forecasting/CLAUDE.md` Current status for detail. The common store
exists with its contract.

**Storage decided (2026-06-25): DuckDB-over-Parquet** is the shared store
(`docs/common_base_reconciliation.md`) — the `data/raw/**` files stay the firewall, DuckDB is the
query layer over them. Standing up the query layer is a phase whose review closes on code merit like any
other: **decided, not yet built.**

**On-ramp website (next surface):** a clean, simple client-facing website is the on-ramp's planned
face. North-star vision: `onramp/plate_cost/docs/website_vision.md`; governance: the new full-stack
rules `.claude/rules/05–07` (paths → `onramp/**`). The build stays thin and phased (W0 = a read-only
reveal over existing `data/raw/`); the durable parts are the capture funnel, storage, and transparency
story, while the plate-cost-specific views are provisional. This is on-ramp *function*, not drift —
but elevating its polish still does not move the moat (Anti-Drift), which lives in `forecasting/`.

Simulation and the on-ramp's later phases remain pending real customer discovery — treat all "Marco"
numbers (`docs/discovery_and_validation`) as plausible placeholders, not validated facts.
