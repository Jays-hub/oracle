# Learning Path to Restaurant Consulting Fluency

**Companion to:** `restaurant-tech-consulting-framework.md`
**Starting point assumed:** strong intuition, limited restaurant domain knowledge, limited CS depth
**Realistic timeline:** billable in 6–8 weeks · competent at 6–9 months · genuinely good at 12–18 months

---

## Preface — two honest observations

**1. The framework is more forgiving than it looks.** Because §7.8.1 concludes you should *buy* the entity resolution substrate rather than build it, the engineering bar drops sharply. You do not need to be able to implement Fellegi–Sunter matching. You need to be able to **evaluate whether a vendor implemented it correctly** — which is a reading-and-judgment skill, not a building skill.

**2. Your real risk is the opposite of what it feels like.** With high intuition and low CS confidence, the instinctive move is to spend nine months learning machine learning before talking to anyone. That would be the single worst use of your time, because the framework's own thesis (§7.8.2) is that the moat is **judgment and adoption, not model sophistication.**

> **Time-box the CS. Uncap the domain.** An operator will forgive a crude model from someone who obviously understands restaurants. They will not forgive an elegant model from someone who calls covers "customers."

**If you already have working forecasting capability from the product business**, skip Stages 3–5 and go straight to Stage 0, then 2, then 6–7. The domain gap is your binding constraint, not the technical one.

---

## The ordering principle

Learn in the order that **produces billable capability**, not the order a curriculum would teach.

Every stage below ends with something you can sell. If a stage doesn't, it's mis-scoped and should be cut or deferred. This is the same logic as §7.5 applied to yourself: **the short-term plays don't just fund the client's substrate — they fund your education.**

Two rules that apply throughout:

- **Practice on real restaurant data only.** You have a cafe client with a year of history. That is your curriculum. Never do a tutorial dataset when you could do the same exercise on their POS export.
- **Get into kitchens repeatedly.** Free, and the highest-ROI item on this entire document. A week of shifts teaches you more about why recommendations fail than any book will.

---

## Stage 0 — Restaurant literacy

**Weeks 1–6. Non-negotiable and first.**

You cannot consult in an industry whose financial statements you can't read at a glance.

### Learn

**The P&L.** Prime cost, COGS %, labor %, occupancy cost, controllable vs. non-controllable, EBITDA, flow-through. Why everything is expressed as a percentage of sales rather than in dollars (Part 5 of the framework).

**The operating vocabulary.** FOH/BOH, covers, turns, PPA, dayparts, 86ing, par levels, walk-in, prep list, the line, expo, KDS, comps vs. voids vs. discounts, tip pooling vs. tip sharing, stage (the kitchen internship).

**Purchasing.** Broadline distributors (Sysco, US Foods, PFG) vs. specialty vs. local. Cases and packs, cost per ounce, spec sheets, order guides, yield and trim loss, credits and short-ships.

**The concepts.** QSR vs. fast casual vs. full service vs. cafe. Why their cost structures and constraints differ.

### Practice

Get one real P&L — from your cafe client or a template — and **rebuild it from scratch in a spreadsheet.** Compute prime cost. Do it repeatedly until the arithmetic is automatic and you can eyeball a statement and immediately know what's off.

Then **stage in a kitchen.** Ask your client. A week of unpaid shifts — prep, line, close — plus a day shadowing a manager doing inventory and placing an order. This is worth more than every book on the list.

### Sellable at the end

Nothing yet. This stage buys you the ability to be taken seriously, which is a prerequisite for selling anything.

### Done when

You can explain to a stranger, without notes, why a business at 5% net margin should care more about one point of COGS than about 20% sales growth — and why that's true (Part 5).

---

## Stage 1 — Spreadsheet analyst

**Weeks 4–10, overlapping Stage 0. Still not CS.**

### Learn

Pivot tables, lookups, INDEX/MATCH, absolute vs. relative references, structured tables, data hygiene. Charting that communicates rather than decorates.

Then the restaurant-specific models:
- Plate costing from recipe + purchase price + yield
- The menu engineering matrix (popularity × contribution margin) from a raw POS export
- Price-vs-mix decomposition (framework §"Measuring it honestly")

### Practice

Build the menu matrix for the cafe from their actual export. Then build the modifier give-away analysis — it's a pivot table over item/modifier data joined to estimated ingredient costs.

### Sellable at the end

**Menu analysis. Price integrity audit. Modifier gap analysis.** Three of the highest-dollar plays in §7.3 are deliverable at single-unit scale with a spreadsheet and no code at all. This surprises people.

### Done when

You can take an unfamiliar POS export and produce a defensible menu matrix and modifier leakage figure in under a day.

---

## Stage 2 — The audit column

**Weeks 6–14, in parallel. Domain knowledge, not CS.**

This is your first real revenue and it requires zero programming. It is also, per §7.8.3, a mature industry with 30-year incumbents — so learn it to **bundle and refer**, not to compete head-on.

### Learn

**Merchant processing** first — highest value, most transferable. The three-part cost decomposition, published Visa/Mastercard interchange schedules, pricing models (interchange-plus vs. tiered vs. flat), the junk-fee taxonomy, terminal lease traps, and how to compute an effective rate.

Then, one weekend each: waste hauling contracts, linen and hood, commercial utility tariffs, workers' comp class codes, CAM reconciliation.

### Practice

Compute the effective rate on any small business's merchant statement you can get — your own, a friend's, a family member's. Build a reusable one-page template while you do it.

### Sellable at the end

**The entire non-CS column of §7.2.** This is your bridge income while Stages 3–5 are underway.

### Done when

You can read a merchant statement cold and state the effective rate, the pricing model, and the three most likely recoverable items within twenty minutes.

---

## Stage 3 — Data handling

**Months 3–6. CS begins here, and only as much as needed.**

### Learn

**SQL** — this is 80% of the CS column. SELECT, WHERE, JOIN, GROUP BY, CTEs, window functions, and date/time handling. Date handling is where restaurant data goes wrong (business day ≠ calendar day; a 2am close belongs to the prior day).

**Python for analysis, not software engineering.** pandas: read, filter, groupby, merge, pivot, resample. matplotlib enough to make an honest chart.

**Data hygiene as a discipline.** Types, nulls, duplicates, timezone handling, and the difference between "missing" and "zero" — which in restaurant data is the difference between "closed" and "sold nothing."

### Practice

Reproduce every Stage 1 spreadsheet analysis in SQL and pandas. Same answers, less clicking. Then do the ones a spreadsheet can't:

- Void/comp distribution by employee, hour, and item
- Open/unclosed checks
- Labor hours vs. sales by 15-minute interval
- Cross-unit comparison between the cafe and the BBQ place

### Sellable at the end

Most of §7.3: void/comp analysis (descriptively — see the Stage 4 gate), open checks, labor overlay, cross-unit benchmarking, and the matching half of delivery reconciliation.

### Done when

Given a raw POS export you've never seen, you can load it, diagnose its quirks, and answer an unanticipated question about it in an hour.

---

## Stage 4 — Statistics for decisions

**Months 5–9. This is what separates you from a spreadsheet analyst.**

### Learn

- **Distributions and quantiles**, and why the mean is the wrong answer to an asymmetric-cost decision (the newsvendor logic, framework §2.1)
- **Variance and coefficient of variation** — required for the capacity diagnostic's variance-collapse signature
- **Confounding and controlling** — why raw server check averages are meaningless without adjusting for daypart, party size, and station
- **Multiple comparisons and false discovery rate** — see the gate below
- **Baselines and holdout validation** — the naive benchmark, and why tuning on the holdout is self-deception

> **⚠ Ethics gate.** Do not run *any* person-level analysis (void/comp by employee, server variance) until you can correctly apply exposure adjustment and FDR control. Naive versions flag innocent people at near-certain rates and someone gets fired over your chart. This is a hard prerequisite, not a nice-to-have (§7.7, note 4).

### Practice

Run the comp analysis on the cafe twice — once naively, once with exposure adjustment and FDR control. Compare the flagged sets. The difference will teach you more than any textbook paragraph.

### Sellable at the end

Void/comp and server variance **run responsibly**. The capacity vs. demand diagnostic. An honest backtest.

### Done when

You can explain to a non-technical owner why you're *not* naming the three servers their raw comp numbers appear to indict.

---

## Stage 5 — Forecasting

**Months 7–14. The differentiated core.**

### Learn, in this order

1. **Baselines first.** Seasonal naive (same weekday last week). Always benchmark against it; it is the client's current implicit forecast.
2. **Time series fundamentals** — trend, multiple seasonalities, day-of-week, holidays and holiday proximity, structural breaks.
3. **Regression with calendar features**, then gradient boosting (LightGBM with a quantile objective is the practical workhorse).
4. **Quantile / pinball loss** — training to the newsvendor service level rather than the mean.
5. **Hierarchical models and partial pooling** — the technique that solves your segment's small-*n* problem.
6. **Forecast reconciliation** (MinT) across total → location → category → item.
7. **Cold start via pooling** — which is exactly the BBQ place's situation.

### Practice

The full backtest on the cafe: hold out four weeks, fit, predict, report WAPE against seasonal naive at daily, daypart, and item level. Then the variance decomposition. Then re-run everything at item level once the substrate is in place and measure the improvement.

### Sellable at the end

The holdout backtest, labor scheduling to forecast, prep quantity recommendations — the engagement the whole framework builds toward.

### Done when

You can produce a calibrated item-level quantile forecast that beats seasonal naive on held-out data, and explain in plain English to an owner why the 74th percentile is the right prep target for a given dish.

---

## Stage 6 — Optimization and causal inference

**Months 12–18. Converts forecasts into decisions and proves impact.**

- **Newsvendor → order quantities and prep lists**, subject to pack sizes and minimums
- **Linear and mixed-integer programming** for scheduling (PuLP or OR-Tools), subject to shift lengths, skill coverage, overtime thresholds
- **Causal methods** — difference-in-differences, synthetic control across their own units, switchback designs for daypart-level price tests

### Done when

You can defend a price change's measured effect to a skeptical accountant.

---

## Stage 7 — Vendor fluency

**Ongoing from month 3. Not CS learning — market learning, and unusually high ROI.**

Per §7.8.1 you are a **buyer and implementer** of the substrate, not its builder. That makes vendor knowledge a core competency.

Get demos and trial accounts for MarginEdge, Restaurant365, MarketMan, ClearCOGS, 7shifts, and Toast's native reporting. For each, answer: what grain does it resolve to? Does it handle yield? Is its review queue prioritized by spend or by record count? Does its item master have temporal validity? What does it do badly?

**Done when** you can recommend a stack for a given operator in one meeting and defend why you excluded the alternatives.

---

## What NOT to learn (yet, or ever, for this)

| Skip | Why |
|---|---|
| Deep learning, transformers, LLM fine-tuning | Irrelevant to tabular forecasting at this scale. Gradient boosting beats them here. |
| Software engineering, deployment, MLOps | You are buying tools, not shipping product |
| Building entity resolution from scratch | §7.8.1 — a $350/month product with 11,000 customers already did it |
| Advanced Bayesian computation | Stage 5+, and only if pooling demands it |
| Web development, dashboards | Deliver in whatever the client already opens |

---

## Curated resources

**Restaurant domain**
- *Restaurant Success by the Numbers* — Roger Fields. The accessible financial primer. Read first.
- *The Restaurant Manager's Handbook* — Douglas Robert Brown. Encyclopedic; use as reference, not cover-to-cover.
- *Setting the Table* — Danny Meyer. For the industry's values and why hospitality decisions aren't always economic ones.
- *Kitchen Confidential* — Anthony Bourdain. Culture and kitchen psychology. Explains why your recommendations will be resisted.
- Toast's *On the Line* blog, Restaurant Business, Nation's Restaurant News — for current vocabulary and issues.

**Analysis and statistics**
- *Forecasting: Principles and Practice* (3rd ed.) — Hyndman & Athanasopoulos. **Free at otexts.com/fpp3.** Covers hierarchical forecasting and reconciliation directly. The single most relevant book on this list.
- *Statistical Rethinking* — Richard McElreath. The best on-ramp to hierarchical/partial pooling thinking.
- *Python for Data Analysis* — Wes McKinney. pandas from its author.
- SQL: skip books. Use interactive practice (SQLBolt, Mode's SQL tutorial) then immediately apply to real exports.

**Communication**
- *Storytelling with Data* — Cole Nussbaumer Knaflic. Your deliverables are charts an exhausted owner reads in thirty seconds. This matters more than it sounds.
- *The Goal* — Goldratt. Theory of constraints, which is the intellectual basis of the capacity vs. demand diagnostic.

---

## The first 90 days, concretely

| Weeks | Focus | Output |
|---|---|---|
| **1–3** | Restaurant literacy. Rebuild a P&L by hand. Read Fields cover to cover. | Fluent in the vocabulary |
| **2–4** | **Stage in your client's kitchen.** Prep, line, close. Shadow inventory and ordering. | Understanding of why things fail |
| **3–6** | Spreadsheet mastery on the cafe's real export. Menu matrix. Modifier analysis. | **First sellable deliverable** |
| **5–8** | Merchant processing deep-dive. Build the audit template. | **First revenue** |
| **6–10** | SQL and pandas, reproducing everything you did in spreadsheets | Ability to answer unanticipated questions |
| **8–12** | Vendor demos. Set up BBQ place instrumentation. Delivery reconciliation on the cafe. | Positioned as the systems advisor, not the auditor |

At day 90 you should have: a paying client, two delivered findings, a kitchen's worth of lived context, and enough SQL to stop being afraid of a raw export. Forecasting comes after that, and it comes faster than you expect once the data handling is fluent.

---

## Five rules to keep

1. **Every stage ends in something billable.** If it doesn't, cut it.
2. **Learn on their data, never on tutorial datasets.**
3. **Domain fluency compounds faster than CS fluency for the first year.**
4. **The Stage 3 plateau — SQL, pandas, spreadsheets — supports two years of billable work.** Don't rush past it out of insecurity.
5. **When in doubt, go stand in a kitchen at Friday peak.** Everything in the framework was written by someone who inferred it from data. You get to see it directly, and that's the advantage you actually have.
