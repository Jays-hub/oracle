---
globs: "forecasting/src/models/**/*.py", "forecasting/src/evaluate/**/*.py"
---
# Model Training Rules

## Primary Objective — Dollar Cost, Not Accuracy
- The evaluation metric is realized dollar cost: `Σ (Co·max(0, prep−demand) + Cu·max(0, demand−prep))` per item per day. Report this first.
- MAPE, RMSE, and MAE are diagnostics only — never the decision criterion for shipping a model.
- A new model layer ships ONLY if it reduces dollar cost vs. the prior baseline on held-out data.

## Cross-Validation — Rolling Origin (Walk-Forward)
- NEVER use random K-Fold or stratified K-Fold on time-series data. This breaks temporal ordering and leaks future information into training, invalidating all metrics.
- Use rolling-origin (walk-forward) CV: expand the training window by one period per fold; the test window is always strictly after training.
- Minimum 4 folds. Report dollar cost, pinball loss, and WAPE per fold; report mean ± std across folds.

## Forecasting Metrics
- **Pinball loss** at the item's critical-ratio quantile q* = Cu/(Co+Cu) is the primary probabilistic metric.
- **Calibration**: for a q-quantile forecast, ~q% of actuals should fall below. Plot reliability diagrams per item on the holdout set.
- **WAPE** (weighted absolute percentage error) and **bias** (mean signed error) for point forecasts. Persistent positive bias = chronic over-prep; negative = chronic stockouts.
- ROC-AUC, precision, recall, and accuracy are classification metrics and must not be used here.

## Model Training Standards
- Log every run to MLflow: parameters, hyperparameters, all metrics above, per-fold results, and the trained artifact.
- Use `random_state=42` for all stochastic components (LightGBM seed, data splits).
- Fit all scalers, encoders, and imputers ONLY on the training split. Transform val/test with pre-fitted objects. Never re-fit on test.
- For Poisson/Tweedie objectives: verify predicted mean vs. actual mean per item after training. Large per-item bias = missing era features or censored-demand contamination.
- For quantile models: train a separate model per quantile OR use LightGBM's multi-quantile objective. Do not derive quantiles by adding/subtracting residual std from a point forecast.
- **Quantiles must not cross.** Independently-fit quantiles are not guaranteed monotone; enforce non-decreasing quantiles per item-day — either with a monotone/joint multi-quantile model or by post-hoc rearrangement (sort / Chernozhukov rearrangement) — *before* any `F⁻¹(q*)` read-off, and run the calibration/coverage checks on the monotonized quantiles. A valid inverse-CDF is monotone by definition: a higher targeted service level must yield a higher (never lower) prep quantity.

## Newsvendor Integration
- The model's job is to produce a demand *distribution*, not just a point estimate. Minimum deliverable per item per day: mean + std (parametric) OR a set of quantile forecasts covering [0.10, 0.25, 0.50, 0.75, 0.90, q*].
- Prep quantity = F⁻¹(q*) where q* = Cu/(Co+Cu) for each item. This is computed in `forecasting/src/decision/`, not inside the model.
- Validate prep levels against `data/_truth/` on the holdout set: the empirical underage rate should approximate (1 − q*) per item.

## Required Baselines (Must Be Beaten Before Adding Complexity)
1. Same-day-last-week (naive lag-7).
2. 28-day rolling mean.
3. Chef's gut proxy: rolling mean rounded to nearest 5.

All three must be computed and their dollar costs logged before any ML model is evaluated. If a new model doesn't beat all three baselines in dollar cost, investigate the signal before adding more complexity.
