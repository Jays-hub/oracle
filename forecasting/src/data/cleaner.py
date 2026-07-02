"""Phase-2 signal cleaner — removes observable pollution from the raw demand series.

Two categories of row-level exclusion, applied in order before aggregation:
  1. Void rows (structural: a voided line is never a sale)
  2. Staff-server rows (server_id in pollution.staff_server_ids from sim.yaml)

Comp-flagged rows (comp_flag == True) are deliberately NOT excluded. A comp tags a
real, fulfilled guest order that was later discounted/comped on the bill — the kitchen
still prepped and served the dish, so it is genuine prep demand, not noise. This was
verified by forecasting/src/evaluate/cleaning_check.py (the sanctioned oracle-comparison
module; docs/phase_decisions/P2_review.md BLOCKER-1): dropping comp-flagged rows moved
observed demand FURTHER from the hidden ground truth (MAE 0.522 vs. 0.472 raw), because
observed demand is already censored at or below the true series, so removing any
real-demand subset can only widen that gap. Keeping voids+staff-only removed and comps
in gives the closest MAE to ground truth (0.302) of any variant tested. Comps (flagged
or silent) stay in by design; the ~40% of comps that are silently untagged were never
removable anyway — they are invisible at the information boundary, honest residual
noise the model must be robust to.

After row-level exclusion the demand series is aggregated to (date, item_id, period)
using the same alias reconciliation as the naive loader. Censored day-items are then
tagged via the eightysix_log: an item that was 86'd on a date ran out before service
ended, so observed demand is a lower bound on true demand. Only the go-forward window
(last ~90 days per sim.yaml) has eightysix entries; older days are tagged censored=False
(the historical 86 board was wiped nightly — a realistic information limit).

Returns: [business_date (date), item_id (str), service_period (str),
          demand (int), censored (bool)]

Firewall (rule 01): reads data/raw/ only (same whitelist guard as loader.py).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from forecasting.src.config import load_items
from forecasting.src.data.loader import (
    _LUNCH_DINNER_CUTOFF_HOUR,
    build_name_to_id_map,
    load_pos_sales,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_RAW_DIR = _REPO_ROOT / "data" / "raw"
_DEFAULT_SIM_CFG = _REPO_ROOT / "config" / "sim.yaml"


def _assert_raw_only(path: Path) -> None:
    if Path(path).name != "raw":
        raise ValueError(
            f"cleaner reads the data/raw/ store only; refused non-raw path: {path}"
        )


def _norm(name: str) -> str:
    """Local trim+casefold — reimplemented, not imported from on-ramp (peer boundary)."""
    return name.strip().casefold()


def _assert_config_names_in_seam(name_to_id: dict[str, str]) -> None:
    """Assert every config/items.yaml item name resolves to a seam alias.

    The alias map is the only cross-artifact join key shared by the engine config and
    data/raw/ (forward note #4 from P0 review). A config name with no matching alias
    means that item can never be joined to POS sales — fail loud with the specific
    items that drifted rather than silently mis-routing them.
    """
    normalized_aliases = {_norm(alias) for alias in name_to_id}
    drifted = [
        f"{item.id}={item.name!r}"
        for item in load_items().values()
        if _norm(item.name) not in normalized_aliases
    ]
    if drifted:
        raise ValueError(
            "config/items.yaml names not found in seam alias map — no join key: "
            + ", ".join(drifted)
        )


def _print_missingness_report(df: pd.DataFrame) -> None:
    """Rule 01: print a null count/% per column before any row is dropped."""
    n = len(df)
    missing = df.isna().sum()
    print(f"[cleaner] missingness report ({n} rows):")
    any_missing = False
    for col, cnt in missing.items():
        if cnt > 0:
            any_missing = True
            print(f"    {col}: {cnt} ({cnt / n * 100:.1f}%)")
    if not any_missing:
        print("    (no missing values)")


def _load_cfg(cfg_path: Path) -> dict[str, Any]:
    return yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8"))


def _load_eightysix_log(raw_dir: Path) -> pd.DataFrame:
    _assert_raw_only(raw_dir)
    path = Path(raw_dir) / "eightysix_log.csv"
    _empty = pd.DataFrame(columns=["business_date", "item_name", "time_86d"])
    if not path.exists():
        return _empty
    try:
        df = pd.read_csv(path)
    except Exception:
        return _empty
    if df.empty or "business_date" not in df.columns:
        return _empty
    df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    return df


def clean_demand(
    raw_dir: Path = _DEFAULT_RAW_DIR,
    cfg_path: Path | None = None,
) -> pd.DataFrame:
    """Remove observable pollution and tag censored day-items.

    Parameters
    ----------
    raw_dir   : path to data/raw/ (whitelisted; non-raw dirs are refused)
    cfg_path  : override for config/sim.yaml (used in tests)

    Returns
    -------
    DataFrame with columns:
      [business_date (date), item_id (str), service_period (str),
       demand (int), censored (bool)]
    on the full (date × canonical_item × period) grid.
    """
    _assert_raw_only(raw_dir)
    cfg_path = cfg_path or _DEFAULT_SIM_CFG
    cfg = _load_cfg(cfg_path)
    staff_ids = set(cfg["pollution"]["staff_server_ids"])
    name_to_id = build_name_to_id_map(cfg_path)

    # Cross-seam name reconciliation (forward note #4): every item in config/items.yaml
    # must resolve to at least one alias in the seam's name→id map so the join key holds.
    _assert_config_names_in_seam(name_to_id)

    df = load_pos_sales(raw_dir)
    n_raw = len(df)
    _print_missingness_report(df)

    # 0. Quarantine qty==0 anomalies (rule 01): a zero-quantity line with NEITHER a void
    # nor a comp flag set is a data-quality anomaly (export glitch / dropped flag) —
    # NOT censored demand. True censoring is sold_qty == prep_qty (a P3 concern), never
    # a zero row. Has no effect on aggregated demand values (a qty==0 row already
    # contributes 0 to the groupby sum) — this is about surfacing the anomaly, not a
    # scoring fix.
    _void_flag = df["void_flag"].astype(str).str.lower().isin(["true", "1"])
    _comp_flag = df["comp_flag"].astype(str).str.lower().isin(["true", "1"])
    zero_qty_anomaly = (df["qty"] == 0) & ~_void_flag & ~_comp_flag
    n_anomaly = int(zero_qty_anomaly.sum())
    if n_anomaly:
        print(f"[cleaner] QUARANTINED {n_anomaly} qty==0 rows with no void/comp flag (data-quality anomaly)")
    df = df[~zero_qty_anomaly].copy()

    # 1. Drop voids — a voided line is never a sale (structural exclusion)
    void_mask = df["void_flag"].astype(str).str.lower().isin(["true", "1"])
    df = df[~void_mask].copy()
    n_void = int(void_mask.sum())

    # 2. Drop staff-server rows — back-of-house accounts follow a scheduling pattern
    # orthogonal to guest demand and must not train a demand signal.
    staff_mask = df["server_id"].isin(staff_ids)
    df = df[~staff_mask].copy()
    n_staff = int(staff_mask.sum())

    # Comp-flagged rows are intentionally NOT dropped — see module docstring
    # (verified via cleaning_check.py against the hidden ground truth: excluding them
    # moves observed demand further away, not closer).
    n_comp = int(
        df["comp_flag"].astype(str).str.lower().isin(["true", "1"]).sum()
    )

    n_kept = len(df)
    print(
        f"[cleaner] {n_raw} raw rows → removed {n_void} voids, {n_staff} staff rows "
        f"({n_comp} comp-flagged rows kept as genuine demand) → {n_kept} kept "
        f"(~{(n_raw - n_kept) / n_raw * 100:.1f}% excluded)"
    )

    # Reconcile drifting item_name → canonical item_id
    unknown = set(df["item_name"].dropna().unique()) - set(name_to_id)
    if unknown:
        raise ValueError(
            f"clean_demand: unrecognized item_name(s) in pos_sales — "
            f"not in alias map: {sorted(unknown)}"
        )
    df["item_id"] = df["item_name"].map(name_to_id)

    # Derive service_period from sold_at timestamp
    df["service_period"] = df["sold_at"].dt.hour.apply(
        lambda h: "lunch" if h < _LUNCH_DINNER_CUTOFF_HOUR else "dinner"
    )

    # Aggregate to (date, item, period)
    grouped = df.groupby(["business_date", "item_id", "service_period"])["qty"].sum()

    # Full-grid reindex: all canonical items × all dates × all configured periods.
    # Using config-defined periods (not just those observed in data) ensures every
    # daypart appears even when a date had zero clean sales for that period —
    # otherwise that daypart is silently absent and overage is never charged.
    dates = sorted(df["business_date"].unique())
    items = sorted(set(name_to_id.values()))
    periods = sorted(s["name"] for s in cfg["service_periods"])
    full = pd.MultiIndex.from_product(
        [dates, items, periods],
        names=["business_date", "item_id", "service_period"],
    )
    demand = (
        grouped.reindex(full, fill_value=0)
        .reset_index()
        .rename(columns={"qty": "demand"})
    )
    demand["demand"] = demand["demand"].astype(int)

    # Tag censored day-items via eightysix_log.
    # An 86 event means the kitchen ran out before service ended — observed demand on
    # that day understates true demand. Only the go-forward window has entries; all
    # other days are tagged censored=False (historical board was wiped nightly).
    # Keyed on (date, item, service_period) via time_86d -- a dinner 86 must not mark
    # that day's lunch row censored too (P2_review.md MINOR-4).
    eightysix = _load_eightysix_log(raw_dir)
    if not eightysix.empty:
        eightysix = eightysix.copy()
        # item_name in the 86 log drifts with era; reconcile it the same way
        eightysix["item_id"] = eightysix["item_name"].map(name_to_id)
        eightysix = eightysix.dropna(subset=["item_id"])
        eightysix["service_period"] = eightysix["time_86d"].apply(
            lambda t: (
                "lunch" if int(str(t).split(":")[0]) < _LUNCH_DINNER_CUTOFF_HOUR
                else "dinner"
            )
        )
        censored_keys = set(
            zip(eightysix["business_date"], eightysix["item_id"], eightysix["service_period"])
        )
    else:
        censored_keys = set()

    demand["censored"] = [
        (d, i, sp) in censored_keys
        for d, i, sp in zip(demand["business_date"], demand["item_id"], demand["service_period"])
    ]
    n_censored = int(demand["censored"].sum())
    print(f"[cleaner] censored day-items tagged: {n_censored}")

    return demand.sort_values(
        ["business_date", "item_id", "service_period"]
    ).reset_index(drop=True)
