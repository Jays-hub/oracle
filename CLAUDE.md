# CLAUDE.md — Platform Charter (the company)

This repo is **one company with two durable parts** feeding a **common data store**. This file is
the thin platform charter: the shape of the whole, the standing orders that span both parts, and the
shared seam. Each part has its own governance; this file does not duplicate it.

## The goal that orders everything (2026-08-13)

**Get this codebase to where it ingests a real POS export and a real stack of vendor invoices from a
real restaurant, and produces output honest enough to hand back to that operator.** Every phase is
measured against that, not against test count or model sophistication. Nothing here has ever seen a
real row: the engine runs on `forecasting/src/simulate/`, and the web funnel accepts only a CSV the
operator reshaped by hand.

Capability sits in a **dependency stack**, and attempting a layer before its prerequisites exist
produces *confident, wrong output — worse than no output, because it gets trusted*:

| Layer | Contents | Where it lives here | State |
|---|---|---|---|
| **L0** Access | POS export/API, invoice capture | `onramp/plate_cost/src/capture/` | simulated / hand-shaped only |
| **L0.5** Recipe capture | Documented recipes + yields | `onramp/plate_cost/src/bom/` | **built, reusable** |
| **L1** Identity | Canonicalization, entity resolution, unit algebra, versioned item master | `onramp/plate_cost/src/ingestion/` | **empty package — the gap** |
| **L2** Derived measures | Plate cost, margin, theoretical vs. actual | `onramp/plate_cost/src/{pricing,costing,report}/` | built on an absent L1 |
| **L3** Decision models | Quantile forecasting, newsvendor, optimization | `forecasting/` | **built + dollar-gated (P0–P4), on simulated data** |
| **L4** Interface & habit | Prep lists, alerts, the operator surface | `onramp/plate_cost/web/` | built (W0–W9) over L2; no prep-list surface yet |
| **L5** Institutionalization | SOPs, lineage, process mining | — | correctly deferred |

**The repo is strongest at L3 and weakest at L1 — the inversion of the dependency order.** Closing
that is the current work. The gap analysis, the five blockers with file-level evidence, and the R0–R6
build order: **`docs/real_data_readiness.md`** (read before planning any phase). The method behind it:
`docs/consulting_framework.md` (Parts 3–5) + `docs/learning_path.md`.

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
   more gratifying than the moat and so a comfortable place to hide. **As of the 2026-08-13 pivot the
   sharpest form of this drift is deepening L3 on simulated data** (more exogenous signal, more model)
   **while L1 stays an empty package.** Modeling is the comfortable place to hide *from* the data
   grind, exactly as the on-ramp was the comfortable place to hide from the moat.
3. **Dollars, not accuracy.** "Done" = beating the prior baseline in realized cost
   `Σ(Co·overage + Cu·underage)`, never MAPE/RMSE. (Engine specifics in `forecasting/CLAUDE.md`.)
   Two corollaries from the pivot: the baseline to beat is the **operator's own par sheet**, not a
   naive mean (`docs/discovery/2026-08-12_wes.md` §8); and ingestion progress is measured in **dollars
   of COGS resolved, not records resolved** — record counts reward long-tail work that doesn't matter
   and hide gaps in the top-20 items carrying ~70% of spend.
4. **Respect the prerequisite order (`docs/real_data_readiness.md` §1).** Do not build a layer whose
   prerequisites are absent. Within ingestion the orderings are forced, not stylistic: grain before
   build, deterministic before probabilistic, blocking-recall audit before matcher tuning, calibration
   before thresholding, clustering after pairing (never pairing alone), temporal validity before any
   history is trusted. If a plan inverts one of these, say so before writing code.
5. **Never emit a number whose lineage you haven't validated.** The failure that ends an engagement is
   not a mediocre model — it's a confident figure resting on a bad unit conversion or a false merge.
   Two named guards: **bias entity decisions toward splits** (a false merge corrupts aggregates
   invisibly and is often irreversible; a false split is visible and recoverable), and **no person-level
   analysis** — void/comp by employee, server check-average — without exposure adjustment *and*
   multiple-comparison (FDR) control. Naive versions accuse innocent people at near-certain rates.

## Repo structure
```
.
├── CLAUDE.md                 # this file — platform charter
├── README.md                 # platform overview + docs index
├── .claude/rules/            # 00 process (platform gate) · 01 ingestion (the raw/truth seam law)
│                             #   · 02 features · 03 training · 04 deployment (engine rules; paths → forecasting/src/**)
│                             #   · 05 fullstack-arch · 06 frontend-ux · 07 backend-api (on-ramp web rules; paths → onramp/**)
├── docs/                     # platform encyclopedia: method, strategy, discovery + common-base record
│                             #   · real_data_readiness.md = THE CURRENT BUILD DOC (L0–L5 gap analysis, R0–R6 order)
│                             #   · consulting_framework.md + learning_path.md = the method behind the pivot (source docs)
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
boundary test — are in place. The **forecasting engine** (`forecasting/`) has **P0–P4 built**: the
decision frame, the simulated-data generator + baselines + backtest harness, the data-cleaning +
feature pipeline + point model, censored-demand unconstraining, and the distribution + newsvendor turn
(a calibrated quantile model converted to a prep quantity — the product in miniature). See
`forecasting/CLAUDE.md` Current status for detail. The common store exists with its contract.

**Storage decided (2026-06-25): DuckDB-over-Parquet** is the shared store
(`docs/common_base_reconciliation.md`) — the `data/raw/**` files stay the firewall, DuckDB is the
query layer over them. Standing up the query layer is a phase whose review closes on code merit like any
other: **decided, not yet built.**

**On-ramp website (built W0–W9):** the client-facing site is up — capture funnel, real identity,
production hosting, the public storefront, and multi-tenancy across the seam. North-star vision:
`onramp/plate_cost/docs/website_vision.md`; governance: the full-stack rules `.claude/rules/05–07`
(paths → `onramp/**`). Its durable parts are the capture funnel, storage, identity, and the
transparency story; the plate-cost-specific views stay provisional. In stack terms it is **L4 serving
L2 views over an absent L1** — the prep-list surface L3 needs does not exist yet.

**Pivot (2026-08-13) — entity resolution first, real data as the goal.** The approach moved from
"ship a forecasting product behind an on-ramp product" to "**progress this codebase until it ingests
real POS + invoice data and returns real-world feedback**," starting at the identity layer and
crossing non-CS ground (merchant processing, contract audits) that buys the access. This does **not**
retire the engine — `docs/consulting_framework.md` §7.8.2 names item-level quantile forecasts at
newsvendor-derived service levels as the one piece that stays defensible, and P0–P4 already built it.
It reorders what comes next: **R0–R6 (`docs/real_data_readiness.md` §4) sit before engine P5 and
on-ramp W10.** Five blockers stand between here and a real export — no source adapters, a sales leg at
the wrong grain to feed any forecast, identity as `casefold()`, no pack-notation unit algebra, and a
seam whose reader never reads what the writer writes. All five are evidenced with file references in
`docs/real_data_readiness.md` §2. The buy-vs-build fork for the matching stack (§3) is deliberately
left open until R0 puts a real export and a real invoice stack on disk.

Simulation and the on-ramp's later phases remain pending real customer discovery — treat all "Marco"
numbers (`docs/discovery/discovery_and_validation`) as plausible placeholders, not validated facts.
Two real operator interviews now exist (`docs/discovery/`), and their findings converge with the
framework independently: the cold-start problem, and the operator's **par sheet** as the real baseline.
