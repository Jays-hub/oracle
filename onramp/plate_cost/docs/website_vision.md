# The On-Ramp Website — Vision (above and beyond)

**Status:** north-star vision, **not a build spec.** This doc paints the *complete* client-facing
website the plate-cost on-ramp deserves — so we know what we're building toward. The actual build
stays **thin and phased** (see §8); every new step gets an adversarial review that closes on code merit
(`../../../.claude/rules/00-process.md`), while comprehension is grown separately on the `/learn` +
`docs/mastery.md` track. Read the two disciplines below before reading the vision, because they bound
it.

**Part of the plate-cost docs.** Index: [plate_cost_overview.md](plate_cost_overview.md).
Governance: `../CLAUDE.md` · durable on-ramp mandate: `../../README.md` · full-stack rules:
`../../../.claude/rules/05-fullstack-architecture.md`, `06-frontend-ux.md`, `07-backend-api.md`.

---

## Two disciplines that bound this vision

1. **North star vs. phased build.** Everything here is the destination. We build the smallest slice
   that delivers an instant, dollar-legible payoff, then earn each addition. A complete vision is not
   a license to build it all at once — it is a map so the thin slice points the right way.
2. **Provisional product, durable slot.** The *plate-cost framing* of these screens is provisional
   (discovery may reshape it). What is **durable** is the website's role as the on-ramp's face: the
   onboarding flow, the data-capture surfaces, the trust/transparency story, and the seam-correct
   storage underneath. Build the durable parts to last; build the plate-cost-specific views to be
   swapped. Don't weld the chrome to today's product.

---

## 1. The premise

Today the "instant value" of the on-ramp happens **once**, live in a chef sitdown: we show real plate
costs and a menu-engineering grid on a laptop, in the room. The website turns that one-time reveal
into a **living surface the operator returns to** — and, critically, into a surface we can *show a
prospective client* to make the value legible in sixty seconds without us in the room.

The website is the on-ramp's storefront and its data-capture funnel at once. It must do exactly what
the on-ramp contract (`../../README.md`) demands: deliver instant, dollar-legible value; add no daily
work; and capture the engine's data legs as a side effect of delivering that value.

**The one-sentence pitch the site must make for itself:** *"Connect your POS and confirm your recipes
once — here is exactly what every dish costs you, which dishes make your money, and which quietly lose
it."*

---

## 2. The client's journey (the story the site tells)

The site is organized as a narrative, not a feature list. A client moving through it should feel a
single arc:

1. **"Here's your menu, as we found it."** Their dishes, pulled from the POS export — familiar
   ground, zero typing to start.
2. **"Here's what each plate actually costs you."** The plate cost per dish, in rounded, trustworthy
   dollars. The first payoff: a number they already half-know, now exact.
3. **"Here's where your money is."** The popularity × margin grid — Stars, Plowhorses, Puzzles, Dogs
   — the menu-engineering reveal that reframes the whole menu in one picture.
4. **"Here's the money on the table."** Specific, dollar-legible opportunities: a mispriced star, a
   high-volume plowhorse a small reprice would fix, a dog to cut.
5. **"Here's what we never touch — and where this goes next."** The transparency view (what data we
   hold, how it's used, the firewall) and the bridge: the same data is what will soon tell them *how
   much to prep* and cut their waste. The on-ramp becomes the on-ramp.

Every screen answers one question in the operator's own language (dollars, dishes, covers) — never in
ours (margins-as-percentages-only, model internals, schema names).

---

## 3. Site map (the complete surface)

Grouped by the journey. Phase tags in §8 say which exist when.

**A. Onboarding / capture (the durable funnel)**
- **Connect your data** — POS export upload (CSV drop, later a POS integration); the recipe-sitdown
  workspace for confirming BOM on ~15–25 items. This is the *single act* that captures the sales +
  BOM legs. Designed so a chef finishes it in one sitting, with a progress meter and "good enough to
  show value" threshold made visible.
- **Ingredient & price setup** — seed prices (rough chef sense or a one-time invoice snapshot);
  later, invoice ingestion (Phase 2) lands here.

**B. The value surfaces (the reveal)**
- **Dashboard** — the at-a-glance home: total covers, menu-wide margin health, top 3 opportunities in
  dollars, anything that changed since last visit. Dollar-legible above the fold.
- **Menu / dish list** — every dish with its rounded plate cost, menu price, and reconciled margin
  (`Menu − ~Cost = Margin`, by eye — see precision discipline). Sortable by what loses money.
- **The Grid** — the popularity × margin quadrant (Stars / Plowhorses / Puzzles / Dogs), the
  signature view. Each dish is a dot; click to drill into its recipe and cost breakdown.
- **Dish detail** — the plate-cost breakdown line by line (ingredient → qty → as-used cost), so a
  chef can sanity-check every number and trust the total.

**C. Insight & alerting (the second hook, Phase 3)**
- **Insights / opportunities** — plain-language, dollar-quantified findings ("Beef +16% this week → 3
  dishes affected → short rib is now your thinnest-margin entrée"). Each is an action, not a chart.
- **Price trends** — per-ingredient movement once invoices flow.

**D. Trust & handoff (the differentiator)**
- **Your data** — the transparency view: exactly what we hold, how each number is derived, what we
  *never* touch (the `_truth`/engine firewall, framed for a non-technical operator), and one-click
  export of their own data. Trust is a feature here, not fine print.
- **What's next** — the forecasting bridge: a tasteful "coming soon" that shows the prep-sheet payoff
  the captured data unlocks, so the operator sees the on-ramp as a doorway, not a destination.

**E. Account**
- Auth, restaurant profile, team access, billing (when there is something to bill). Single-tenant
  isolation is non-negotiable from day one (one restaurant must never see another's numbers).

---

## 4. The data story, made visible (transparency as a feature)

Because the site exists partly *to show clients what we do with their data*, transparency is a
first-class surface, not a policy page:

- **Provenance on every number.** A plate cost can be expanded to its inputs: which recipe lines,
  which prices, which yields. No black boxes — a chef can audit any figure.
- **"What we collected" ledger.** A human-readable list of the data legs we hold (sales export, BOM,
  prices) and *why each is needed* — phrased as the value it powers, not the field it fills.
- **The firewall, in plain English.** We show that scoring/ground-truth data (`data/_truth/`) and the
  forecasting internals are walled off from anything that touches their live numbers — the same
  raw-vs-truth discipline that makes the engine verifiable, told as a trust story.
- **Their data is theirs.** One-click export of everything we hold for them, in the same open formats
  the seam uses (CSV/Parquet). No lock-in as a selling point.

---

## 5. Aesthetic & UX direction

- **Clean, calm, restaurant-appropriate.** Not enterprise-SaaS density; not a consumer toy. Think a
  well-set table: generous whitespace, one clear focus per screen, a confident type scale, a restrained
  palette with a single accent for "this is money."
- **Dollar-legible at a glance.** The most important number on any screen is a dollar figure the
  operator already tracks, large and unambiguous. Charts support the number; they never replace it.
- **Honest precision.** Rounded costs ($0.25 grid or ranges), binned margin tiers, labeled
  placeholder/sample data. The numbers must *reconcile by eye* (see precision discipline below). A
  confidently-wrong figure loses the chef on day one.
- **Sanity-checkable.** Prefer "last Saturday's covers" over an opaque index. A chef should be able to
  look at any view and say "yes, that's about right" — that reaction is the product.
- **Fast and light.** It will be opened on a tablet on a pass or a phone in an office. Quick first
  paint, responsive layout, no heavyweight client bundle.
- **Accessible.** Legible contrast, keyboard navigability, real semantics — a kitchen is a hostile
  viewing environment (glare, grease, gloves).

---

## 6. The above-and-beyond: the forecasting bridge

This is what makes the site *more* than a menu-analytics tool and keeps it honest about the company's
actual end. The website should make the operator feel the next step before we sell it:

- A tasteful **"What your data unlocks next"** panel that previews the prep-demand payoff: *"You've
  already given us the sales history and recipes a prep forecast needs. Soon this becomes a daily
  prep sheet that tells you how much to make — and stops the waste you can't currently see."*
- The framing matters: the prep engine is the **end**, the website is the **means**. Elevating the
  website's polish does not move the moat (`../../CLAUDE.md`, Anti-Drift). The bridge panel exists to
  point at the moat, not to substitute for it.

---

## 7. Tech posture (pointer, not spec)

The full rules are in `.claude/rules/05–07`. In brief, and binding:

- **Storage = DuckDB-over-Parquet** (decided 2026-06-25, `../../../docs/common_base_reconciliation.md`).
  The website's persistence and the engine's input are the same `data/raw/**` artifact; the file
  boundary stays the firewall. No premature server-class DB. (If "client-facing" ever means a hosted,
  many-tenants-writing-concurrently service, that is the explicitly-deferred server-DB decision —
  revisit it then, recorded, gated.)
- **Seam-correct, no coupling.** The backend writes captured legs to `data/raw/` **only through**
  `../../../schemas/seam.py`; it never reads `data/_truth/`, never reads the engine's
  `interim/`/`processed/`, and never imports `forecasting/`. The on-ramp owns its own store helper.
- **Compute stays pure.** The plate-cost math in `../src/` stays framework-agnostic and unit-tested;
  the API is thin glue over it; the front end is presentation. A web layer must never become the only
  way to run the compute.
- **Secrets in env, never committed.** Connection strings and keys live in config/env.

---

## 8. Phased build roadmap (thin first)

A map from today's CLI-grade Phase-0 tool to the full vision. Each phase is a separate gated step; do
**not** batch them.

| Site phase | Slice | Delivers | Durable vs. provisional |
|-----------|-------|----------|-------------------------|
| **W0** | Read-only reveal | A single hosted page that renders the existing plate-cost grid + dish list for one restaurant, from the on-ramp's source inputs (the same chain `src/run.py` costs). The seam `data/raw/` deliberately carries only the BOM + sales legs the engine needs — not menu or unit prices — so it can't reconstruct margins; W0 reads source data, not the seam. No auth, no editing. The "show a client in 60s" artifact. | Chrome durable; plate-cost views provisional |
| **W1** | Capture funnel | POS-export upload + recipe-confirmation workspace; writes the sales + BOM legs to `data/raw/` through `schemas/`. The one-act capture, now self-serve. | **Durable** (this is the on-ramp funnel) |
| **W2** | Account + persistence | Auth, single-tenant isolation, DuckDB-over-Parquet store wired in, "your data" export. | **Durable** |
| **W3** | Insight & price | Invoice ingestion (post-gate), price-trend alerts, the opportunities surface. | Mixed |
| **W4** | Transparency + bridge | The full "your data" transparency view and the forecasting "what's next" panel. | Durable framing, provisional content |

> **The map now extends past W4.** W0–W3 are built and reviewed; the approved execution map from
> this proof of concept to a full production service — a designated application database, real
> identity, hosting, the public storefront + design/accessibility pass, seam-level tenancy
> (phases W5–W10) — is
> [website_production_overview.md](website_production_overview.md) (2026-07-13). This section stays
> as the original thin-first record; the production overview governs the phases beyond it.

**W0 is the honest next slice** — it reuses the `src/` compute chain already built and produces the
client-showable artifact with the least new code. (W0 *reads* the on-ramp's source inputs, not the
seam: the `data/raw/` export carries only BOM + sales, which can't reconstruct margins — reading the
seam back is W2's job, once there is captured tenant data to read.) It is also the slice that proves
the thin-presentation-over-pure-compute layering (rule 05) before any of the heavier funnel work.

---

## 9. What this vision is *not*

- Not a mandate to build a multi-tenant hosted platform now. W0 is one page over existing data.
- Not a reason to deepen plate-cost before discovery validates it. The grid is the hook; resist
  turning it into a full menu-analytics suite (the Anti-Drift trap, `../CLAUDE.md` callout #5).
- Not a relocation of the moat. The defensibility still lives in `forecasting/`. This site is the
  means; the prep engine is the end.
