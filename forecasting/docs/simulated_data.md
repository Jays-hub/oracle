# Simulated Data Specification

This is the heart of the simulation. The goal is to generate synthetic data that looks like a real
restaurant's **first data dump** — as messy, polluted, and censored as what you'd actually receive
from "Marco" via his bookkeeper — while *you* secretly hold the ground-truth generative process so
you can verify every model you build.

## The core discipline (do not violate)
- **`data/raw/`** = "what the restaurant hands you." Messy. This is the ONLY thing models, cleaning,
  and feature code are allowed to read.
- **`data/_truth/`** = the generator's ground truth (true demand before stockouts, which item-days
  were censored, the real recipes, injected spoilage, the generative knobs). Used **only** by
  `forecasting/src/evaluate/` for scoring. It is never a feature, never joined into training, never peeked at
  while modeling. If `_truth/` leaks into a model, every result it produces is a lie.

Why this matters: without ground truth you can *fit* models but never *verify* them. With it, you can
ask the questions that actually teach you the domain — did my unconstraining recover true demand? are
my 90% quantiles right 90% of the time? does my waste residual match the spoilage I injected? That
verification loop is most of the learning value of the whole project.

## What a real first dump actually contains (and what it's missing)
Anchored to the discovery onboarding conversation (`docs/discovery/discovery_and_validation`). You receive:
1. A **Toast line-item sales export** (~2.5 years), via the bookkeeper — item-level, timestamped, and
   polluted with comps/staff meals/voids, spanning ~4 menu changes a year.
2. A **Resy reservation export** (CSV) — the forward book, with no-shows and cancellations, and
   **walk-ins absent** (so it under-counts covers, badly on weekends).
3. **Supplier invoices** — lumpy purchases in as-purchased units, delivery dates ≠ usage dates.
4. **Hand-confirmed recipes** for ONLY the ~15 big items — approximate, half "by feel," mixed units.
5. Critically, **no historical 86/stockout log.** The board got wiped every morning. So your most
   popular dishes' true demand is invisible in the history — this is the censoring problem, and the
   simulator must bake it in. (A go-forward `eightysix_log` starts being captured from day one.)
You also assemble two external feeds the POS can't see:
6. A **weather** series — and you must keep the *forecast* separate from the *actuals*.
7. A local **events** calendar (the amphitheater).

---

## Tables to generate — `data/raw/` (the messy version models read)

### `pos_sales.csv` — the Toast line-item export
One row per item sold per check.

| column | type | notes / the realism |
|---|---|---|
| `check_id` | str | groups items on one ticket |
| `line_id` | str | unique per row |
| `business_date` | date | service date |
| `sold_at` | datetime | timestamp; daypart (lunch/dinner) is *implied*, not labeled |
| `item_name` | str | **drifts across menu eras** ("Short Rib" → "Braised Short Rib" → "SR"); occasional typos |
| `category` | str | inconsistent labels; some blank |
| `menu_price` | float | **changes over time**; promo prices appear |
| `qty` | int | usually 1; small integers |
| `modifiers` | str | free text, often empty; noise |
| `discount_amount` | float | nonzero on comps/promos |
| `comp_flag` | bool/null | **sometimes set, sometimes null even when comped** (partial flagging) |
| `void_flag` | bool | voided line; may have negative/zero effective qty |
| `server_id` | str | mostly irrelevant; staff-meal rows cluster on certain ids |

### `reservations.csv` — the Resy export
| column | type | notes |
|---|---|---|
| `reservation_id` | str | |
| `created_at` | datetime | when the booking was made (a leading indicator) |
| `reserved_for` | datetime | the covered slot |
| `party_size` | int | |
| `status` | str | `seated` / `no_show` / `cancelled` (no-shows ~10–15%) |
| `source` | str | resy/phone/walk-in-conversion; **pure walk-ins are NOT here** |

### `invoices.csv` — supplier invoices
| column | type | notes |
|---|---|---|
| `invoice_id` | str | |
| `supplier` | str | US Foods / produce purveyor |
| `delivery_date` | date | **lags or leads usage** — not when it was consumed |
| `product_desc` | str | as-purchased naming, inconsistent ("Beef Short Rib BNLS" vs "Short Ribs") |
| `pack_size`, `unit` | str | cases, lbs, each — **as-purchased units, not recipe units** |
| `qty_ordered` | float | lumpy (order Sun & Wed) |
| `unit_cost`, `ext_cost` | float | prices fluctuate week to week |

### `recipes_stated.csv` — the chef's hand-confirmed BOM (big items only)
| column | type | notes |
|---|---|---|
| `dish_name` | str | ~15 items only |
| `ingredient` | str | |
| `qty_per_portion` | float/null | **approximate; some missing; "by feel" rows noisier** |
| `unit` | str | mixed (oz, g, "pinch") |
| `prep_type` | str | `batch` / `made_to_order` — **the modeling fork; only the chef can set it** |
| `confidence` | str | `spec_sheet` / `by_feel` |

### `weather_actuals.csv` and `weather_forecast.csv` — TWO files on purpose
Actuals: `date, temp_high, temp_low, precip_mm`. Forecast: same columns **plus** `forecast_issued_on`
(the morning the prep decision is made), and the values **differ from actuals**. You will train and
backtest on the *forecast* version only. Training on actuals reports an accuracy you can never
reproduce in production — this is the single most common way demos cheat.

### `events.csv` — the amphitheater calendar
`event_date, venue, start_time, expected_attendance_band` (low/med/high). Drives early-evening
spikes on nearby concert nights.

### `eightysix_log.csv` — go-forward stockout capture (starts ~empty)
`business_date, item_name, time_86d`. Historical rows are absent (the censoring); this table fills in
only for the simulated "going forward" window, so you can *test* unconstraining against a period where
you also know the truth.

---

## Tables to generate — `data/_truth/` (hidden; scoring only)

- `truth_demand.csv` — **true latent demand** per item per daypart per day, *before* capacity capping.
  This is what `pos_sales` would have shown if nothing ever sold out.
- `truth_stockouts.csv` — which item-days were capped, the cap, and the true (uncensored) demand.
- `truth_recipes.csv` — the **real** per-portion BOM. The gap vs `recipes_stated` *is over-portioning*,
  not model error.
- `truth_spoilage.csv` — injected spoilage per ingredient per period (so the waste residual has an
  answer key).
- `truth_params.yaml` — every generative knob (base rates, day-of-week and seasonal multipliers, event
  multipliers, weather sensitivities, censoring thresholds, pollution rates). The "answer key" to the
  whole world.

---

## The generative process (what `forecasting/src/simulate/` implements)
Build the world truth-first, then degrade it into the messy export.

1. **Latent demand.** For each item × daypart × day, draw demand from a **Negative Binomial** (small
   integers, overdispersed, zero-inflated for rare items). The mean is
   `base_rate × dow_factor × season_factor × trend × menu_era_factor × exo_multiplier`, where
   `exo_multiplier` folds in weather (with the "first warm day after cold" *delta* effect), events
   (early-evening concert lift), and a reservation-driven component. Write this to `truth_demand`.
2. **Censoring (the silent killer).** For popular items on peak days, impose a kitchen **capacity cap**.
   Observed sales = `min(true_demand, cap)`. Where capped, record it in `truth_stockouts` and (for the
   go-forward window only) in `eightysix_log`. This is what makes the history systematically
   under-represent your best dishes.
3. **Pollution.** Inject ~3–6% of rows as comps, staff meals, and voids. Flag *some* (`comp_flag=True`,
   discounts) and leave *some* unflagged. Staff meals cluster on certain `server_id`s and dayparts.
4. **Menu eras.** Every ~quarter, shift the menu: items enter/leave, names drift, prices step. Tag the
   truth with era boundaries (so you can later verify your menu-era detection).
5. **Reservations.** Generate a forward book correlated with — but not equal to — true covers: ~60%
   coverage on weeknights, ~50% on weekends (the rest walk in and never appear), plus no-shows and
   cancellations. The book leads demand but imperfectly.
6. **Invoices.** Run a noisy, lumpy ordering policy (order Sun/Wed) on top of true ingredient depletion
   (= Σ over dishes of true_demand × *true* recipe qty), with deliberate over/under-ordering and
   shelf-life spoilage. Spoilage goes to `truth_spoilage`; the purchases (in as-purchased units) go to
   `invoices`.
7. **Recipes.** Hold the true BOM in `truth_recipes`; emit a degraded `recipes_stated` with portion
   error, missing rows, and higher noise on `by_feel` items.

**Config-driven.** All knobs live in `config/sim.yaml` and are echoed to `truth_params.yaml`. Seed
everything for reproducibility.

## Realism checklist (the data is "good enough" when it has all of these)
- Counts are small integers, overdispersed, zero-inflated — NegBin, never Gaussian.
- Day-of-week + annual seasonality + slow trend + **menu-era regime shifts**.
- **Censoring baked in** on popular items on peak days; the correction data absent from history.
- 3–6% pollution (comps/staff/voids), **partially** flagged.
- Item-name drift, price steps, items entering/leaving at ~quarterly menu changes.
- Reservations correlated-but-imperfect, no-shows/cancellations, walk-ins excluded, weekend coverage
  lower.
- Weather **forecast ≠ actuals** (two files), forcing decision-time discipline.
- Events drive early-evening spikes on nearby concert nights.
- Invoices lumpy, lagged, as-purchased units; spoilage injected.
- Recipes approximate; `by_feel` items noisier; stated ≠ true.

## Intended defect — no unit-normalization rule (by design)
The raw recipes (`recipes_stated`: mixed `oz`/`g`/"pinch") and invoices (as-purchased units — cases,
lbs, each) carry **deliberately unconverted, mixed units**, and the project deliberately imposes **no
ingestion or feature rule that canonicalizes units before a model sees them.** This is an *intended
defect*, not an oversight. In a real first data dump there is never a clean-unit case that arrives
pre-converted — the messy units come in with everything else, and turning as-purchased and "by feel"
units into a coherent base unit is real work done *inside* the build (the recipe→ingredient→waste close,
Phase 7), where conversion factors and yield/shrink coefficients are applied explicitly. Do **not**
"fix" this by adding a rule that assumes clean or pre-normalized units; confronting the conversion is
part of what the simulation exists to teach.

## How each phase uses this (the payoff)
The simulation is built so every later phase has an answer key:
- Phase 1 baselines/backtest run on `pos_sales`; the dollar metric needs `Cu`/`Co` from config.
- Phase 2 cleaning is *verifiable* — did you strip the pollution `truth_params` says you injected?
- Phase 3 unconstraining is *verifiable* — does recovered demand match `truth_demand` on capped days?
- Phase 4 calibration is *verifiable* — do empirical coverage and the realized newsvendor cost match
  what the true distribution implies?
- Phase 7 waste close is *verifiable* — does your residual match `truth_spoilage`?
Without `_truth/`, none of these checks exist and you're flying blind. That's the entire reason the
discipline in this doc is non-negotiable.
