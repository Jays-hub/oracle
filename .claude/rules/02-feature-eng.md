---
globs: "forecasting/src/features/**/*.py", "forecasting/notebooks/*.ipynb"
---
# Feature Engineering Rules

## Temporal Integrity — No Leakage (Highest Priority)
- All features must be computable from information available at *decision time* (prior evening, before service). Never use same-day actuals as inputs.
- Lag features: minimum lag = 1 day. Use lag-7 for weekly seasonality, lag-1 through lag-7 for short-term trend. Lag-0 (current day) is forbidden.
- Rolling statistics: always apply `.shift(1)` before `.rolling()` to exclude the current observation from the window.
- After building the feature matrix, assert `max(feature_date) < min(target_date)` as a leakage canary. This check must run in CI.

## Required Feature Groups
- **Calendar**: `day_of_week`, `is_weekend`, `week_of_year`, `month`, `is_holiday`, `days_until_holiday`, `days_since_holiday`.
- **Demand lags**: `lag_1`, `lag_7`, `lag_14` per item; `rolling_mean_7`, `rolling_std_7`, `rolling_mean_28`. Compute per `(item_id, service_period)`.
- **Menu era**: integer `era_id` per item (from ingestion boundary detection); `era_days_elapsed` (recency within era). Models trained on cross-era data should include era as a categorical feature.
- **Price & promotion**: `current_price`, `price_change_flag` (bool, lag-1), `is_promotion_day`.
- **Service context**: `service_period` (lunch/dinner/brunch), `cover_count_forecast` (reservations at decision time — not updated same-day).
- **Exogenous** (Phase 5+): weather features must come from a *forecast* at decision time, not observed actuals. Train and serve on the same information set.

## Pipeline Architecture
- Implement all feature logic inside a `FeaturePipeline` class with `.fit(train_df)` / `.transform(df)` methods.
- Training statistics that inform features (target-encoding means, era boundaries, rolling baselines) must be fit on the training split only and stored on the pipeline object. Never recompute on the full dataset.
- Log feature cardinality and null rates after every `.fit()` call.

## Encoding
- Do not one-hot encode high-cardinality IDs (e.g., `item_id` with 50+ levels) — use LightGBM's native categorical support (`dtype='category'`) or target-encode fitted on train only.
- Ordinal/cyclical calendar features (day_of_week, month): for the GBM-first stack, prefer LightGBM native categoricals (or plain integers) — trees split on thresholds and gain little from cyclical encoding, and a named day is easier for a chef to sanity-check. Reserve `sin/cos` transforms for a linear or neural layer, where cyclical distance actually matters.

## Feature Selection
- After each major feature addition, run a feature importance pass (LightGBM `feature_importances_`). Drop features with zero importance across 3+ folds before adding more complexity.
- Prefer interpretable features that a chef could sanity-check (e.g., "last Saturday's sales") over opaque interactions.
