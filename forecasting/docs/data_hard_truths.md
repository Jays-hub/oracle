# Restaurant-Data Hard Truths

The things that, spoken fluently, mark you as someone who understands this industry's data rather than
someone applying generic ML. Most are baked into the simulated data (`forecasting/docs/simulated_data`) on purpose, so you'll
hit them whether you plan to or not. Drill these — they recur across phases and they're exactly what an
operator probes for when deciding whether to trust you.

1. **Censored demand is the silent killer.** Sold-out ≠ low demand; it's right-censored demand. Train
   naively on observed sales and you systematically under-forecast your *most popular, highest-margin*
   items — in a self-reinforcing loop, because under-forecasting causes more stockouts. Capture
   stockout events from day one (Phase 1); unconstrain before you trust popularity (Phase 3). The
   correction data evaporates every morning the board gets wiped — it is physically unrecoverable
   later, which is why capture cannot wait.

2. **The sales signal is polluted.** Comps, staff meals, voids, and promo giveaways sit in the POS but
   aren't organic demand. Some are flagged, some aren't. Clean deliberately (Phase 2); a quietly
   polluted target poisons everything downstream.

3. **Counts are not Gaussian.** Demand is small non-negative integers, overdispersed (variance > mean),
   and zero-inflated for rare items. Use Poisson / Negative Binomial / Tweedie, never OLS. And MAPE is
   broken when demand is zero or tiny (it explodes or is undefined) — use MASE and, for the
   distributional work, pinball loss.

4. **You forecast at decision-time information.** You may only use what existed at the moment of the
   prep commit. The sharpest trap: backtest with the weather **forecast** available that morning and
   reservation depth **as known then** — never realized actuals. Train on actuals and you report an
   accuracy you can never reproduce in production. This invalidates more demos than anything else; the
   simulator ships two weather files precisely to keep you honest.

5. **The decision is a quantile, not a mean.** Per-dish newsvendor critical ratio `Cu/(Cu+Co)`. The
   economics pick the percentile; the model only has to be *calibrated*. This is the keystone
   (`forecasting/docs/conceptual_spine`) and the reason a point forecast can't produce the right prep number.

6. **Feature relevance beats feature volume.** One relevant exogenous signal (the concert, the warm-day
   delta, the forward book) can outweigh 100× more POS transaction rows. This is the entire basis for
   not losing a pure-data-volume fight to the POS — the binding signal lives *outside* their data.

7. **Pooling solves cold-start; data access is the moat, not the algorithm.** Hierarchical/embedding
   methods are well-understood and copyable. What's hard to copy is *assembling the multi-platform
   pool* — and that's a distribution/sales problem, not a modeling achievement. Build pooling because
   it genuinely helps day-one cold-start; don't tell yourself the math is the moat.

8. **Made-to-order vs. batch-prepped is a modeling fork.** Newsvendor-on-dishes for batch, commit-ahead
   items; par-levels-on-ingredients for à-la-minute items built from shared mise. A culinary judgment —
   only the chef can sort the menu — that changes which math each item gets.

9. **Structural breaks lurk in the history.** Menu changes (~quarterly here), price changes,
   renovations, the pandemic. Old data can be actively misleading; tag by menu era and don't train
   blindly across breaks.

10. **Calibration is a credibility instrument.** "90% confident → right 90% of the time" is something a
    chef can check and trust, and conformal prediction makes it defensible. A confidently
    *miscalibrated* distribution is worse than an honest point estimate — the chef trusts the quantile
    and gets burned.

## Two domain economics worth stating precisely (you'll be asked)
- **`Co` (overage)** ≈ food cost + prep labor − salvage. For perishable prep, salvage ≈ 0. A "Sunday
  special" that moves yesterday's surplus is partial salvage you fold in.
- **`Cu` (underage)** ≈ contribution margin (price − variable cost) + the intangible angry-table cost.
  At the *ordering* horizon there's a second `Cu`: the margin-killing emergency retail run when you run
  short. Same logic, longer clock.

These ten are the difference between a forecaster and a forecaster who understands kitchens. When an
operator hears you name #1 and #4 unprompted, you've earned the conversation.
