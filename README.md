# Restaurant Loss-Forecasting Platform

One company, **two durable parts**, feeding a **common data store**:

- **`forecasting/`** — the core engine. Prep-demand forecasting under a waste framing (a daily prep
  sheet). The moat. → `forecasting/CLAUDE.md`
- **`onramp/`** — the on-ramp service: a durable bridge that delivers instant, dollar-legible value
  and captures the engine's data in the same act. Current implementation: `onramp/plate_cost/`.
  → `onramp/README.md`
- **`data/`** — the common store, owned by neither peer. The on-ramp writes `data/raw/`; the engine
  reads it. → `data/CONTRACT.md`

Start with `CLAUDE.md` (the platform charter). The `docs/` encyclopedia is the deep "why" behind it.

## The Encyclopedia (two homes)

`CLAUDE.md` is the terse anchor; these are the human-readable deep dives. Read top-to-bottom in the
order listed below the first time; thereafter use as reference. The chapters live in **two** places:
platform-level method/strategy in `docs/`, engine-specific theory in `forecasting/docs/`.

**Platform — `docs/`** (cross-cutting; both peers depend on these)

| File | What it covers | When you need it |
|---|---|---|
| `docs/overview_and_method.md` | Project identity, strategic context, and **how comprehension works** (building and review are free; understanding is grown on a parallel `/learn` + `docs/mastery.md` spaced-repetition track that gates nothing) | First. Sets how the whole project is run. |
| `docs/strategic_context.md` | Why this wedge: the accuracy trap + the 5-part test, the closed lanes (A–E), founder constraints, and the open gates | When questioning direction or scope — the strategic "why." |
| `docs/discovery/discovery_and_validation.md` | Where the "Marco" data assumptions come from (the onboarding transcript), the cold-discovery question set, and the A1–A13 assumption decoder | Phase 1 data realism; and before any real customer interview. |
| `docs/common_base_reconciliation.md` | The decision log for the shared data store: files vs. a real DB, DuckDB-over-Parquet, and how the raw/truth firewall survives the move | Before any session that builds out the common database. |

**Engine — `forecasting/docs/`** (forecasting-specific theory)

| File | What it covers | When you need it |
|---|---|---|
| `forecasting/docs/conceptual_spine.md` | The **newsvendor** keystone — why the prep decision is a quantile, not a forecast; why waste falls out for free | Before any modeling. This is *the* idea. |
| `forecasting/docs/simulated_data.md` | Full spec of the synthetic dataset: schemas, the generative process, the realism checklist, and the raw-vs-truth discipline | Phase 1, and any time you touch data. |
| `forecasting/docs/construction_roadmap.md` | The phase-by-phase build plan (P0–P8): objective, why-now, code deliverables, practices invoked, done-when | Continuously. Your map start→finish. |
| `forecasting/docs/data_hard_truths.md` | The 10 domain gotchas that separate "fits a model" from "understands restaurant data" | Drill these; they recur across phases. |
| `forecasting/docs/mastery_and_customer_language.md` | Concepts to master + where to learn them, and the plain-language cheat sheet for talking to operators | Learning, and prepping customer conversations. |

**The one rule that governs everything:** code and the *why* advance together — but on parallel tracks.
Code ships on its merits (build freely; review closes on code quality). Understanding is grown
continuously and re-checked over time on the `/learn` + `docs/mastery.md` spaced-repetition track, which
tests why each step was necessary, how it changed the codebase, and the practices it called on — across
software, data-science, and restaurant domains. It gates nothing. See `docs/overview_and_method`.

## Shape of the repo
```
.
├── CLAUDE.md            # platform charter (start here)
├── docs/               # platform encyclopedia: method, strategy, discovery + common-base record
├── data/               # the common store (platform-owned): raw/ interim/ processed/ _truth/ + CONTRACT.md
├── config/             # shared config (YAML)
├── schemas/            # shared schemas both peers import
├── forecasting/        # PEER 1 — the core engine (+ forecasting/docs/ = engine theory)
└── onramp/             # PEER 2 — the on-ramp service → plate_cost/ (current implementation)
```
