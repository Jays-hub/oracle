---
globs: "onramp/**/*.tsx", "onramp/**/*.jsx", "onramp/**/*.ts", "onramp/**/*.js", "onramp/**/*.css", "onramp/**/*.scss", "onramp/**/*.html", "onramp/**/*.svelte", "onramp/**/*.vue"
---
# Front-End & Client-UX Rules (the on-ramp website)

**Scope.** The client-facing surfaces of the on-ramp (`onramp/**` front-end assets). These encode the
on-ramp contract (`onramp/README.md`) and the precision discipline
(`onramp/plate_cost/docs/seam_and_precision.md`) as UI law. Vision: `website_vision.md`.

## Dollar-Legible Value First (the on-ramp's reason to exist)
- **Every primary view surfaces a number the operator already tracks** — a plate cost, a margin in
  dollars, money-on-the-table — large and unambiguous, above the fold. This is on-ramp contract #1
  (`onramp/README.md`): instant, dollar-legible value, no "input now, payoff later" valley.
- **Charts support the number; they never replace it.** A quadrant or trend line is context for a
  dollar figure, not a substitute. If a screen's most prominent element is not a number the operator
  cares about, the screen is wrong.
- **Speak the operator's language.** Dishes, covers, dollars, "last Saturday." Never model internals,
  schema field names, or margin-as-bare-percentage-only.

## Honest Data Presentation (never false precision)
- **Round costs to the natural grid.** Display plate costs to the nearest $0.25 or as a range
  ("$6.50–7.00"), never "$6.83". Bin `margin_pct` into labeled tiers ("<20%", "20–35%", ">35%")
  rather than raw percentages. (`seam_and_precision.md`.)
- **Numbers must reconcile by eye.** Any surface that prints both a cost and a margin must compute the
  margin from the **displayed (rounded) cost**, so `Menu − ~Cost = Margin` adds up when the chef does
  the subtraction in their head. A rounded cost beside a margin derived from the *unrounded* cost is a
  credibility leak. (This is a real regression we have already fixed once — it is now a rule.)
- **Label placeholder and sample data as such.** Demo/sample numbers (e.g. the "Marco" figures) are
  visibly marked as illustrative, never dressed as the client's validated results.
- **Provenance is reachable.** Any displayed cost can be expanded to its inputs (recipe lines, prices,
  yields). No black-box numbers — a chef must be able to audit any figure and say "yes, about right."

## Aesthetic & Simplicity
- **Clean, calm, restaurant-appropriate** — generous whitespace, one clear focus per screen, a
  restrained palette with a single accent reserved for "this is money." Not enterprise-SaaS density;
  not a consumer toy.
- **Sanity-checkable over clever.** Prefer interpretable, verifiable views ("last Saturday's covers")
  over opaque indices or composite scores a chef can't reason about.

## Trust, Transparency & Tenant Isolation
- **Single-tenant isolation is non-negotiable.** One restaurant must never see another's data. Every
  data fetch is scoped to the authenticated tenant; never rely on the client to filter.
- **Transparency is a first-class surface, not fine print.** Show what data we hold, how each number
  is derived, and what we never touch (the `_truth`/engine firewall), in plain operator language
  (`website_vision.md` §4). Offer one-click export of the client's own data in the seam's open formats.
- **Never expose firewall or internal data to the client.** Ground truth, engine internals, other
  tenants, and raw secrets never reach the browser — not in markup, not in an API payload, not in a
  bundle.

## Accessibility & Responsiveness
- **Kitchen-hostile by default.** Legible contrast, real semantic markup, keyboard navigability —
  assume glare, grease, and gloves. Meet WCAG AA contrast on any money figure.
- **Responsive.** Works on a tablet on the pass and a phone in the office, not only a demo laptop.

## Performance & Safety
- **Fast first paint, light bundle.** It is opened mid-service; quick render beats feature density.
  No heavyweight client framework where a light surface will do.
- **No secrets, no direct store access in the browser.** The front end talks only to the on-ramp API;
  it never holds a DB connection string, never opens DuckDB/Parquet directly, never embeds keys.
- **Fail legibly.** A failed load shows a calm, plain-language fallback (and, where relevant, the same
  spirit as the engine's "prep sheet must always be producible" — degrade to last-known numbers rather
  than a broken screen), never a stack trace or a blank page.
