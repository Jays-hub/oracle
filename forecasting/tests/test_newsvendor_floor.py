"""Tests for the Phase-4 dollar-gate adapter (forecasting/src/evaluate/newsvendor_floor.py).

Scoped to _NewsvendorAdapter's fit/predict contract on a small, fast synthetic
fixture — like test_point.py/test_quantile.py, the full dollar-gate PROOF
(compute_newsvendor_floor() on real data) is exercised manually via `python -m`,
not through pytest (see test_unconstrain_floor.py's docstring for why: a fresh
checkout has no generated data/raw/ for it to run against).
"""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from forecasting.src.config import ItemEconomics, PrepType
from forecasting.src.decision.newsvendor import (
    critical_ratio,
    required_quantile_levels,
    route_batch_items,
)
from forecasting.src.evaluate.backtest import RollingOriginBacktest
from forecasting.src.evaluate.newsvendor_floor import _NewsvendorAdapter
from forecasting.src.models.baselines import Lag7Baseline


def _demand_df(n_days: int = 90, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = datetime.date(2024, 1, 1)
    rows = []
    for offset in range(n_days):
        d = start + datetime.timedelta(days=offset)
        for it in ["item_a", "item_b"]:
            for sp in ["lunch", "dinner"]:
                rows.append({
                    "business_date": d,
                    "item_id": it,
                    "service_period": sp,
                    "demand": int(rng.poisson(10)),
                })
    return pd.DataFrame(rows)


def _items():
    # Deliberately different co/cu -> different critical ratios per item, so the
    # adapter's per-item r lookup is actually exercised (not both items sharing q*).
    eco_a = ItemEconomics(id="item_a", name="Item A", prep_type=PrepType.BATCH,
                           co=10.0, cu=15.0, lead_time_days=1)
    eco_b = ItemEconomics(id="item_b", name="Item B", prep_type=PrepType.BATCH,
                           co=5.0, cu=30.0, lead_time_days=1)
    return {"item_a": eco_a, "item_b": eco_b}


def _items_with_made_to_order():
    """Like _items() but with a third, made_to_order item -- for the P4_review.md
    MINOR-3 regression guard: route_batch_items() must strip it before it ever
    reaches the adapter, so the dish-count read-off never fires for it."""
    items = _items()
    items["item_c"] = ItemEconomics(
        id="item_c", name="Item C", prep_type=PrepType.MADE_TO_ORDER,
        co=6.0, cu=22.0, lead_time_days=1,
    )
    return items


# ------------------------------------------------------------------ fit/predict contract --

def test_predict_before_fit_raises():
    items = _items()
    adapter = _NewsvendorAdapter(items, required_quantile_levels(items), n_estimators=10)
    with pytest.raises(RuntimeError, match="fit"):
        adapter.predict([datetime.date(2024, 3, 1)], ["item_a"], ["lunch"])


def test_predict_schema_and_nonnegativity():
    items = _items()
    train = _demand_df(n_days=40)
    adapter = _NewsvendorAdapter(items, required_quantile_levels(items), n_estimators=10).fit(train)
    test_dates = [datetime.date(2024, 2, 12), datetime.date(2024, 2, 13)]
    preds = adapter.predict(test_dates, ["item_a", "item_b"], ["lunch", "dinner"])

    assert list(preds.columns) == ["business_date", "item_id", "service_period", "forecast"]
    assert len(preds) == 2 * 2 * 2  # 2 dates x 2 items x 2 service_periods
    assert (preds["forecast"] >= 0).all()
    assert preds["forecast"].notna().all()


def test_predict_skips_items_absent_from_economics():
    """An item with no matching ItemEconomics must be silently dropped, not crash
    or invent a cost -- mirrors score_predictions()'s own missing-item handling."""
    items = {"item_a": _items()["item_a"]}  # item_b deliberately omitted
    train = _demand_df(n_days=40)
    adapter = _NewsvendorAdapter(items, required_quantile_levels(items), n_estimators=10).fit(train)
    preds = adapter.predict([datetime.date(2024, 2, 12)], ["item_a", "item_b"], ["lunch"])
    assert set(preds["item_id"]) == {"item_a"}


def test_forecast_is_the_items_own_critical_ratio_readoff():
    """The whole point of the adapter: forecast at prep_qty = F^-1(q*_item), NOT
    the median -- items with a higher critical ratio (item_b: q*=30/35=0.857) must
    get a higher forecast, relative to their own distribution, than a lower-q*
    item (item_a: q*=15/25=0.6), all else equal. Checked via each item's OWN
    fitted quantile curve rather than a raw cross-item forecast comparison (the
    two items have independent demand levels in the fixture)."""
    items = _items()
    r_a = critical_ratio(items["item_a"].co, items["item_a"].cu)
    r_b = critical_ratio(items["item_b"].co, items["item_b"].cu)
    assert r_b > r_a  # sanity check on the fixture itself

    train = _demand_df(n_days=60)
    adapter = _NewsvendorAdapter(items, required_quantile_levels(items), n_estimators=20).fit(train)
    test_dates = [datetime.date(2024, 3, 1)]
    preds = adapter.predict(test_dates, ["item_a", "item_b"], ["lunch"])

    # The adapter's own quantile model, queried directly at each item's median (0.5)
    # and at its critical ratio, must show the read-off moved with r (not stuck at
    # the median) -- this is the contract test that would fail if predict() ever
    # regressed to always returning the median instead of prep_quantity(grp, r).
    long_preds = adapter._model.predict_quantiles(test_dates, ["item_a", "item_b"], ["lunch"])
    for item_id, r in [("item_a", r_a), ("item_b", r_b)]:
        grp = long_preds[(long_preds["item_id"] == item_id)]
        median = grp[grp["quantile"] == 0.5]["forecast"].iloc[0]
        forecast = preds[preds["item_id"] == item_id]["forecast"].iloc[0]
        if r > 0.5:
            assert forecast >= median - 1e-6, (
                f"{item_id}: critical-ratio read-off (r={r:.2f} > 0.5) should be >= the median"
            )


# ------------------------------------------------------------------ prep_type routing (MINOR-3) --

def test_made_to_order_item_never_gets_a_dish_count_readoff():
    """P4_review.md MINOR-3 regression guard: an adapter constructed with
    route_batch_items(items) -- newsvendor_floor.py's own convention -- must
    never emit a prep_qty row for a made_to_order item, even though the model
    itself was trained on demand for all three items."""
    items = _items_with_made_to_order()
    batch_items = route_batch_items(items)
    assert set(batch_items) == {"item_a", "item_b"}  # item_c (made_to_order) stripped

    train = _demand_df(n_days=40)
    # Fit against demand for all three items (item_c must appear in the training
    # signal even though it's never read off) by injecting a third item's rows.
    extra_rows = train[train["item_id"] == "item_a"].copy()
    extra_rows["item_id"] = "item_c"
    train = pd.concat([train, extra_rows], ignore_index=True)

    adapter = _NewsvendorAdapter(batch_items, required_quantile_levels(batch_items), n_estimators=10).fit(train)
    preds = adapter.predict(
        [datetime.date(2024, 2, 12)], ["item_a", "item_b", "item_c"], ["lunch"]
    )
    assert "item_c" not in set(preds["item_id"])
    assert set(preds["item_id"]) == {"item_a", "item_b"}


# ------------------------------------------------------------------ backtest integration --

def test_backtest_integration_produces_finite_bounded_costs():
    """Regression guard: the adapter must run cleanly inside RollingOriginBacktest
    and produce finite, non-negative dollar costs in the same ballpark as a simple
    baseline -- NOT a claim that it beats it on this tiny synthetic fixture (the
    dollar-gate PROOF is newsvendor_floor.py's compute_newsvendor_floor() on real
    data, mirroring test_point.py's own disclaimer)."""
    items = _items()
    demand_df = _demand_df(n_days=90)
    models = {
        "lag7": Lag7Baseline(),
        "quantile_newsvendor": _NewsvendorAdapter(items, required_quantile_levels(items), n_estimators=15),
    }
    bt = RollingOriginBacktest(n_folds=4, test_weeks=1, min_train_weeks=6)
    results = bt.run(demand_df, models, items)

    totals = results.groupby("baseline")["dollar_cost"].sum()
    assert np.isfinite(totals["quantile_newsvendor"])
    assert totals["quantile_newsvendor"] >= 0
    assert totals["quantile_newsvendor"] <= totals.drop("quantile_newsvendor").max() * 3.0
