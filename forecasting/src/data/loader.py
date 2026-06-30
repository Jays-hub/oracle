"""Raw -> observed-demand bridge (Phase 1).

Reads the data/raw/ store ONLY. This produces the *naive observable* demand series
that the honest baselines and the dollar floor are computed on -- it is NOT the
Phase-2 cleaner. It performs exactly the structural exclusions (a voided line is not a
sale; a drifting item_name must be reconciled to a canonical item_id) and derives the
implied daypart; it otherwise leaves the raw pollution (comps, staff meals) and the
baked-in censoring in place, because a naive operator pulling POS counts cannot see them.
Stripping pollution is the Phase-2 cleaner's job (forecasting/src/data/cleaner.py).

Firewall (rule 01-data-ingestion): a data-loading module opens data/raw/ only. The
whitelist guard below is the runtime last line of defense; the structural boundary test
(tests/test_module_boundaries.py) is the first.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_RAW_DIR = _REPO_ROOT / "data" / "raw"
_DEFAULT_SIM_CFG = _REPO_ROOT / "config" / "sim.yaml"

# Daypart is implied by the sale timestamp, never labeled in a Toast export
# (forecasting/docs/simulated_data.md). Lunch service runs 11:00-15:00 and dinner
# 17:00-22:00 in the generator; nothing is rung up in the 15:00-17:00 gap, so a single
# 16:00 cutoff separates the two cleanly.
_LUNCH_DINNER_CUTOFF_HOUR = 16


def _assert_raw_only(path: Path) -> None:
    """Whitelist the raw store (rule 01): this loader opens the data/raw/ directory only.
    Whitelisting beats blacklisting -- any directory that is not the raw store is refused,
    so a model-input path can never resolve into the hidden ground-truth oracle.
    """
    if Path(path).name != "raw":
        raise ValueError(
            f"loader reads the data/raw/ store only; refused non-raw path: {path}"
        )


def build_name_to_id_map(cfg_path: Path | None = None) -> dict[str, str]:
    """Build a flat lookup from every era's POS display name to canonical item_id.

    Reads item_name_aliases from config/sim.yaml. A real Toast export has no stable
    item_id across menu reprints -- only the display name is observable, and it drifts
    with each reprint. This map encodes every known era alias so both the naive loader
    and the Phase-2 cleaner can recover the canonical id without touching truth.

    Raises ValueError on ambiguous aliases (two canonical ids claim the same display name).
    """
    path = cfg_path or _DEFAULT_SIM_CFG
    cfg: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for canonical_id, aliases in cfg["item_name_aliases"].items():
        for name in aliases:
            if name in mapping and mapping[name] != canonical_id:
                raise ValueError(
                    f"Ambiguous alias '{name}' maps to both '{mapping[name]}' and "
                    f"'{canonical_id}'. Fix item_name_aliases in sim.yaml."
                )
            mapping[name] = canonical_id
    return mapping


def load_pos_sales(raw_dir: Path = _DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load the raw Toast line-item export. Opens the data/raw/ store only."""
    _assert_raw_only(raw_dir)
    df = pd.read_csv(Path(raw_dir) / "pos_sales.csv")
    df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    df["sold_at"] = pd.to_datetime(df["sold_at"])
    return df


def build_observed_demand(raw_dir: Path = _DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Aggregate the raw POS export into the per-(date, item, service_period) demand
    series the baselines and the dollar floor consume.

    Returns [business_date (date), item_id (str), service_period (str), demand (int)] on
    the FULL (date x item x service_period) grid: a date/item/daypart with no sales is
    emitted as demand 0, not dropped -- otherwise a baseline is never charged the overage
    of prepping on a day that turned out empty, and the floor is dishonestly low.

    Scope discipline: this is the naive observable series (voids dropped, item_name
    reconciled, daypart derived, nothing else). Comps/staff meals and censoring stay in by
    design; the honest floor must be computed on what the restaurant can actually see.
    The Phase-2 cleaner (cleaner.py) strips the observable pollution and tags censored days.
    """
    df = load_pos_sales(raw_dir)

    # The one structural exclusion: a voided line never represents a sale. Coerce
    # defensively so a bool column or a "True"/"False" string column behaves identically.
    void_mask = df["void_flag"].astype(str).str.lower().isin(["true", "1"])
    df = df.loc[~void_mask].copy()

    # Reconcile the drifting POS display name to a stable canonical item_id.
    # Real POS exports (Toast, Square) delete and recreate menu items at each reprint,
    # so item_id is not stable across reprints -- only item_name is observable, and it
    # drifts. The alias map in config/sim.yaml encodes every era's display name.
    name_to_id = build_name_to_id_map()
    unknown = set(df["item_name"].dropna().unique()) - set(name_to_id)
    if unknown:
        raise ValueError(
            f"build_observed_demand: unrecognized item_name(s) in pos_sales — "
            f"not in alias map: {sorted(unknown)}"
        )
    df["item_id"] = df["item_name"].map(name_to_id)

    df["service_period"] = df["sold_at"].dt.hour.apply(
        lambda h: "lunch" if h < _LUNCH_DINNER_CUTOFF_HOUR else "dinner"
    )

    grouped = df.groupby(["business_date", "item_id", "service_period"])["qty"].sum()

    # Reindex onto the full grid so empty dayparts surface as 0 (chargeable overage).
    # Use ALL canonical items from the alias map so items with zero sales on a date still
    # appear (with demand=0) rather than being silently absent from the grid.
    dates = sorted(df["business_date"].unique())
    items = sorted(set(name_to_id.values()))
    periods = sorted(df["service_period"].unique())
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
    return demand.sort_values(
        ["business_date", "item_id", "service_period"]
    ).reset_index(drop=True)
