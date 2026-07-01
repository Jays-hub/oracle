# common_base_reconciliation — Decision Record for the Shared Data Store

**Status:** Decided in principle, **not yet built.** Read this before any session that constructs the
common database. It is the record of *why* the shared store is shaped the way it is, and the concrete
plan for turning today's `data/` folder into a queryable common base **without** breaking the
discipline the whole project depends on.

**Companions:** `data/CONTRACT.md` (the store *as contracted today*), `forecasting/docs/simulated_data.md`
(the schemas + generative process), `.claude/rules/01-data-ingestion.md` (the enforced law).

---

## 1. The question that prompted this

The startup was reframed into **two parts that feed a common database**: the `forecasting/` engine
and the `onramp/` service. That framing surfaced a tension worth resolving on purpose rather than by
drift:

- The strategy + data docs describe a **file-based** handoff: the on-ramp writes CSV/Parquet into
  `data/raw/`; models read only from `data/raw/`; ground truth sits in `data/_truth/` for scoring.
- But "common **database**" implies a queryable store both parts open against — and the on-ramp's
  stack note already says "SQLite or DuckDB for local price history."

So: is the common base a **folder of files** or a **real database**? And whichever it is, **how does
the sacred raw-vs-truth firewall survive** the choice? (That firewall — models read only `raw/`, only
`evaluate/` reads `_truth/` — is what makes every model in the project *verifiable*. It is not
negotiable; the store design must preserve it.)

## 2. The options considered

**Option 1 — Stay pure files (CSV/Parquet in `data/`).**
*Pro:* dead simple; git-diffable; the firewall is just a folder boundary enforced by a path assertion
+ import-linter. *Con:* no SQL ergonomics; cross-file joins are hand-rolled in pandas; the "common
database" framing is aspirational only.

**Option 2 — One real RDBMS (Postgres/SQLite) as the common base.**
*Pro:* a genuine shared query surface; real constraints/roles. *Con:* the firewall now has to be
enforced by **schemas/roles/connections** instead of folders — more machinery, and easy to get
subtly wrong (a single over-broad connection string leaks `_truth` into a model path and every result
becomes a lie). Also adds a server/ops surface a Phase-0 learning build does not need. Heavier;
higher risk to the one invariant that matters most.

**Option 3 — DuckDB *over* the Parquet/CSV files in `data/` (CHOSEN).**
DuckDB queries Parquet/CSV in place. The "folder of files" and the "common database" become **the
same artifact viewed two ways**: the files are the durable, diffable, contract-checkable store; DuckDB
is the SQL query layer both peers open against it. You get the database ergonomics the "common base"
framing wants **without** giving up the file-level firewall the verification discipline depends on.

## 3. The decision

**Adopt Option 3: DuckDB-over-Parquet as the shared query layer; the `data/` folder boundary stays
the firewall enforcement surface.**

Rationale, in one line per domain (the project's three-domain habit):
- **(a) software:** keep the cheap, legible enforcement (a folder boundary + a path assertion) and
  add a query layer on top, rather than swapping a simple invariant for a complex one.
- **(b) data-science:** the raw-vs-truth split is a *leakage boundary*; expressing it as a physical
  directory split makes leaks structurally visible and CI-catchable. Don't dissolve it into schema
  permissions that fail silently.
- **(c) restaurant/consulting:** directional truth over false precision applies to infrastructure
  too — don't stand up an RDBMS (machinery you can't yet justify) before a single critical ratio
  runs. The common base earns complexity only when the data exists to put in it.

## 4. How the firewall maps onto each option (the part not to get wrong)

| Store form | "Models read only raw" becomes… | Enforced by |
|---|---|---|
| Pure files (today) | read only files under `data/raw/` | path assertion + import-linter (rule 01) |
| Real RDBMS | connect only to the `raw` schema; only `evaluate` may touch `truth` | DB roles/grants + separate connections (fragile) |
| **DuckDB-over-Parquet (chosen)** | open only the `data/raw/**` Parquet/CSV globs in model paths; `_truth/**` opened only by `evaluate/` | **same folder boundary** as today + a thin DB-access helper that refuses non-`raw` globs in model code |

The chosen form keeps the enforcement identical to today's file rule — the DB layer is *additive*,
not a replacement for the firewall.

## 5. What the common base carries (the seam)

Authoritative list lives in `data/CONTRACT.md`. In brief, the on-ramp writes three legs to
`data/raw/` (`sales_export`, `bom`, `price_observations`); the fourth leg (`eightysix_log`) arrives
via the separate 86-tap habit; the engine reads all of `data/raw/`, writes `interim/`+`processed/`,
and scores against `_truth/` — which only `simulate/` writes and only `evaluate/` reads.

## 6. Starting checklist — for the session that actually builds the DB

Do **not** do these now (Phase 0, nothing built; Anti-Drift). When the time comes — i.e. once
`forecasting/src/simulate/` emits real Parquet, or the first plate-cost BOM write happens — treat "stand
up the shared query layer" as a normal phase (build freely, review closes on code merit;
`.claude/rules/00-process.md`), then:

1. **Land the store as Parquet, not CSV**, under the existing `data/{raw,interim,processed,_truth}/`
   layout. Parquet keeps types and is what DuckDB reads fastest. (CSV is fine for tiny seed tables.)
2. **Write a single DB-access helper** (suggested: `forecasting/src/data/store.py`) that opens a
   DuckDB connection and exposes *read* views over `data/raw/**` only. Model/feature code imports
   this helper; it **refuses** to register any `_truth/**` or `interim/processed` glob. This is the
   path assertion, relocated into the query layer.
3. **Keep the truth reader separate** — `forecasting/src/evaluate/` gets its *own* helper that may
   open `data/_truth/**`. Nothing else imports it. (Single funnel for the oracle — rule 01.)
4. **Define the `schemas/` definitions** for the seam files (pydantic/pandera) and validate on the
   on-ramp's write **and** the engine's read. This is the moment `schemas/` stops being empty.
5. **Add the cross-module boundary test** (`onramp/` never imports `forecasting/`; no `_truth` path
   in either model code or `onramp/`) to CI, beside the existing leakage canary + import-linter.
6. **Do not introduce a server.** DuckDB is embedded/in-process. If a multi-restaurant pool (Phase 6)
   or a real deployment later needs a server-class DB, that is a *separate* decision recorded *then* —
   this record covers the single-build common base only.

## 7. Open questions deferred to that session

- **Parquet partitioning** (by `business_date`? by `item`?) — decide against the real query patterns,
  not speculatively.
- **Multi-restaurant pooling (Phase 6):** does the cross-restaurant store stay one DuckDB base with a
  `restaurant_id` column, or split per tenant? The cross-platform-pool *moat* lives here, so revisit
  with the hierarchy phase, not before.
- **Real exports replacing the simulation:** when a live POS/invoice feed lands, the `schemas/`
  schemas become the ingestion gate; confirm the simulated schema and the real schema agree (they
  should, by construction of `forecasting/docs/simulated_data`).

---

*This record exists so the common-database decision is made once, deliberately, and not re-litigated
or quietly drifted into an RDBMS mid-build. When you build it, build Option 3, preserve the firewall,
and update `data/CONTRACT.md` to mark the query layer "built."*
