# repo_architecture — Decision Record for the Multi-Restaurant Repo Shape

**Status:** Shape **decided on paper, deliberately not yet built.** Read this before any session that
restructures directories, adds a second real tenant, or stands up the pooling substrate. It records
*why* the repo is shaped the way it is as real restaurants arrive, and — just as importantly — **how
little of it to build now.**

**Companions:** `real_data_readiness.md` (the L0–L5 gap analysis + R0–R6 order — read first),
`common_base_reconciliation.md` (why the store is DuckDB-over-Parquet), `../data/CONTRACT.md` (the
seam as contracted today), `consulting_framework.md` §2.1/§4.7/§7.8 (pooling, grain, the marginal
cost of questions).

---

## 1. The question that prompted this

Jay proposed a consolidating codespace shaped as **a folder per restaurant** — each operator's data
in its own area — with **technique folders alongside** (entity resolution, forecasting, and the other
processes to be built) that read from those areas and **write results back into each restaurant's
folder.**

```
repo/
├── restaurants/
│   ├── halden/     { raw data, results }
│   ├── depot_bbq/  { raw data, results }
│   └── …
├── entity_resolution/
├── forecasting/
└── …
```

The instinct behind it is correct and the requirement it encodes is non-negotiable. The
*implementation* has a failure mode that gets worse precisely as the business succeeds, which is the
kind worth catching on paper rather than at n=5.

## 2. What the proposal gets right (keep all of this)

- **Tenant isolation is a hard requirement.** One operator's data must never surface in another's
  report, and each must be deletable on request. Already built in W9 (`tenant_raw_dir()`'s path-safe
  slug validator, the shared sentinel, cross-tenant isolation tests). This decision *extends* that; it
  does not replace it.
- **Techniques must be separate from data.** Correct, and the reason the current seam works at all.
- **Per-restaurant retrievability of results.** An operator-facing "here is your stuff" view is real
  and needed (L4). The disagreement is only about whether that view is the *storage truth* or a
  *query over runs*.
- **Data does not belong in git.** Already the standing practice — `/data/raw/*` and
  `/docs/discovery/_raw/*` are gitignored; five files are tracked under `data/`, all `.gitkeep` plus
  the contract. A `restaurants/<name>/` layout invites violating this, since it *looks* like source.
  Real POS exports are large and re-exported often; invoice scans are large binaries; git keeps every
  version forever. And it is customer financial data and PII — once committed it is in every clone and
  every fork, and removing it means rewriting history.

## 3. The six failures, worst first

**1. Folder-per-restaurant taxes the only query that compounds.**

The strategy docs say it three ways — principle #6 (data-network-effect moat), principle #10
(hierarchical/transfer learning so a new restaurant works on day one), 5-part test #5 (a compounding
data loop). `consulting_framework.md` §2.1 says it independently: partial pooling *"solves cold start
outright: a new location inherits the group prior on day one, which independent models cannot do at
all."* And `discovery/2026-08-12_wes.md` §8 says cold start is the live, felt pain.

A filesystem partitioned by restaurant makes the single-tenant read trivial and the **all-tenant read
a directory walk plus ad-hoc concatenation** — glue written once per technique, slightly differently
each time, rotting independently. The single-tenant query is the one that does not compound. The
cross-tenant query is the asset. **The layout would tax the asset and subsidize the commodity.**

**2. "Results back into each folder" is pre-computed answers to anticipated questions.**

§7.8 states the actual payoff of a substrate precisely: it *"collapses the marginal cost of asking
questions."* Before resolution, every question is a bespoke analysis and cost is linear in questions;
after, questions are queries — high fixed cost, near-zero marginal. A results-directory is the
*before* shape wearing the *after* clothes: the first unanticipated question puts you back to bespoke
work. The target is a **queryable store**, not a directory of frozen answers.

**3. Result files overwritten in place destroy lineage.**

`restaurants/halden/results/prep_sheet.csv` cannot answer: which code version produced it, against
which input snapshot, under what config? Standing order #5 (`../CLAUDE.md`, from §3.3) forbids
emitting a number whose lineage you have not validated, because *"the failure mode that ends
engagements is a confident figure the owner acts on that turns out to rest on a bad unit conversion or
a false merge."* Overwrite-in-place is the canonical way that record is lost, and L5 (lineage,
reproducible reporting) later needs exactly what it destroys.

**4. Techniques as sibling folders flatten a dependency chain into a peer group.**

Entity resolution is L1. Forecasting is L3 and consumes L1's output. A merchant-processing audit is a
§7.1 one-off play that touches neither. As siblings they read as interchangeable and nothing prevents
an import in the wrong direction. This repo already learned the lesson — it is why `.importlinter` and
the seam contract exist. A restructure must not discard that enforcement.

**5. The unit of schema variation is the POS vendor, not the restaurant.**

Halden's on Toast, Depot on Square, the next client on SpotOn. If the folder is the organizing unit,
vendor-specific parsing scatters across tenant folders and duplicates. The correct factoring is **one
adapter per source system**, with tenant carried as a key.

**6. It re-invents multi-tenancy that already ships.**

`data/raw/<restaurant_id>/` exists with validation and isolation tests (W9). Extend it; do not fork it.

## 4. The options considered

**Option 1 — Folder per restaurant, techniques as siblings (the proposal).**
*Pro:* isolation is obvious and physical; easy to reason about at n=1; trivially easy to hand one
operator their folder. *Con:* everything in §3. Pooling becomes glue, lineage is lost on overwrite,
dependency direction is unenforced, vendor variation scatters.

**Option 2 — One database per restaurant.**
*Pro:* the strongest possible isolation story; a per-tenant restore or delete is one file. *Con:* the
same pooling tax as Option 1, plus schema migrations must now run N times and can drift apart. Cross-
tenant analysis requires ATTACH-ing N databases and unioning by hand. Gets worse monotonically with
every new client.

**Option 3 — One partitioned store, tenant as a key (CHOSEN).**
Hive-style partitioning (`restaurant_id=<id>/`) under the already-decided DuckDB-over-Parquet store.
*Pro:* single-tenant reads are a predicate pushdown (`WHERE restaurant_id = ?`); **cross-tenant reads
are the default — you simply omit the filter.** One schema, one migration path. Isolation moves to the
access layer, where W9's validator already lives and where it can be tested once rather than per
directory. Partition pruning means single-tenant reads stay as fast as separate folders.
*Con:* isolation is enforced by code rather than by physics, so the access layer must be tight and
covered by tests — which W9 already established the pattern for. Accepted deliberately: the alternative
buys marginally stronger isolation at the cost of the moat.

## 5. The decision — three separations, held strictly

### 5.1 Code ↔ data

The repo holds code, config, schemas, and migrations. **Data lives outside version control**, behind
a root path resolved from config. This is already the practice; the restructure must not erode it.

### 5.2 Tenant is a partition key, not a directory identity

One logical store, partitioned by `restaurant_id`. Single-tenant is a predicate; all-tenant is the
absence of one. Pooling becomes free instead of a rewrite.

### 5.3 Code organizes by layer, not by technique

The L0–L5 order *is* the dependency direction, so it can be enforced mechanically rather than
remembered:

| Dir | Layer | Contents |
|---|---|---|
| `ingest/` | L0 | one adapter per source system (`toast/`, `square/`, `spoton/`, `invoices/`) |
| `identity/` | L1 | canonicalize → block → match → cluster → adjudicate (the R2–R6 spec) |
| `measures/` | L2 | plate cost, contribution margin, theoretical vs. actual variance |
| `decide/` | L3 | quantile forecasting, newsvendor, optimization |
| `surface/` | L4 | web, prep sheets, operator-facing reports |
| `plays/` | ⊥ | §7.1 one-off analyses — read the store, emit a report, **not** in the dependency chain |

Import-linter contracts express the arrows: `identity/` may not import `decide/`; nothing may import
`plays/`. Standing order #4 stops being a thing an agent must remember and becomes a thing CI checks.

**Why `plays/` sits outside the chain.** Merchant-processing audits, modifier-gap analysis, and
delivery reconciliation are *stock, not flow* (§7.8): one-time extractions from a finite pool,
detective rather than prescriptive. They fund and de-risk the substrate but must never become a
dependency of it, or their commoditized, non-compounding nature infects the part that does compound.

### 5.4 Runs replace result files

Every execution writes under a `run_id` with a manifest — code version, input snapshot reference,
config hash, timestamp. Outputs are immutable; **"latest" is a pointer, not an overwrite.** The
per-restaurant results view Jay wanted becomes a *query over runs* — same operator-facing feel,
without making it the storage truth. Built once, it is also exactly what L5 needs later.

## 6. The target shape

```
repo/                          ← code, config, schemas. No data, ever.
├── ingest/        L0   adapters: toast/ square/ spoton/ invoices/
├── identity/      L1   ER — the R2–R6 spec (src/ingestion/__init__.py today)
├── measures/      L2   plate cost, theoretical vs. actual, margin
├── decide/        L3   forecasting, newsvendor, optimization
├── surface/       L4   web, prep sheets, reports
├── plays/         ⊥    one-off analyses; deliberately outside the dependency chain
└── schemas/ config/ tests/

<data root — outside git, path from config>
├── raw/        restaurant_id=<id>/source=<vendor>/dt=<date>/…   immutable, as-received
├── canonical/  restaurant_id=<id>/…                             adapter output, schema-conformed
├── resolved/   restaurant_id=<id>/…                             post-ER, entity ids assigned
├── marts/      restaurant_id=<id>/…                             features, measures
├── runs/       run_id=<uuid>/ manifest.json + outputs           immutable execution record
└── _truth/                                                      simulation only — firewall intact
```

`raw → canonical → resolved → marts` is the existing `raw/interim/processed` idea with the **one layer
the pivot adds: `resolved/`,** which is where L1 output lands and which nothing today produces.

**The firewall is unchanged.** `_truth/` stays write-only-by-`simulate/`, read-only-by-`evaluate/`,
never a model input, never touched by the on-ramp. Any restructure that weakens this is rejected on
sight — it is what makes every backtest in the project verifiable (`common_base_reconciliation.md` §1).

## 7. Migration path from today

Ordered so that each step is independently useful and none is a big-bang rewrite.

| Step | Change | Trigger |
|---|---|---|
| M1 | Add `source=` and `dt=` partition levels under the existing `data/raw/<restaurant_id>/` | R1, with the first real adapter |
| M2 | Introduce `runs/` + manifests; have one technique write through it end-to-end | R1 |
| M3 | Add the `resolved/` layer | R2, when ER produces its first output |
| M4 | Rename `restaurant_id=<id>` to Hive-style partition dirs; point the DuckDB views at globs | when a **second real tenant** exists — not before |
| M5 | Re-home code into the layer directories + import-linter contracts | when the layer boundaries are load-bearing, i.e. once `identity/` has real code |

**M4 and M5 are explicitly deferred.** At n=1 they are pure churn against 622 passing tests and buy
nothing. The point of deciding the shape now is that M1–M3 can be built *compatible* with it, so M4/M5
are renames rather than redesigns.

## 8. What to build now — and the reason to build almost none of it

**The binding constraint is not storage. It is that zero real restaurants' data exists.** Designing
and building the multi-tenant pooling substrate before the first real export lands violates standing
order #4 (`../CLAUDE.md`): do not build a layer whose prerequisites are absent.

So the recommendation splits:

- **Decide the shape now** (this document). Partition key, adapter-per-vendor, run manifests,
  layer-ordered code. These are cheap on paper and expensive to retrofit — the same argument §4.7
  makes about temporal validity, where retrofitting is *"close to a rebuild."*
- **Build only what R0–R1 needs, for one restaurant.** One adapter, one tenant, daily grain, the seam
  actually connected (`real_data_readiness.md` §2 blockers B1, B2, B5). Part 5's warning applies to
  the builder as much as the client: *"a nine-month cleaning project with no visible output loses the
  client in month four."*

The partitioned shape **costs nothing extra at n=1** and is the difference between pooling being free
and pooling being a rewrite at n=5. That asymmetry is the entire reason to write this down before
building anything.

## 9. What this does not decide

1. **Whether `identity/` (R2–R5) is built or bought.** Unchanged from `real_data_readiness.md` §3 —
   decided after R0, on measured variance from a real export. This document's shape works either way:
   if bought, `identity/` becomes a vendor client plus the adjudication and grain judgment that stays
   yours (§7.8.2), and `resolved/` is populated by import rather than by local matching.
2. **Where the data root physically lives** — local disk, an object store, or a managed warehouse.
   Deliberately left open; the config indirection in §5.1 is what makes it a late, cheap decision.
3. **Whether the existing `forecasting/` + `onramp/` peer split survives M5.** The layer directories
   cut across it. Both framings can coexist (peers own layers) but the charter should eventually say
   one thing — the same open item as `real_data_readiness.md` §6.
4. **Cross-tenant consent and contracts.** Pooling one operator's data to improve another's forecast
   is the moat *and* a commitment made to a real business. The technical shape here enables it; the
   agreement that permits it is not a repo decision and is not made here.
