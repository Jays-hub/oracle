---
globs: "forecasting/src/report/**/*.py", "forecasting/src/decision/**/*.py"
---
# Deployment & Serving Rules

## Decision Time vs. Inference Time
- Every feature used at serving must be available at *decision time* (prior evening, before the next day's service). Document the cutoff for each feature explicitly in the pipeline.
- Weather features must come from a *forecast* API at serving time, not observed actuals. Train on forecast-at-decision-time values to match the serving information set.
- Reservations: use the cover count available at decision time. Do not update features intra-day.

## Prep-Type Routing (batch vs. made-to-order)
- **Route every item by its chef-set `prep_type` before computing a prep quantity.** `prep_type=batch` (braises, sauces, portioned proteins, par-baked, shelf-life mise) → dish-count newsvendor `Q*=F⁻¹(q*)`. `prep_type=made_to_order` (à-la-minute dishes assembled from shared mise) → **not** a dish-count item; route to ingredient par-level logic (Phase 7 ingredient demand). The newsvendor-on-dishes math applies to batch items only — do not flatten the fork (Hard Truth #8, `forecasting/docs/data_hard_truths`).
- **`prep_type` is chef-set, never inferred.** It is a culinary judgment that changes which decision object an item gets; an item with a missing or unknown `prep_type` is flagged for chef confirmation and excluded from the dish-count prep sheet, never silently defaulted to batch.
- **The dish-count prep sheet lists batch items only.** Made-to-order items surface as ingredient par levels (Phase 7), not as a "make N portions" line — so the sheet never prints a quantity nobody would batch (e.g. "make 18 Caesars").

## The Prep Sheet Output
- The output surface is a single daily prep sheet: one row per item, columns = `[item_name, prep_qty, expected_demand, expected_waste_qty, stockout_risk_pct, Co, Cu, critical_ratio]`.
- `prep_qty` = newsvendor quantity (F⁻¹(q*)), rounded to the kitchen's natural prep unit (whole portions, half-pans, etc.).
- Always display expected overage cost and expected underage cost alongside `prep_qty` so the chef can verify the tradeoff at a glance.
- New menu items in their first 14 days must be flagged with a cold-start indicator on the sheet.

## Model Versioning & Artifact Management
- **Run tracking (from Phase 1).** Log every run to MLflow — params, metrics, realized dollar cost, and the trained artifact (cf. rule `03`). This lightweight experiment tracking applies as soon as models exist and powers the dollar-comparison discipline.
- **Model Registry, promotion & rollback (Phase 8+ only).** The three requirements below are production-governance machinery — require them only at deployment (Phase 8). Do not stand up a registry earlier; it is premature overhead the Anti-Drift Standing Order (`CLAUDE.md`) warns against.
- Every deployed model must be registered in MLflow Model Registry with: version tag, promotion date, and dollar-cost metric on the validation set it was promoted on.
- Keep the previous model version available for rollback until the new version has accumulated ≥ 14 days of live feedback.
- Never overwrite a production artifact in-place. Use versioned output paths (`models/v{n}/`).

## Calibration & Drift Monitoring
- **Calibration check** (weekly): compare predicted quantiles to realized empirical quantiles per item. Alert if calibration error on any item exceeds 0.10 (e.g., 80th-pct forecast covers actuals only 65% of the time). (This 0.10 weekly-alert threshold is intentionally tighter than the 0.15 retraining trigger in Feedback Loop & Retraining — alert first, retrain only on a larger miss; the gap is deliberate.)
- **Distribution drift check** (weekly): flag items where the 7-day rolling demand mean deviates >2σ from the training distribution mean. Drift signals a retraining trigger, not a model bug.
- **Daily logging**: actual prep qty, actual demand, realized overage cost, realized underage cost. This is the feedback loop that powers retraining.

## Feedback Loop & Retraining
- Retrain on a rolling window: add the latest 30 days; drop 30 days from the front if the window exceeds the configured max. Validate that dropping old eras doesn't degrade performance before committing.
- Trigger retraining automatically when: (a) 14-day rolling dollar cost exceeds 1.15× the validation baseline, OR (b) calibration error on any item exceeds 0.15.
- Cold-start rule: for items with fewer than 14 days of history, use the category-level hierarchical prior (Phase 6). Flag these items on the prep sheet.

## Operational Safety
- The prep sheet must always be producible, even if the model pipeline fails. Fallback = 28-day rolling mean. Log every fallback event with reason and timestamp.
- High-Cu items (Cu > 3× Co): round prep quantity to ceiling of the quantile forecast.
- High-Co items (Co > 3× Cu): round to floor.
- **Rounding precedence:** the `Cu`/`Co` skew sets the rounding *direction* (ceiling for high-`Cu`, floor for high-`Co`, nearest otherwise); the natural prep unit sets the *grid* — round to the nearest natural unit in the skew-implied direction.
- Never serve a prep quantity below the item's historical 5th percentile or above the 99th percentile without a human override flag logged to the audit trail.
