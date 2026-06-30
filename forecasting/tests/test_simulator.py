"""Tests for the synthetic data generator (Phase 1).

Uses a 90-day date range for speed; all structural invariants still apply.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yaml

from forecasting.src.simulate.generator import RestaurantSimulator, _DEFAULT_SIM_CFG


@pytest.fixture(scope="module")
def sim_outputs():
    """Run the simulator with a 90-day range into a temp dir. Reused across tests."""
    with tempfile.TemporaryDirectory() as tmp:
        raw_dir = Path(tmp) / "raw"
        truth_dir = Path(tmp) / "_truth"
        raw_dir.mkdir()
        truth_dir.mkdir()

        import yaml as _yaml
        cfg = _yaml.safe_load(_DEFAULT_SIM_CFG.read_text())
        cfg["date_range"] = {"start": "2023-01-01", "end": "2023-03-31"}
        cfg["goforward_days"] = 20
        # Reduce eras to those within this range
        cfg["menu_eras"] = [e for e in cfg["menu_eras"] if e["start"] <= "2023-03-31"]
        if not cfg["menu_eras"]:
            cfg["menu_eras"] = [{"start": "2023-01-01", "id": 0, "name": "Test"}]

        import tempfile as _tf
        cfg_file = Path(tmp) / "sim_test.yaml"
        cfg_file.write_text(_yaml.dump(cfg))

        sim = RestaurantSimulator(cfg_file)
        sim.run(raw_dir, truth_dir)

        yield {
            "raw_dir": raw_dir,
            "truth_dir": truth_dir,
            "pos_sales": pd.read_csv(raw_dir / "pos_sales.csv"),
            "reservations": pd.read_csv(raw_dir / "reservations.csv"),
            "invoices": pd.read_csv(raw_dir / "invoices.csv"),
            "recipes_stated": pd.read_csv(raw_dir / "recipes_stated.csv"),
            "weather_actuals": pd.read_csv(raw_dir / "weather_actuals.csv"),
            "weather_forecast": pd.read_csv(raw_dir / "weather_forecast.csv"),
            "events": pd.read_csv(raw_dir / "events.csv"),
            "eightysix_log": pd.read_csv(raw_dir / "eightysix_log.csv"),
            "truth_demand": pd.read_csv(truth_dir / "truth_demand.csv"),
            "truth_stockouts": pd.read_csv(truth_dir / "truth_stockouts.csv"),
            "truth_recipes": pd.read_csv(truth_dir / "truth_recipes.csv"),
            "truth_spoilage": pd.read_csv(truth_dir / "truth_spoilage.csv"),
        }


RAW_FILES = [
    "pos_sales.csv", "reservations.csv", "invoices.csv", "recipes_stated.csv",
    "weather_actuals.csv", "weather_forecast.csv", "events.csv", "eightysix_log.csv",
]
TRUTH_FILES = [
    "truth_demand.csv", "truth_stockouts.csv", "truth_recipes.csv",
    "truth_spoilage.csv", "truth_params.yaml",
]


def test_raw_files_exist(sim_outputs):
    for fname in RAW_FILES:
        assert (sim_outputs["raw_dir"] / fname).exists(), f"Missing raw file: {fname}"


def test_truth_files_exist(sim_outputs):
    for fname in TRUTH_FILES:
        assert (sim_outputs["truth_dir"] / fname).exists(), f"Missing truth file: {fname}"


def test_pos_sales_schema(sim_outputs):
    df = sim_outputs["pos_sales"]
    required = {
        "check_id", "line_id", "business_date", "sold_at", "item_name",
        "category", "menu_price", "qty", "modifiers",
        "discount_amount", "void_flag", "server_id",
    }
    assert required.issubset(set(df.columns)), f"Missing columns: {required - set(df.columns)}"
    assert "item_id" not in df.columns, (
        "pos_sales must not contain a stable item_id — real POS exports don't have one; "
        "reconciliation from drifting item_name is the P2 cleaner's job (issue #5)"
    )
    assert len(df) > 0, "pos_sales is empty"
    assert (df["qty"] >= 0).all(), "qty has negative values"
    assert (df["menu_price"] > 0).all(), "menu_price has non-positive values"


def test_demand_is_integer_nonneg(sim_outputs):
    df = sim_outputs["truth_demand"]
    assert "true_demand" in df.columns
    assert (df["true_demand"] >= 0).all(), "Negative demand found"
    assert (df["true_demand"] == df["true_demand"].astype(int)).all(), "Non-integer demand"


def test_truth_demand_has_all_items(sim_outputs):
    df = sim_outputs["truth_demand"]
    expected_items = {
        "braised_short_rib", "pan_seared_salmon", "half_roast_chicken",
        "house_burger", "ribeye_steak_12oz", "duck_confit", "butter_poached_cod",
        "wild_mushroom_risotto", "classic_caesar_salad", "pappardelle_bolognese",
        "tuna_tartare",
    }
    found = set(df["item_id"].unique())
    assert expected_items == found, f"Missing items: {expected_items - found}"


def test_truth_demand_has_both_service_periods(sim_outputs):
    df = sim_outputs["truth_demand"]
    assert set(df["service_period"].unique()) == {"lunch", "dinner"}


def test_censoring_present(sim_outputs):
    df = sim_outputs["truth_stockouts"]
    # With 90 days and realistic demand, at least some item-days hit the cap
    assert len(df) > 0, (
        "truth_stockouts is empty — no censoring occurred. "
        "Check capacity_caps or censoring_threshold in sim.yaml."
    )


def test_censoring_observed_le_cap(sim_outputs):
    df = sim_outputs["truth_stockouts"]
    if df.empty:
        return
    assert (df["observed_demand"] <= df["cap"]).all(), "observed_demand exceeds cap"
    assert (df["true_demand"] >= df["observed_demand"]).all(), "true_demand < observed_demand"


def test_pollution_rate_in_range(sim_outputs):
    df = sim_outputs["pos_sales"]
    n = len(df)
    if n == 0:
        return
    n_comp = ((df["discount_amount"] > 0) | (df["comp_flag"] == True)).sum()
    n_void = df["void_flag"].sum()
    pollution_frac = (n_comp + n_void) / n
    assert 0.02 <= pollution_frac <= 0.15, (
        f"Pollution fraction {pollution_frac:.3f} outside expected 2–15% range"
    )


def test_weather_forecast_differs_from_actuals(sim_outputs):
    act = sim_outputs["weather_actuals"]
    fct = sim_outputs["weather_forecast"]
    merged = act.merge(fct, on="date", suffixes=("_act", "_fct"))
    diff = (merged["temp_high_act"] - merged["temp_high_fct"]).abs()
    assert diff.std() > 0, "Weather forecast is identical to actuals — no divergence"
    assert diff.mean() > 0.5, "Weather forecast divergence is suspiciously small"


def test_eightysix_log_only_in_goforward_window(sim_outputs):
    df = sim_outputs["eightysix_log"]
    if df.empty:
        return  # pass: no stockouts in go-forward window
    # All eightysix dates should be in the last goforward_days of the simulation
    df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    cutoff = pd.Timestamp("2023-03-11").date()  # 2023-03-31 - 20 days
    assert (df["business_date"] >= cutoff).all(), (
        "eightysix_log contains dates outside the go-forward window (historical leak)"
    )


def test_truth_firewall(sim_outputs):
    """Raw files must not reference the _truth path anywhere in string columns."""
    for key in ["pos_sales", "reservations", "invoices", "recipes_stated"]:
        df = sim_outputs[key]
        for col in df.select_dtypes(include="object").columns:
            hits = df[col].astype(str).str.contains("_truth", na=False)
            assert not hits.any(), f"{key}.{col} contains a '_truth' reference"


def test_recipes_stated_noisier_than_truth(sim_outputs):
    truth = sim_outputs["truth_recipes"]
    stated = sim_outputs["recipes_stated"]
    # Join on dish_name + ingredient and compare qty_per_portion
    merged = truth.merge(
        stated, on=["dish_name", "ingredient"], suffixes=("_truth", "_stated")
    )
    if merged.empty:
        pytest.skip("No matching recipe lines to compare (all dropped by noise)")
    diffs = (merged["qty_per_portion_truth"] - merged["qty_per_portion_stated"]).abs()
    # At least some lines should differ
    assert (diffs > 0).any(), "Stated recipes are identical to truth recipes — noise not applied"


def test_item_name_drift_present(sim_outputs):
    """With 9 eras and per-era aliases, pos_sales contains more unique display names
    than canonical items (11). item_id is no longer in pos_sales — name drift is the
    reconciliation problem the P2 cleaner solves (issue #5)."""
    df = sim_outputs["pos_sales"]
    n_unique = df["item_name"].nunique()
    assert n_unique > 11, (
        f"Only {n_unique} unique item_names in pos_sales; expected > 11 because each "
        "of the 11 canonical items has multiple era aliases in config/sim.yaml"
    )


def test_weather_actuals_schema(sim_outputs):
    df = sim_outputs["weather_actuals"]
    assert set(df.columns) >= {"date", "temp_high", "temp_low", "precip_mm"}
    assert (df["temp_high"] > df["temp_low"]).all()
    assert (df["precip_mm"] >= 0).all()


def test_weather_forecast_has_issued_on(sim_outputs):
    df = sim_outputs["weather_forecast"]
    assert "forecast_issued_on" in df.columns
    assert df["forecast_issued_on"].notna().all()


def test_truth_params_yaml(sim_outputs):
    params_path = sim_outputs["truth_dir"] / "truth_params.yaml"
    params = yaml.safe_load(params_path.read_text())
    assert "seed" in params
    assert "total_pos_rows" in params
    assert "total_stockout_rows" in params


def test_assert_not_truth_path():
    """Generator must refuse a raw_dir that contains '_truth' in its path."""
    from forecasting.src.simulate.generator import _assert_not_truth_path
    with pytest.raises(ValueError, match="_truth"):
        _assert_not_truth_path(Path("/some/data/_truth/raw"))
