"""Phase-4 quantile model — global LightGBM quantile regression across all items.

QuantileGBMModel mirrors GlobalLGBMModel's structure (same FeaturePipeline, same
item_id-as-native-categorical boundary) but fits one LGBMRegressor per requested
quantile level instead of a single Poisson mean model. It delivers the predictive
DISTRIBUTION Phase 4 needs; the newsvendor read-off (forecasting/src/decision/
newsvendor.py) is a separate, later step — "clean separation of model (delivers
quantile) from policy (picks which quantile)" (construction_roadmap.md Phase 4
Practices (a)). This module never imports config.py/objective.py and knows
nothing about Co/Cu — it only knows quantile levels.

Non-crossing (rule 03-model-training.md): independently-fit per-quantile models
are not guaranteed monotone across quantile levels for a given row. Enforced here
by post-hoc rearrangement (Chernozhukov, Fernandez-Val & Galichon 2010) — sorting
each row's predictions across the quantile axis — the simpler of the two rule-
sanctioned fixes and the one that needs no joint-model retraining.

Why lgb.LGBMRegressor (sklearn API) here, unlike point.py's raw lgb.train()/
Dataset: forecasting/src/evaluate/calibration.py's MAPIE conformal wrapper
(ConformalizedQuantileRegressor) requires a regressor exposing sklearn's
estimator interface, and explicitly whitelists lightgbm.LGBMRegressor for this.
Using the sklearn API for the whole quantile grid (not just calibration.py's own
separate conformal fit) keeps one training code path in this module instead of two.
"""
from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from forecasting.src.features.pipeline import FeaturePipeline, _coerce_date

# Columns LightGBM treats as categorical — identical to models/point.py's _CAT_COLS
# (same convention: item_id stays plain str upstream, cast to category only here).
_CAT_COLS = ["item_id", "service_period", "day_of_week", "era_id"]

# Rule 03's stated minimum coverage is [0.10, 0.25, 0.50, 0.75, 0.90]; widened here
# with a near-0/near-1 anchor pair (0.05, 0.95, 0.99) so decision/newsvendor.py's
# waste/stockout integrals (which need CDF anchors near 0 and near 1, not just the
# interior) have a stable base grid to union each item's own critical ratio into.
DEFAULT_QUANTILE_LEVELS: tuple[float, ...] = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)


class QuantileGBMModel:
    """One LightGBM quantile regressor per requested quantile level, trained
    globally across all items (item_id a native categorical feature, matching
    GlobalLGBMModel).

    Parameters
    ----------
    quantile_levels : the quantile levels to fit — e.g. DEFAULT_QUANTILE_LEVELS
                       unioned with each item's own critical ratio via
                       decision.newsvendor.required_quantile_levels(). Stored
                       sorted and de-duplicated; order of the input doesn't matter.
    n_estimators, learning_rate, num_leaves, random_state, sim_cfg_path : same
        meaning as GlobalLGBMModel (models/point.py).
    """

    def __init__(
        self,
        quantile_levels: tuple[float, ...] = DEFAULT_QUANTILE_LEVELS,
        n_estimators: int = 300,
        learning_rate: float = 0.05,
        num_leaves: int = 31,
        random_state: int = 42,
        sim_cfg_path: Path | None = None,
    ) -> None:
        levels = sorted({round(float(q), 6) for q in quantile_levels})
        if not levels or levels[0] <= 0.0 or levels[-1] >= 1.0:
            raise ValueError(f"quantile_levels must all lie strictly in (0, 1); got {levels}")
        self.quantile_levels = levels
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self.random_state = random_state
        self._sim_cfg_path = sim_cfg_path
        self._pipeline: FeaturePipeline | None = None
        # Public (diagnostic) on purpose — evaluate/calibration.py's docstring
        # explains why it does NOT reach in here for its own conformal fit, but a
        # test or a future caller legitimately might want to inspect a single level.
        self.estimators_: dict[float, lgb.LGBMRegressor] = {}

    # ------------------------------------------------------------------ #
    #  Fit / predict                                                       #
    # ------------------------------------------------------------------ #

    def fit(self, demand_df: pd.DataFrame) -> "QuantileGBMModel":
        """Fit the feature pipeline once, then one quantile regressor per level."""
        df = demand_df.copy()
        df["business_date"] = _coerce_date(df["business_date"])

        self._pipeline = FeaturePipeline(sim_cfg_path=self._sim_cfg_path).fit(df)
        # check_leakage=False: the one sanctioned exception (pipeline.py docstring,
        # mirrored from GlobalLGBMModel.fit) — transforms the SAME rows just fit on.
        featured = self._pipeline.transform(df, check_leakage=False)

        feat_cols = self._pipeline.feature_columns()
        X = featured[feat_cols].copy()
        for col in _CAT_COLS:
            X[col] = X[col].astype("category")
        y = featured["demand"].astype(float)

        self.estimators_ = {}
        for q in self.quantile_levels:
            est = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                num_leaves=self.num_leaves,
                min_child_samples=5,
                subsample=0.8,
                subsample_freq=5,
                colsample_bytree=0.8,
                random_state=self.random_state,
                verbosity=-1,
            )
            est.fit(X, y, categorical_feature=_CAT_COLS)
            self.estimators_[q] = est

        print(
            f"[quantile_model] trained {len(self.quantile_levels)} quantile levels "
            f"{self.quantile_levels}, {len(X)} rows, {len(feat_cols)} features"
        )
        return self

    def _build_features(self, df: pd.DataFrame, check_leakage: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
        if self._pipeline is None:
            raise RuntimeError("QuantileGBMModel.fit() must be called first")
        featured = self._pipeline.transform(df, check_leakage=check_leakage)
        feat_cols = self._pipeline.feature_columns()
        X = featured[feat_cols].copy()
        for col in _CAT_COLS:
            X[col] = X[col].astype("category")
        return featured, X

    def predict_quantiles(
        self,
        dates: list,
        items: list[str],
        service_periods: list[str],
    ) -> pd.DataFrame:
        """Long-format quantile forecasts for every (date, item, service_period, quantile).

        Columns: [business_date, item_id, service_period, quantile, forecast].
        Non-crossing enforced per (business_date, item_id, service_period) row via
        sort-based rearrangement (rule 03) before returning.
        """
        if not self.estimators_:
            raise RuntimeError("QuantileGBMModel.fit() must be called before predict_quantiles()")

        rows = [
            {"business_date": d, "item_id": it, "service_period": sp}
            for d in dates
            for it in items
            for sp in service_periods
        ]
        input_df = pd.DataFrame(rows)
        input_df["business_date"] = _coerce_date(input_df["business_date"])
        input_df["demand"] = 0  # placeholder; never read as a feature

        # Inference must always be on genuinely future dates — default
        # check_leakage=True, same discipline as GlobalLGBMModel.predict().
        featured, X = self._build_features(input_df, check_leakage=True)

        preds = np.column_stack(
            [np.maximum(self.estimators_[q].predict(X), 0.0) for q in self.quantile_levels]
        )
        # Non-crossing: rearrange each row's predictions ascending (Chernozhukov
        # et al.) — self.quantile_levels is already sorted, so column j must hold
        # the j-th smallest value for the curve to be a valid (monotone) inverse-CDF.
        preds = np.sort(preds, axis=1)

        base = featured[["business_date", "item_id", "service_period"]]
        long_rows = []
        for j, q in enumerate(self.quantile_levels):
            part = base.copy()
            part["quantile"] = q
            part["forecast"] = preds[:, j]
            long_rows.append(part)
        return (
            pd.concat(long_rows, ignore_index=True)
            .sort_values(["business_date", "item_id", "service_period", "quantile"])
            .reset_index(drop=True)
        )
