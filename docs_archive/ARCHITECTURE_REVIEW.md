# Architecture Review — Two-Product Monorepo

> **DECISION (2026-06-22): Option A adopted, with the on-ramp reframed as a durable peer.** This
> review recommended Option B; Jay chose **Option A** and corrected the framing — the on-ramp
> *function* is durable (not disposable); `plate_cost` is its provisional implementation. The repo
> was restructured accordingly. This file is kept as the *analysis record* that led to the decision;
> for the current structure see `CLAUDE.md` (platform charter), `onramp/README.md` (durable on-ramp
> mandate), `data/CONTRACT.md` (the seam), and `docs/common_base_reconciliation.md` (the common-DB
> decision log). Where this review's §3/§5 describe Option B as the recommendation, read them as
> superseded.

*Reviewer pass over `restaurant-dev/` as of 2026-06-22. Scope: directory organization for the
two-product startup (forecasting engine + plate-cost on-ramp) sharing a common data store. This is
an advisory document, not a build step — nothing here is executed without your sign-off.*

---

## TL;DR

Your structure is **80% right and the remaining 20% is one real issue, not ten.** The real issue:
**the shared data store — your "common database" — is the architectural seam of the whole company,
but right now it's an implicit folder owned by the forecasting engine that the on-ramp reaches *up*
into via `../data/raw/`.** The seam is described in prose in three different files and enforced
nowhere. Everything else (the asymmetry between core and on-ramp, the per-module `CLAUDE.md`, the
rules layer) is sound and should be kept.

My recommendation is **deliberately small**: make the shared seam a first-class, neither-module-owns-it
**data contract**, fix two naming/ownership ambiguities, and *stop there*. Do **not** do a big
symmetric reorg that promotes the disposable rail to a co-equal top-level peer — that would
contradict your own strategy docs and is exactly the kind of intellectually-tidy work your
Anti-Drift Standing Order exists to catch. A directory reorg moves zero dollars of newsvendor cost.

---

## 1. What you actually have right now

Read honestly, the repo is at **Phase 0 — almost nothing is built**, and that is the most important
fact for this review because it makes structural change cheap *and* low-urgency at the same time.

> **Update (2026-06-25):** this snapshot was accurate at the 2026-06-22 review. Since then the
> on-ramp's plate-cost **Phase 0 has been built and runs** (BOM + plate-cost + margin grid + a
> schema-validated seam export + a test suite); the forecasting engine remains empty. The live
> status lives in `CLAUDE.md` — this file is kept as the dated analysis record.

**Exists on disk:**

- Governance: root `CLAUDE.md`, `.claude/rules/00–04`, `plate_cost/CLAUDE.md`.
- Docs: `docs/overview_and_method–07` (forecasting encyclopedia), `plate_cost/docs/overview_and_method`.
- Code: only `plate_cost/src/{bom,ingestion,pricing,report}/__init__.py` — **empty stubs.**
- `README.md`, `.gitignore`.

**Described in `CLAUDE.md` but does NOT exist yet:**

- The entire forecasting engine tree: `src/{simulate,data,features,models,decision,evaluate,report}/`.
- The data tree: `data/{raw,interim,processed,_truth}/`.
- `config/`, `notebooks/`, `tests/`.

So the "architecture" today is a **documented intention** plus a half-scaffolded on-ramp. This has a
clean implication: **you can fix the skeleton now at near-zero cost** (there is no code to migrate),
but you should also resist gold-plating it, because none of it has earned its complexity yet.

---

## 2. The structural issues, in priority order

### Issue 1 (the only big one) — the common database is an implicit, asymmetrically-owned seam

The root `CLAUDE.md` puts `data/` *inside* the forecasting engine's repo root and treats it as the
engine's territory. `plate_cost` then writes into it from below with `../data/raw/`. Three problems
fall out of this single design choice:

- **Ownership is wrong-shaped.** The data store is shared infrastructure that *both* products depend
  on. Right now one product owns it and the other trespasses upward. The `../` relative path is the
  tell — a module reaching outside its own root to write someone else's folder is a coupling smell.
- **The contract is triplicated.** The "who writes what / raw-vs-truth law" is described in root
  `CLAUDE.md` ("Shared data boundary"), in `plate_cost/CLAUDE.md` ("Scope boundary"), and again in
  `plate_cost/docs/overview_and_method` ("Data boundary with the forecasting engine"). Three copies of one contract
  drift apart the moment one is edited. There is no single source of truth for the single most
  important interface in the company.
- **It's enforced nowhere.** Your rules already call for an import-linter boundary test and a runtime
  path assertion *inside* the engine (`01-data-ingestion.md`). But the **cross-module** guarantees —
  "`plate_cost` never imports `../src/`", "`plate_cost` never reads `_truth/`" — have no home and no
  test. They live only as prose promises.

### Issue 2 — the root `CLAUDE.md` wears two hats

The root file simultaneously declares "**What this project is**: a forecasting engine…" *and* acts
as the umbrella over a second product. That conflation was harmless with one product; with two it
means platform-level concerns (the two-product strategy, the shared contract, cross-module drift)
and engine-level concerns (newsvendor, phases P0–P8, the rules) are tangled in one file. A reader
can't tell which statements bind the *company* and which bind the *forecasting module*.

### Issue 3 — "common database" vs. a folder of CSVs

You describe the shared store as a "common database," but the design is file-based
(`data/raw/*.csv`), while `plate_cost`'s stack note says "SQLite or DuckDB for local price history."
These aren't contradictory, but the mismatch is unresolved and it changes how the raw-vs-truth law
gets enforced (a folder boundary vs. a schema/connection boundary). Worth deciding on purpose rather
than by drift. (Reconciled in §4.)

### Issue 4 — smaller ownership ambiguities

- **`config/`** is referenced by the engine (`config/sim.yaml`, `Cu`/`Co` for the dollar metric)
  but also conceptually shared (plate-cost will want seed-price and yield config). Who owns it?
- **`tests/`** is described at root for the engine; `plate_cost` has no `tests/` dir; and the
  *cross-module contract test* has nowhere to live.
- **`config/` for plate_cost** (seed prices, yield tables) isn't placed anywhere yet.

None of these are urgent, but they're cheap to settle now while the tree is empty.

---

## 3. Three topologies (scored against *your own* principles)

I evaluated three end-states. The scoring axis that matters most here is not "what does a textbook
monorepo look like" — it's your stated values: **the on-ramp is disposable and must not be
dignified into half the company** (`plate_cost/CLAUDE.md` drift callout #3, the "chef's knife"
principle), and **structural elegance must not outrank dollar-moving work** (Anti-Drift Standing
Order).

### Option A — Symmetric platform (promote both to peers)

```
restaurant-platform/
├── CLAUDE.md            # thin platform charter
├── docs/                # company strategy only
├── shared/  (data + contracts + config)
├── forecasting/         # the engine, demoted into a subdir
└── plate_cost/          # the on-ramp, now a co-equal peer
```

*Pro:* textbook-clean separation; the shared store is owned by neither code module; symmetric.
*Con:* **over-dignifies the disposable rail** — making `plate_cost/` a top-level peer of
`forecasting/` visually signals "two co-equal products," which is precisely the framing your strategy
docs fight ("the on-ramp is the means; the prep engine is the end"). Also the biggest churn: every
`src/decision/ingredients.py` reference and every `../docs/` reference must be rewritten. For a repo
with no engine code yet, that's churn spent on docs, not product.

### Option B — Asymmetric, minimal (forecasting stays the host; formalize only the seam) ✅

```
restaurant-dev/                 # root = the PLATFORM (re-framed), engine still lives here
├── CLAUDE.md                   # gains a short "Platform vs. this module" header; rest unchanged
├── docs/                       # unchanged
├── data/
│   ├── raw/  interim/  processed/  _truth/
│   └── CONTRACT.md             # NEW: the single source of truth for the shared seam
├── contracts/  (or data/schemas/)   # NEW: pydantic/pandera schemas both modules import
├── config/                     # engine + sim config (shared store gets its own sub-namespace)
├── src/…                       # engine, unchanged location
├── tests/
│   └── test_module_boundaries.py    # NEW: the cross-module contract test lives here
└── plate_cost/                 # unchanged; keeps writing ../data/raw/, now against a real contract
```

*Pro:* near-zero churn (no code moves); keeps the strategic asymmetry intact; fixes the *actual*
problem (the seam) by promoting it from prose to a contract + a test. *Con:* the root file still
nominally hosts both the platform and the engine — but a clear header section resolves the ambiguity
without a move.

### Option C — Two repos

*Reject.* They share a data contract, a strategy, and the entire premise is *one build feeding two
products*. Splitting fractures the seam and doubles governance. Mentioned only to close it.

---

## 4. Reconciling "common database" — files vs. a real DB

The cleanest resolution dissolves the tension instead of picking a side:

**Use DuckDB *over Parquet/CSV files in `data/`*.** DuckDB queries Parquet and CSV in place, so the
"folder of files" and the "common database" become the *same artifact viewed two ways*: the files
are the durable, git-diffable, contract-checkable store; DuckDB is the query layer both modules open
against it. You get a real SQL surface without a server, without ETL, and without giving up the
file-level raw-vs-truth boundary your whole verification discipline depends on.

This matters because the raw-vs-truth law has to survive the move to "a database":

- **As folders** (today): the law is "models read only `data/raw/`", enforced by a path assertion +
  import-linter. Simple and visible.
- **As one real RDBMS**: the law becomes "models connect only to the `raw` schema; only
  `src/evaluate` may touch `truth`" — enforced by **separate schemas/roles/connections**, not
  folders. More machinery, easy to get subtly wrong.
- **DuckDB-over-Parquet** keeps the *folder* boundary (so the cheap, legible enforcement still works)
  while giving you the *query* ergonomics you wanted from "a database." Best of both, and it's in
  your stated stack already.

**What the seam actually carries** (the contract `plate_cost` writes and the engine reads):

| File in `data/raw/` | Written by | Read by | The data leg |
|---|---|---|---|
| `sales_export.csv` / `pos_sales.*` | plate_cost (onboarding) → later POS feed | engine | sales history |
| `bom.csv` (RecipeLine) | plate_cost (recipe sitdown) | engine (`decision/ingredients.py`) | BOM |
| `price_observations.csv` | plate_cost (invoice ingestion) | engine (`decision/waste.py`) | invoices/prices |
| `eightysix_log.csv` | the separate 86-tap habit (neither module) | engine | stockouts/censoring |

That table **is** the contract. It belongs in one place (`data/CONTRACT.md`), referenced by both
`CLAUDE.md`s instead of re-described in each.

---

## 5. Recommendation

**Adopt Option B now. Keep Option A in your back pocket as a *triggered* migration** — execute it
only if `plate_cost` ever stops being disposable (i.e., if discovery says the margin tool is itself a
sellable product). Per your own docs, that shouldn't happen; so plan for it, don't pre-build it.

Concretely, the minimal high-value changes:

1. **Create `data/CONTRACT.md`** — the single source of truth for the shared seam: the table in §4,
   the raw-vs-truth law, the one-way data-flow rule (plate_cost → `data/raw/` → engine), and the
   "only `src/evaluate` reads `_truth/`, only `src/simulate` writes it" funnel. Then **delete the
   duplicated prose** from the three CLAUDE/doc locations and replace each with a one-line pointer to
   the contract.

2. **Add a short "Platform vs. this module" header to the root `CLAUDE.md`** — two sentences naming
   that the root governs *both* the company-level concerns *and* the forecasting engine, and that
   `plate_cost/CLAUDE.md` governs the on-ramp. No file moves. Resolves the two-hats ambiguity cheaply.

3. **Introduce `contracts/` (or `data/schemas/`)** — the *one* place a shared schema (the BOM /
   RecipeLine and PriceObservation shapes, as pydantic or pandera) is defined, so both modules
   validate against the same definition rather than two hand-kept copies. This is the structural
   teeth behind the contract doc.

4. **Give the cross-module boundary a test home** — `tests/test_module_boundaries.py` asserting (a)
   `plate_cost` never imports from `src/`, (b) nothing in `plate_cost` references a `_truth` path,
   (c) the existing engine-internal import-linter rule. Wire it into CI beside the leakage canary.
   This converts three prose promises into one failing build when violated.

5. **Decide the DB question on purpose** — adopt DuckDB-over-Parquet as the shared query layer, note
   it in `data/CONTRACT.md`, and keep the folder boundary as the enforcement surface (§4).

6. **Settle the small ownerships** — `config/` stays engine+sim and gains a `config/plate_cost/`
   sub-namespace for seed-price/yield config; `plate_cost/tests/` gets created when the first
   plate-cost code does. Don't pre-create empty trees beyond what a step needs.

**What NOT to do:** don't move `src/` into a `forecasting/` subdir, don't promote `plate_cost` to a
top-level peer, don't stand up a real RDBMS, don't pre-scaffold the full engine tree before Phase 1
needs it. Each of those is tidiness the project hasn't earned.

---

## 6. The drift check (holding myself to your standing order)

Your Anti-Drift Standing Order says the two highest-leverage things are barely ML: the **newsvendor
reframe** and the **data-access grind**. A directory reorganization is *neither* — it reduces zero
dollars of realized cost and ships zero critical ratios. So the honest framing of this whole review
is: **the seam fix is worth ~half a day because it removes a real ambiguity at the company's most
important interface and it's cheap while the tree is empty; everything beyond that on the
organization axis is procrastination dressed as architecture.** Do items 1–5, time-box them, and get
back to building the thing that beats the baseline in dollars.

Said to a chef: *get the pass organized once so two cooks aren't fighting over the same cutting
board — then stop rearranging the kitchen and start cooking.*

---

## Appendix — practices invoked (the three-domain habit)

- **(a) Software craft:** single-source-of-truth for a contract; dependency direction / module
  boundaries enforced by test, not convention; "don't reach across a module root with `../`."
- **(b) Data-science:** the raw-vs-truth firewall is a leakage-prevention boundary; a schema contract
  (pydantic/pandera) is the data-quality gate at the seam; DuckDB-over-Parquet keeps the verification
  boundary file-legible.
- **(c) Restaurant/consulting:** the on-ramp is a loss-leader, not a co-equal product — the directory
  tree should *say* that; one recipe sitdown feeds two products through one shared store; directional
  truth over false precision applies to architecture too (don't build machinery you can't yet justify).
