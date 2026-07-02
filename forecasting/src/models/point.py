"""Phase-2 point model — global LightGBM across all items (Poisson objective).

GlobalLGBMModel: one model, item_id as a LightGBM native categorical feature,
trained on the cleaned demand series from Phase 1/2. Matches the BaseBaseline
fit/predict interface so it plugs into the existing backtest harness without change.

Why a global model (not 11 per-item models):
  - Each per-item/period series has ~900 observations — thin for a GBM.
  - Items share structure (Friday lifts, era transitions, seasonal arc); the global
    model borrows that signal across items. Per-item models can't.
  - This is the "many short related series → global GBM" regime from rule 03.

Why Poisson objective:
  - Demand is a non-negative integer. OLS assumes additive Gaussian noise and can
    predict negative values. Poisson/Tweedie objectives respect the count structure
    and constrain the log-link prediction to non-negative values.
  - Overdispersion (variance > mean) is handled by the Poisson's log-link; Tweedie
    generalizes it further. For P2 Poisson is the correct baseline; Tweedie is a P3+
    upgrade if calibration shows systematic over-dispersion.

Known limitation -- lag features are skewed in a BLOCK backtest (P2_review.md MAJOR-3):
  - RollingOriginBacktest scores a whole multi-week test window in one predict() call.
    FeaturePipeline only has TRAINING history to look back on, so a test day deep in
    the window has no revealed prior-test-day actuals -- lag_1 is ~96% NaN, lag_7 ~75%,
    by the end of a 28-day block. This is symmetric across baselines and the GBM (the
    naive baselines degrade to training-only info the same way), so point_floor.py's
    dollar comparison stays fair -- if anything conservative -- but it understates a
    properly-served day-ahead model (lead_time_days=1 is the real product horizon).
  - forecasting/src/evaluate/day_ahead_eval.py is the supplementary (non-gating)
    diagnostic that replays the realistic regime: FeaturePipeline.extend_history()
    reveals each day's ACTUAL demand before the next day is scored, so lags are
    populated the way they would be in production. Restructuring the shared
    RollingOriginBacktest itself to do this for every model was judged out of scope
    for a P2 remediation pass (Anti-Drift) -- see construction_roadmap.md Phase 2.
"""
from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from forecasting.src.features.pipeline import FeaturePipeline, _coerce_date
from forecasting.src.models.baselines import BaseBaseline

# Columns LightGBM treats as categorical (native split on integers, no one-hot).
# day_of_week and era_id are included: trees gain nothing from cyclical encoding of
# these discrete labels, but native categoricals let the model learn non-monotone
# splits (e.g., Saturday > Friday > Monday in one tree node). Rule 02-feature-eng.
_CAT_COLS = ["item_id", "service_period", "day_of_week", "era_id"]


class GlobalLGBMModel(BaseBaseline):
    """One LightGBM model trained globally across all items.

    Parameters
    ----------
    n_estimators   : number of boosting rounds (rule 03: log all runs; 300 default)
    learning_rate  : step size shrinkage (0.05 is conservative but converges well)
    num_leaves     : tree complexity ceiling; 31 is the LightGBM default
    random_state   : seed for reproducibility (rule 03: random_state=42 everywhere)
    sim_cfg_path   : override for config/sim.yaml passed to FeaturePipeline
    """

    def __init__(
        self,
        n_estimators: int = 300,
        learning_rate: float = 0.05,
        num_leaves: int = 31,
        random_state: int = 42,
        sim_cfg_path: Path | None = None,
    ) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self.random_state = random_state
        self._sim_cfg_path = sim_cfg_path
        self._pipeline: FeaturePipeline | None = None
        self._model: lgb.Booster | None = None

    # ------------------------------------------------------------------ #
    #  BaseBaseline interface                                              #
    # ------------------------------------------------------------------ #

    def fit(self, demand_df: pd.DataFrame) -> "GlobalLGBMModel":
        """Fit the feature pipeline then train LightGBM on the cleaned demand."""
        df = demand_df.copy()
        df["business_date"] = _coerce_date(df["business_date"])

        self._pipeline = FeaturePipeline(sim_cfg_path=self._sim_cfg_path).fit(df)
        # check_leakage=False: the one sanctioned exception (pipeline.py docstring) --
        # this transforms the SAME rows just passed to fit(), to build training
        # features/labels. The canary would always fire here since train_max_date
        # trivially equals the transform window's own max.
        featured = self._pipeline.transform(df, check_leakage=False)

        feat_cols = self._pipeline.feature_columns()
        X = featured[feat_cols].copy()
        y = featured["demand"].astype(float)

        # LightGBM native categoricals: pass dtype='category', then name the columns
        for col in _CAT_COLS:
            X[col] = X[col].astype("category")

        lgb_train = lgb.Dataset(
            X, label=y, categorical_feature=_CAT_COLS, free_raw_data=False
        )

        params = {
            "objective": "poisson",
            # Max step-size clip on the log-link gradient; 0.7 prevents exploding
            # updates when early training has wildly wrong scale (LightGBM docs).
            "poisson_max_delta_step": 0.7,
            "learning_rate": self.learning_rate,
            "num_leaves": self.num_leaves,
            "min_data_in_leaf": 5,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "seed": self.random_state,
        }
        self._model = lgb.train(params, lgb_train, num_boost_round=self.n_estimators)
        print(
            f"[point_model] trained {self.n_estimators} rounds, "
            f"{len(X)} rows, {len(feat_cols)} features"
        )
        self._log_diagnostics(X, y, featured["item_id"])
        return self

    def _log_diagnostics(self, X: pd.DataFrame, y: pd.Series, item_ids: pd.Series) -> None:
        """Rule 03 training diagnostics: per-item predicted-vs-actual mean (large bias
        signals missing era features or censored-demand contamination -- exactly the 130
        censored rows currently fed into the target, see construction_roadmap.md Phase 3)
        and feature importance. Stored on self for programmatic access (e.g. point_floor.py).
        MLflow run logging stays parked as premature infra (P2_review.md MINOR-6).
        """
        pred = self._model.predict(X)
        diag = pd.DataFrame({"item_id": item_ids.values, "pred": pred, "actual": y.values})
        self.item_bias_ = (
            diag.groupby("item_id")
            .agg(pred_mean=("pred", "mean"), actual_mean=("actual", "mean"))
            .assign(bias=lambda d: d["pred_mean"] - d["actual_mean"])
            .sort_values("bias")
        )
        self.feature_importances_ = pd.Series(
            self._model.feature_importance(), index=self._model.feature_name()
        ).sort_values(ascending=False)

        print("[point_model] per-item predicted vs. actual mean (bias = pred - actual):")
        print(self.item_bias_.round(3).to_string())
        print("[point_model] feature importances:")
        print(self.feature_importances_.to_string())

    def predict(
        self,
        dates: list,
        items: list[str],
        service_periods: list[str],
    ) -> pd.DataFrame:
        """Return point forecasts for every (date, item, service_period) combination.

        Columns: [business_date, item_id, service_period, forecast].
        """
        if self._pipeline is None or self._model is None:
            raise RuntimeError("GlobalLGBMModel.fit() must be called before predict()")

        # Build the full cross-product input frame (matches BaseBaseline contract)
        rows = [
            {"business_date": d, "item_id": it, "service_period": sp}
            for d in dates
            for it in items
            for sp in service_periods
        ]
        input_df = pd.DataFrame(rows)
        input_df["business_date"] = _coerce_date(input_df["business_date"])
        # 'demand' placeholder so transform() finds the column it might copy through
        input_df["demand"] = 0

        # Inference must always be on genuinely future dates -- rely on the pipeline's
        # default (check_leakage=True) so predicting inside/before the training
        # window fails loud instead of silently producing a number (backlog #6).
        featured = self._pipeline.transform(input_df)
        feat_cols = self._pipeline.feature_columns()
        X = featured[feat_cols].copy()
        for col in _CAT_COLS:
            X[col] = X[col].astype("category")

        raw_preds = self._model.predict(X)
        # Clamp to >= 0: the Poisson log-link guarantees positive outputs, but
        # numeric edge cases (NaN lag features near the train boundary) can rarely
        # produce tiny negatives after the exp(). Hard-clamp is the safe floor.
        preds = np.maximum(raw_preds, 0.0)

        featured["forecast"] = preds
        return featured[["business_date", "item_id", "service_period", "forecast"]]
