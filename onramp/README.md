# onramp/ — The On-Ramp Service (a durable peer)

## Why this is its own peer, not a sub-folder of the engine

The startup has **two durable parts**, and this is one of them:

- `../forecasting/` — the **core engine**: prep-demand forecasting under a waste framing. The moat
  and the *end*.
- `onramp/` (this peer) — the **on-ramp service**: deliver instant, dollar-legible value to an
  operator *fast*, and in the very same act capture the data the engine needs to switch on.

Both write to / read from the platform-shared store at `../data/` (the seam: `../data/CONTRACT.md`).

## The durable function vs. the provisional product (read this twice)

The distinction this peer exists to make explicit:

- **The on-ramp *function* is not disposable.** Every operator must cross *some* low-friction,
  instant-value bridge before the forecasting engine has any data to forecast on. There is no path
  to the engine that doesn't run through an on-ramp. The need for an acquisition + data-capture rail
  is permanent and load-bearing — it is half of how this company actually reaches a kitchen.
- **The current *product* (`plate_cost/`) is provisional.** Plate-cost + menu-margin is the first
  bet on *how* to deliver the on-ramp function. Customer discovery may keep it, reshape it, or
  replace it with a different instant-value hook (e.g. an invoice-price monitor, a labor-cost
  snapshot, an 86/lost-sales tracker). If the product changes, this peer stays; we swap the child.

> **One sentence:** the on-ramp is a permanent role in the architecture; `plate_cost/` is today's
> casting for that role.

This is a deliberate correction to the earlier "disposable capture rail" framing. The *rail as a
specific tool* is thin and replaceable; the *rail as a function* is structural. Build the current
product thin (don't sink cost into something discovery might discard) **and** treat the on-ramp
slot as first-class (don't under-resource the only bridge onto the engine).

## What an on-ramp implementation must do (the contract for any product in this slot)

Whatever product fills this peer, it must satisfy all three:

1. **Instant, dollar-legible value** — a payoff the operator feels in the first session, mapped to a
   number they already track (a margin, a price spike, a lost-sale). No "input now, payoff later"
   valley.
2. **No added daily work** — it rides on data already flowing (POS export, invoices) plus at most a
   one-time setup act. The "easy transition / no new ritual" gate (`../docs/strategic_context.md`)
   applies here as hard as it does to the engine.
3. **Captures ≥1 engine data leg as a side effect of delivering value** — the act that produces the
   value and the act that captures the data are the *same act*. This is what makes the on-ramp
   self-justifying and turns onboarding friction into the first payoff.

The four data legs the engine ultimately needs: **sales history, BOM, invoice/price history,
86/stockout log.** `plate_cost/` captures the first three in one recipe sitdown; the fourth stays a
separate tiny habit (the 86-tap tracker). A future on-ramp product is judged partly by which legs it
captures.

## Current contents

```
onramp/
├── README.md          # this file — the durable on-ramp mandate
└── plate_cost/        # current implementation (provisional); governed by plate_cost/CLAUDE.md
```

## Discipline (carried from the strategy docs, re-scoped to the durable function)

- **Thin product, durable slot.** Provisional implementation, permanent role. See `plate_cost/CLAUDE.md`
  callout #1.
- **One sharp on-ramp at a time** — win the slot with a single chef's-knife tool, not a scatter of
  half-built thin features.
- **The on-ramp is the means; the prep engine is the end.** Elevating the on-ramp's importance does
  not relocate the moat. The defensibility still lives in `../forecasting/` (the prep forecast,
  exogenous fusion, cross-restaurant pool). If a session drifts into polishing the on-ramp before a
  critical ratio runs on a quantile model, name the drift (Anti-Drift Standing Order, `../CLAUDE.md`).
