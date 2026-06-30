# forecasting/docs/ — Engine Theory

The forecasting-specific half of the project encyclopedia. These are the "how the engine is built"
chapters. The cross-cutting chapters they depend on — `overview_and_method` (method + the
Comprehension Contract), `strategic_context`, `discovery_and_validation`, and the
`common_base_reconciliation` record — live at the **platform** level in `../../docs/` (because both
peers depend on them).

Read in order; start with `overview_and_method` at the platform level.

| Chapter | What it covers |
|---|---|
| `conceptual_spine.md` | The **newsvendor** keystone — the prep decision as a quantile, not a forecast; waste as a free residual. *The* idea. |
| `simulated_data.md` | The synthetic-dataset spec: schemas, the generative process, the realism checklist, the raw-vs-truth discipline. |
| `construction_roadmap.md` | The phase-by-phase build plan (P0–P8): objective, why-now, deliverables, practices, comprehension checkpoint, done-when. |
| `data_hard_truths.md` | The 10 restaurant-data gotchas that separate "fits a model" from "understands the data." |
| `mastery_and_customer_language.md` | The mastery curriculum + the plain-language cheat sheet for talking to operators. |

Reading path: `../../docs/overview_and_method` → `conceptual_spine` → `simulated_data` →
`construction_roadmap` → `data_hard_truths` → `mastery_and_customer_language` →
`../../docs/strategic_context` → `../../docs/discovery_and_validation`.
