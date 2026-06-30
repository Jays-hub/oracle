# The Conceptual Spine (read before any modeling)

Everything in this project hangs on one idea. If you internalize only one page, make it this one.

## The prep decision is a newsvendor problem, not a forecasting problem
A forecast tells you what demand will *probably* be. That is not what the kitchen needs. The kitchen
needs to know *how much to make*, committed in the morning, before demand is known. Those are
different questions, and the gap between them is where almost everyone building restaurant ML goes
wrong — they ship an accurate forecast of a number nobody can directly act on.

Here is the structure. Each morning you choose a prep quantity **Q** for a dish. Then demand **D** is
revealed over service. Two things can go wrong, and they cost different amounts:

- **Overage** — you prepped more than sold. Cost per unit `Co ≈ ingredient + prep labor − salvage`.
  For perishable prep, salvage ≈ 0, so `Co` is roughly the food cost of the dish you dumped.
- **Underage** — you ran out. Cost per unit `Cu ≈ lost contribution margin (price − variable cost)
  + the intangible cost of an angry table / 86'd menu`.

The optimal quantity is **not** average demand. It is the demand quantile set by the economics of
*that specific dish*:

```
Q* = F⁻¹( Cu / (Cu + Co) )
```

`F` is the cumulative distribution function of demand. `r = Cu / (Cu + Co)` is the **critical ratio**
(critical fractile). Read it as: *of all the dollars at risk, what fraction is the cost of running
out?* You prep to that percentile of the demand distribution.

## Why this single equation is the whole product

**1. It forces a distribution, not a point.** To compute `F⁻¹(r)` you need the full predictive
*distribution* of demand, not the expected value. This is why the probabilistic turn (Phase 4) is not
"advanced sophistication" — it is the part that makes the answer *correct*. A point forecast cannot
produce the right prep quantity except in the unrealistic case where overage and underage cost the
same.

**2. It makes the output a decision (not a forecast).** The model doesn't say "demand ≈ 22." It says
"prep 26 — this dish is cheap to make and you hate running out, so target the 80th percentile." The
number finishes the decision. There is no human-judgment layer behind it the way covers→staffing has
(skill mix, callouts). This is exactly the property that lets this wedge escape the trap that killed
labor forecasting.

**3. It makes the output dollar-legible.** The critical ratio is built out of the dish's own P&L. You
can show an operator precisely why one dish preps above its average and another below it, in dollars
they already track. Accuracy improvements show up as *reduced realized over/under cost*, not an
invisible MAPE delta — which is why even a modest model beats a gut baseline perceptibly.

**4. Waste prediction falls out of the same object (the "free waste" claim, made literal).** Once you
have the demand distribution and the chosen `Q`, expected leftover is just
`E[max(Q − D, 0)]` — an integral over the same distribution you already produced. Expected stockout is
`E[max(D − Q, 0)]`. You do not build a separate waste model. Waste is a readout of the prep engine.
This is the mathematical version of the strategy doc's claim that waste is downstream of prep-demand.

**5. It encodes your culinary edge as a parameter.** A chef's tacit policy — "I never 86 the burger,
but I'd rather run out of the special than dump it" — is *exactly* a statement about `Cu/Co` per dish.
You elicit those intuitions (as the discovery onboarding in `docs/discovery_and_validation` shows) and turn them into critical ratios.
Domain knowledge becomes the algorithm. A generic POS forecast cannot do this because it never
captured the per-dish economics.

> **The one-sentence customer pitch this produces:** *"We don't just predict how busy you'll be — we
> tell you exactly how many of each thing to prep, tuned to whether running out or throwing out costs
> you more on that specific dish."* The rest of the build is earning the right to say it.

## The one caveat that changes the math: batch-prepped vs. made-to-order
The dish-count newsvendor is cleanest for **batch-prepped, commit-ahead items** — braises, sauces,
portioned proteins, par-baked items, mise with a shelf life. For **made-to-order items** assembled on
demand from shared mise (a salad, a pasta fired to order), the dish-count framing is wrong; the real
decision is ingredient **par levels**, and the newsvendor logic moves *down* to the ingredient. Which
items are which is a culinary judgment and a genuine input to model design — only the chef can sort
them, and the sort decides which math each item gets. Do not let the equation flatten this
distinction.

## How this anchors the codebase
- `forecasting/src/decision/newsvendor.py` is where `r` and `Q* = F⁻¹(r)` live. It consumes the quantile model's
  output (Phase 4) and produces the prep quantity the report layer renders.
- `forecasting/src/evaluate/` scores everything in realized dollars `Σ(Co·overage + Cu·underage)`, the objective
  this equation defines — never accuracy in the abstract.
- `config/` carries per-item `Cu`/`Co` (Phase 0), because the *economics* pick the percentile and the
  *model* only has to deliver a calibrated quantile. Keeping them in config makes the chef's policy a
  tunable, inspectable thing, not a buried constant.
