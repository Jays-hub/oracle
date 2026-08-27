# CLAUDE.md — Platform Charter (the company)

This repo is **one company organized by capability layer** over a **common data store**. This file
is the thin platform charter: the shape of the whole, the standing orders that span every layer, and
the shared store. Individual layers carry their own governance; this file does not duplicate it.

> **Restructured 2026-08-14 to the shape decided in `docs/repo_architecture.md`.** The old
> `forecasting/` + `onramp/` peer split is gone — code now organizes by layer (§5.3), tenant is a
> partition key rather than a directory identity (§5.2), and the dependency direction is enforced by
> `.importlinter` instead of remembered. §9.3 ("does the peer split survive M5?") is answered by
> this file: it does not. Historical records (`docs/phase_decisions/`, `docs/progress_log.md`,
> `docs_archive/`) keep the old paths on purpose — they record what was true when written.

## The goal that orders everything (2026-08-13)

**Get this codebase to where it ingests a real POS export and a real stack of vendor invoices from a
real restaurant, and produces output honest enough to hand back to that operator.** Every phase is
measured against that, not against test count or model sophistication. Nothing here has ever seen a
real row: the engine runs on `ingest/simulate/`, and the web funnel accepts only a CSV the
operator reshaped by hand.

Capability sits in a **dependency stack**, and attempting a layer before its prerequisites exist
produces *confident, wrong output — worse than no output, because it gets trusted*:

| Layer | Contents | Where it lives here | State |
|---|---|---|---|
| **L0** Access | POS export/API, invoice capture | `ingest/capture/` | simulated / hand-shaped only |
| **L0.5** Recipe capture | Documented recipes + yields | `ingest/bom/` | **built, reusable** |
| **L1** Identity | Canonicalization, entity resolution, unit algebra, versioned item master | `identity/` | **empty package — the gap** |
| **L2** Derived measures | Plate cost, margin, theoretical vs. actual | `measures/` | built on an absent L1 |
| **L3** Decision models | Quantile forecasting, newsvendor, optimization | `decide/` (scored by `evaluate/`) | **built + dollar-gated (P0–P4), on simulated data** |
| **L4** Interface & habit | Prep lists, alerts, the operator surface | `surface/` | built (W0–W9) over L2; no prep-list surface yet |
| **L5** Institutionalization | SOPs, lineage, process mining | — | correctly deferred |

**The repo is strongest at L3 and weakest at L1 — the inversion of the dependency order.** Closing
that is the current work. The gap analysis, the five blockers with file-level evidence, and the R0–R6
build order: **`docs/real_data_readiness.md`** (read before planning any phase). The method behind it:
`docs/consulting_framework.md` (Parts 3–5) + `docs/learning_path.md`.

## Code organizes by layer, not by product (`docs/repo_architecture.md` §5.3)

| Dir | Layer | Contents |
|---|---|---|
| `ingest/` | L0 | `capture/` (invoice + seam upload), `bom/` (L0.5 recipe capture), `demand/` (raw→observed series), `simulate/` (the synthetic source) |
| `identity/` | L1 | `canonicalize.py`, `units.py` — today the whole of ER. The R2–R6 spec is `identity/__init__.py` |
| `measures/` | L2 | plate cost, contribution margin, the popularity×margin grid, price trends |
| `decide/` | L3 | features, point + quantile models, newsvendor |
| `surface/` | L4 | `web/` (the operator site), `report/`, `prep_sheet/`, `run.py` |
| `plays/` | ⊥ | §7.1 one-off analyses — read the store, emit a report, **never** a dependency |
| `evaluate/` | ⊥ | the truth-scoring harness: the **only** reader of the hidden oracle |
| `store/` `db/` `econ/` `schemas/` | — | layer-neutral leaves any layer may use |

**The arrows are checked, not remembered.** `.importlinter` carries four contracts —
`layer-direction`, `truth-firewall`, `plays-are-terminal`, `shared-modules-are-leaves` — and
`make import-lint` runs in CI. If a change needs a contract relaxed, that is the signal to re-home
the code, not to edit the contract.

**Two framings still matter, and neither is a directory any more.** The **engine** (the moat, the
*end*) is `decide/` + `evaluate/` + `ingest/demand|simulate/`, governed by `decide/CLAUDE.md`. The
**on-ramp** (the durable acquisition + capture bridge, the *means*) is `surface/` + `measures/` +
`ingest/capture|bom/`, governed by `surface/CLAUDE.md` and `docs/onramp_service.md`. The on-ramp
*function* is **not disposable** — there is no path onto the engine that doesn't cross some
instant-value bridge — while the current plate-cost *product* is provisional and should stay thin.
Elevating the on-ramp does **not** move the moat: defensibility still lives in `decide/`.

## The common data store (the seam — read `data/CONTRACT.md`)

`data/` is **platform infrastructure owned by no layer.** It is the interface between them, and it
holds no code:

- `data/raw/` — the messy "restaurant export," as received. `ingest/capture/` writes the captured
  legs; `ingest/simulate/` writes the synthetic dump. **The only thing models may read.**
- `data/canonical/` → `data/resolved/` → `data/marts/` — adapter output, then post-ER rows with
  entity ids assigned, then features and measures. **`resolved/` is the layer the pivot adds**;
  nothing produces it until R2.
- `data/runs/` — one immutable directory per execution, manifest + outputs. "Latest" is a pointer,
  never an overwrite (§5.4). **Not built yet (M2).**
- `data/_truth/` — hidden ground truth. Written **only** by `ingest/simulate/`, read **only** by
  `evaluate/`. **Never** a model input, **never** touched by any layer in the chain.

**Tenant is a partition key, not a directory identity (§5.2).** Single-tenant reads are a predicate;
all-tenant reads are the absence of one — which is what makes pooling free instead of a rewrite at
n=5. Isolation lives in the access layer (`store/__init__.py::tenant_raw_dir()`, W9's slug
validator), covered by tests once rather than per directory.

The authoritative who-writes-what + the raw/truth law: **`data/CONTRACT.md`**. Shared schemas every
layer validates against: **`schemas/`**. The direction for turning this folder into a queryable
common database (DuckDB over Parquet) and what that does to the firewall:
**`docs/common_base_reconciliation.md`** (a forward record for the session that builds the DB).

**One-way data flow:** `ingest/capture/` → `data/raw/` → `ingest/demand/` → `decide/`. Code coupling
runs strictly downward through the layers, and `.importlinter` is what says so.

## Standing orders that span EVERY layer

1. **Comprehension is a parallel track, not a gate.** Nothing about Jay's understanding blocks work:
   building is free and a phase's **review closes on the code** (findings, fixes, log entry) — no
   comprehension sign-off, no verbatim capture. Understanding is grown and re-checked over time on its
   own spaced-repetition track — the **`/learn`** command + **`comprehension-tutor`** subagent
   maintaining **`docs/mastery.md`** — which never blocks a build, review, merge, or phase close.
   Applies to every layer alike. Defined in `.claude/rules/00-process.md`; reasoning in
   `docs/overview_and_method.md`. (The old review-exit gate was retired 2026-07-01.)
2. **Anti-Drift Standing Order.** The highest-value work is barely ML (the newsvendor reframe + the
   data-access grind). Name the drift if a session reaches for sophistication before the simpler,
   higher-dollar step exists — **including drift *into* the on-ramp**, which is more buildable and
   more gratifying than the moat and so a comfortable place to hide. **As of the 2026-08-13 pivot the
   sharpest form of this drift is deepening L3 on simulated data** (more exogenous signal, more model)
   **while L1 stays an empty package.** Modeling is the comfortable place to hide *from* the data
   grind, exactly as the on-ramp was the comfortable place to hide from the moat.
3. **Dollars, not accuracy.** "Done" = beating the prior baseline in realized cost
   `Σ(Co·overage + Cu·underage)`, never MAPE/RMSE. (Engine specifics in `decide/CLAUDE.md`.)
   Two corollaries from the pivot: the baseline to beat is the **operator's own par sheet**, not a
   naive mean (`docs/discovery/2026-08-12_wes.md` §8); and ingestion progress is measured in **dollars
   of COGS resolved, not records resolved** — record counts reward long-tail work that doesn't matter
   and hide gaps in the top-20 items carrying ~70% of spend.
4. **Respect the prerequisite order (`docs/real_data_readiness.md` §1).** Do not build a layer whose
   prerequisites are absent. Within ingestion the orderings are forced, not stylistic: grain before
   build, deterministic before probabilistic, blocking-recall audit before matcher tuning, calibration
   before thresholding, clustering after pairing (never pairing alone), temporal validity before any
   history is trusted. If a plan inverts one of these, say so before writing code. The *code-level*
   half of this order is now mechanical: `.importlinter`'s `layer-direction` contract fails the build
   on an upward import, so what a session still has to judge is the **sequencing**, not the wiring.
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
├── .claude/rules/            # 00 process (platform gate) · 01 ingestion (the raw/truth store law)
│                             #   · 02 features · 03 training · 04 deployment (engine rules; paths → ingest/** decide/** evaluate/**)
│                             #   · 05 fullstack-arch · 06 frontend-ux · 07 backend-api (web rules; paths → surface/** measures/**)
├── .importlinter             # the layer arrows, machine-checked (make import-lint)
├── docs/                     # platform encyclopedia: method, strategy, discovery + common-base record
│                             #   · real_data_readiness.md = THE CURRENT BUILD DOC (L0–L5 gap analysis, R0–R6 order)
│                             #   · repo_architecture.md   = why the repo is shaped this way (this restructure's source)
│                             #   · consulting_framework.md + learning_path.md = the method behind the pivot (source docs)
│                             #   · engine/ = engine theory · onramp/ = on-ramp product docs
│                             #   · agentic_workflow/ = the agent workflow's own record (read ONLY when changing .claude/** or workflow efficiency)
├── data/                     # ⟵ THE COMMON STORE (no code): raw/ canonical/ resolved/ marts/ runs/ _truth/ + CONTRACT.md
├── config/                   # shared generative + model config (YAML)
├── schemas/                  # the store's schemas, validated by every layer (pydantic/pandera)
├── ingest/                   # L0  capture/ bom/ demand/ simulate/
├── identity/                 # L1  canonicalize.py units.py (+ the R2–R6 spec in __init__.py)
├── measures/                 # L2  grid.py pricing/ costing/ insights/
├── decide/                   # L3  features/ models/ newsvendor.py   (+ CLAUDE.md = engine governance)
├── surface/                  # L4  web/ report/ prep_sheet/ auth/ email/ run.py  (+ CLAUDE.md = on-ramp governance)
├── plays/                    # ⊥   one-off analyses; nothing may import these
├── evaluate/                 # ⊥   truth-scoring harness — the only reader of the hidden oracle
├── store/ db/ econ/          # layer-neutral leaves: store paths · app database · newsvendor economics
├── tests/                    # platform/ ingest/ identity/ measures/ decide/ evaluate/ store/ surface/
└── scripts/ migrations/ examples/ notebooks/
```

## Current status
The **on-ramp** (`surface/` + `measures/` + `ingest/capture|bom/`) has its **Phase-0 tool built and
running**: BOM + plate-cost compute, the popularity×margin grid, and a schema-validated export of the
sales + BOM legs into the store (`data/raw/`). Shared schemas (`schemas/`) and a test suite —
including the firewall boundary tests — are in place. The **forecasting engine** (`decide/` +
`evaluate/` + `ingest/demand|simulate/`) has **P0–P4 built**: the
decision frame, the simulated-data generator + baselines + backtest harness, the data-cleaning +
feature pipeline + point model, censored-demand unconstraining, and the distribution + newsvendor turn
(a calibrated quantile model converted to a prep quantity — the product in miniature). See
`decide/CLAUDE.md` Current status for detail. The common store exists with its contract.

**Storage decided (2026-06-25): DuckDB-over-Parquet** is the shared store
(`docs/common_base_reconciliation.md`) — the `data/raw/**` files stay the firewall, DuckDB is the
query layer over them. Standing up the query layer is a phase whose review closes on code merit like any
other: **decided, not yet built.**

**On-ramp website (built W0–W9):** the client-facing site is up — capture funnel, real identity,
production hosting, the public storefront, and multi-tenancy across the seam. North-star vision:
`docs/onramp/website_vision.md`; governance: the full-stack rules `.claude/rules/05–07`
(paths → `surface/**`, `measures/**`). Its durable parts are the capture funnel, storage, identity, and the
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
