# Strategic Context (why this wedge, what's closed, what's unvalidated)

This is the strategic case the rest of the project assumes: why prep-demand forecasting is the chosen
wedge, which alternatives are already closed (so they don't get reopened), the reusable test that
selected it, and the constraints that govern the build. `docs/overview_and_method` (method) plus the
engine chapters in `forecasting/docs/` are *how* the engine is built; this is *why* it's the thing
worth building. **Everything here is a hypothesis filter, not validated fact** — only real customer
discovery (`docs/discovery/discovery_and_validation`) settles it.

## The wedge, in one paragraph
The surviving wedge is **ingredient/prep-level demand forecasting, sold under a waste/spoilage
framing** — a daily prep sheet telling the kitchen how much of each high-volume item to make tomorrow.
Lead the *sales pitch* with the waste pain ("stop dumping money in the bin / stop running out at 8pm" —
dollar-legible, opens wallets); build the *prep-demand engine* underneath (where the number IS the
decision and where the model + exogenous data create the edge). Waste isn't a separate product — it's
mathematically downstream of prep-demand (`forecasting/docs/conceptual_spine`). Nothing is built; the wedge rests on two
unvalidated assumptions: (1) is prep-item forecasting genuinely unsaturated, and (2) can the founder
source the exogenous signal that creates the edge.

## Founder constraints that govern the project
- **Goal: a *sustaining* business**, not necessarily venture-scale. This loosens the "must have a
  venture moat" pressure and makes a consulting-flavored model acceptable *if it sustains*. Live
  strategic fork: is this a **product** (per-restaurant work amortizes into something reusable) or a
  **consulting job** (bespoke per restaurant, headcount-ceilinged)? Different companies; decide it as
  discovery clarifies how reusable the work is.
- **A credibility fast-lane via a well-connected industry insider** — warm, high-trust access to
  multiple restaurants for discovery and data. Materially de-risks the distribution/data-access grind
  (principle #8). Does NOT remove the need for real discovery; it makes discovery fast instead of cold.
- **"Easy transition / no added work" is a hard governing gate**, co-equal with the test below.
  Adoption dies if the product adds daily work. It must ride on data already flowing and slot into a
  decision already made — no new ritual. This alone kills most forecasting ideas (anything with a heavy
  action layer or a new data-entry burden).

## Market reality (the constraints every idea hits)
Three-layer stack: **POS** (Toast dominant; Square; SpotOn/Lightspeed; Clover) owns the clean
transaction data and is increasingly **absorbing the adjacent layers**; **back-office/inventory**
(MarketMan, MarginEdge, Restaurant365, xtraCHEF, WISK…) — crowded; **labor/scheduling** (7shifts,
Fourth, Toast/R365-native) — crowded. Three structural facts: nobody re-enters data (everything
integrates with POS); POS platforms are eating the back-office layer; new entrants win as a sharp
"chef's knife," never a "Swiss Army knife." **Buyer barbell:** too small (single indie at capacity) and
too big (12+ unit chain with procurement + security review) are both wrong; the **viable zone is ~1–10
location operators** — enough pain and budget, no internal analyst, moves without procurement.
Recurring operator refrain: *"I don't need more data, I need to know what to do with it"* — the
decision/action layer, not analytics, is underserved.

## The accuracy trap, refined (the core reframe)
The "accuracy trap" (improving 88%→91% is invisible in the P&L, and the POS always has more data) is
**a property of the *target*, not of forecasting as a method.** It rests on four hidden premises, each
breakable by the right target:

1. **A usable baseline already exists** → breaks when the target is **unsaturated** (today set by gut
   at ~50%; the real delta is *nothing → a usable signal*).
2. **The predictive signal lives in POS transaction data** → breaks when the signal is **exogenous**
   (events, weather, the forward book — data the POS doesn't have).
3. **More data buys more accuracy** → **feature relevance dominates feature volume**; 100× more rows
   don't help if the binding signal is an unmodeled exogenous feature.
4. **A hard action layer sits behind the number** → breaks when **the number IS the decision** ("prep
   18" is the action; there's no judgment layer the way covers→staffing has).

Covers→staffing fails all four (which is why it's closed). A correctly chosen target escapes.

## The deeper trap: workflow / value-capture
Even a target that escapes all four faces a harder trap: **value flows to whoever owns the workflow and
the customer relationship, not to whoever produces the estimate.** A forecast is an *input*, and inputs
get commoditized by the layer that owns the decision surface — this is how POS platforms keep absorbing
these layers (a good-enough model bolted onto a workflow they already own). So the real bar is: **can
the estimate BE the product the operator pays for and acts on directly, not a feature the
workflow-owner absorbs?** The one structural asymmetry favoring a neutral entrant: a POS can only ever
pool *its own* customers; a neutral third party could **pool across Toast + Square + SpotOn + …** — a
cross-platform dataset no single POS can assemble. That moat is real **but it lives in the data
*access*, not the model** — and assembling it is the expensive distribution grind, not an ML
achievement.

## The 5-part test (reusable filter for any forecasting wedge)
A wedge escapes both traps only if it passes most of these; **#2 and #3 are the axes incumbents
structurally can't easily take — weight them most.**

1. **Unsaturated target** — and you can say *why*: small-for-them (good), not-worthless (must
   disprove), not-just-as-hard-for-you (must disprove — the CV lesson, lane D below).
2. **Exogenous or cross-platform signal** — predictive power from data outside any single POS.
3. **The number is the bottleneck** — a perfect estimate handed over for free nearly solves the
   decision (no human-judgment action layer behind it).
4. **Dollar-legible output** — maps to a figure the operator already tracks (a stockout, an over-order,
   a spoilage $), so even modest accuracy is perceptibly valuable.
5. **A compounding data loop** — usage generates proprietary (ideally cross-restaurant) data that
   improves the estimate, so the moat grows with adoption.

## Why prep-demand passes (and where it's weak)
- **#3 (number is the decision): STRONG** — "prep 18 short ribs" is the action; the single biggest
  reason it escapes covers→staffing.
- **#4 (dollar-legible): STRONG** — error maps to the 86'd dish and the end-of-night dumpster, both
  already felt daily.
- **No-added-work gate: VERY STRONG** — rides POS sales already flowing + a one-time chef confirmation
  of the ~15–25 big items; the output *replaces* a guess the prep cook already makes.
- **#1 (unsaturated): MIXED — validate this first.** POS-native tools forecast covers/$, not "braise
  18 short ribs." Plausible but unverified — this is the confirm-or-kill question for discovery
  (`docs/discovery/discovery_and_validation`).
- **#2 (exogenous): WEAK UNLESS deliberately added.** The base signal is POS-ownable; the prep forecast
  becomes *defensibly* better only by fusing in signal the POS can't see (events, weather-delta,
  day-before reservation depth). **Designing that exogenous layer is the technical heart of the
  differentiation.**

## The closed lanes (do not reopen without cause)
- **A — All-in-one platform.** Competes against a specialized incumbent on every axis at once while
  worse at all of them, with no integrations. All-in-one is a *destination* reached after winning
  *one* thing, never the wedge.
- **B — Card-data line items.** Dead end: card networks (Visa/MC/Amex) carry merchant + total, **not
  line items**. The itemized truth lives on the **supplier invoice** (why MarginEdge/xtraCHEF are
  invoice-OCR).
- **C — Automatic recipe inference.** Clever (constrained deconvolution — NLP proposes the ingredient
  set, numerical inversion estimates portions), but **Square + MarketMan shipped it April 2026**;
  crowded, and a setup-friction (not lie-awake) pain. Closed as a standalone play. *Key carry-forward:
  forecasting/prep works on good-enough recipes + clean POS sales; you don't need penny-perfect recipe
  inversion for value.*
- **D — CV physical counts.** Contested (NomadGo: patented, ~$5.7M raised, ~7 yrs ahead) and the
  central bet was freshly falsified: **Starbucks pulled NomadGo in May 2026** — its *best-case*
  environment (uniform SKUs, enterprise budget) and it still failed. The defensible part (liquid
  levels, deformable label-less items) is a **sensing/identifiability wall ML skill doesn't dissolve.**
  The founder also deprioritized CV as a field.
- **E — Labor/scheduling forecasting.** Saturated; demand forecasting already ships inside
  7shifts/Toast/R365; the execution/trust layer is the *active 2026 battleground*, and "be simpler" is
  a quality bar, not defensible IP. **Scope note: what's closed is covers-based forecasting *for
  staffing* specifically — NOT all forecasting.** The old "forecasting = downstream feature only"
  verdict is retired.

## Cross-cutting principles (carry into every session)
1. Validate problem value + market saturation **before** deepening any solution.
2. Compete on **what you do with the data**, not on having it.
3. Don't fight the POS head-on on a layer it's absorbing.
4. **Sell the decision, not the dashboard.**
5. Go narrow (chef's knife), not all-in-one.
6. Design toward a **data-network-effect moat** (cross-restaurant priors).
7. The founder's true edge is **culinary domain knowledge**, not ML — build the thing only this founder
   can build.
8. The real commitment question is **willingness to do the unglamorous distribution/data-access work**
   (~70% of the first two years), not startup-vs-resume.
9. **Accuracy is an escapable trap — escape via target selection + data access, not modeling.**
   "Hard-tech difficulty = moat" is unreliable (the CV lesson); prefer difficulty that's *yours* to
   overcome.
10. Carry the **hierarchical/transfer-learning** pattern into the wedge — learn across many restaurants
    so a new one works on day one (test #5).

## What's still unvalidated (the open gates)
None of this validates the wedge — discovery does (`docs/discovery/discovery_and_validation`). Outstanding:
- **The lead confirm-or-kill question:** *"Do your current tools tell you 'prep 18 short ribs
  tomorrow,' or just 'Thursday will do $8,400'?"* — ask it first.
- Define the **MVP** (prep sheet, top ~15 items, POS sales + one-time recipe confirm + 1–2 exogenous
  signals).
- Resolve the **product-vs-consulting fork.**
- Design the **exogenous-signal layer** (the differentiation).
- **POS API access reality-check** (Toast/Square partner approval, cost, restrictions) — gates the
  wedge; the cross-platform moat needs access across *multiple* POS systems.
- **Data-access test:** can 3–5 of the insider's restaurants hand over real POS history + the exogenous
  signals the model needs?
- A ~90-day decision gate (one restaurant paying even $50/mo, or a credible "I'd pay" backed by data
  access + changed behavior).
