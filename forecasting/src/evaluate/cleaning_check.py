"""The cleaning-vs-truth check -- the second, previously-unbuilt clause of P2's
"done when": *cleaning verified against `_truth/`.*

This is one of the two sanctioned readers of data/_truth/ (data/CONTRACT.md; the other
is forecasting/src/simulate/, which writes it). It never feeds `_truth/` into anything
that touches model inputs -- it only compares two already-computed OBSERVABLE demand
series (the naive raw series and the Phase-2 cleaned series) against the hidden
true_demand to check that cleaning actually moves the signal closer to reality, the
way stripping comps/staff/voids is supposed to.

Firewall: only forecasting.src.evaluate may import this module's truth-reading path
(tests/test_module_boundaries.py + .importlinter enforce this structurally).

Run:  python -m forecasting.src.evaluate.cleaning_check
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from forecasting.src.data.cleaner import clean_demand
from forecasting.src.data.loader import build_observed_demand

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TRUTH_DIR = _REPO_ROOT / "data" / "_truth"


def _assert_truth_only(path: Path) -> None:
    if Path(path).name != "_truth":
        raise ValueError(
            f"cleaning_check reads the data/_truth/ store only; refused non-truth path: {path}"
        )


def _load_truth_demand(truth_dir: Path = _DEFAULT_TRUTH_DIR) -> pd.DataFrame:
    _assert_truth_only(truth_dir)
    df = pd.read_csv(Path(truth_dir) / "truth_demand.csv")
    df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    return df.rename(columns={"true_demand": "truth"})[
        ["business_date", "item_id", "service_period", "truth"]
    ]


def _mae_and_bias(observed: pd.DataFrame, truth: pd.DataFrame) -> tuple[float, float]:
    """Mean absolute error and mean signed bias of observed demand vs. true_demand.

    Left-merge from truth so every truth row is scored even if an observed series
    (dirty or clean) is missing a date/item/period combination -- missing observed
    demand is treated as 0, which is the honest worst case for that comparison.
    """
    merged = truth.merge(
        observed, on=["business_date", "item_id", "service_period"], how="left"
    )
    merged["demand"] = merged["demand"].fillna(0)
    err = merged["demand"] - merged["truth"]
    return float(err.abs().mean()), float(err.mean())


def compute_cleaning_gap(truth_dir: Path = _DEFAULT_TRUTH_DIR) -> dict[str, float]:
    """Compare dirty (raw-observable) vs. clean demand against true_demand.

    Returns dirty/clean MAE and bias. A working cleaner should show clean_mae <
    dirty_mae (comps/staff/voids were inflating the observed signal away from truth)
    and |clean_bias| generally no worse than |dirty_bias|.
    """
    truth = _load_truth_demand(truth_dir)
    dirty = build_observed_demand()
    clean = clean_demand().drop(columns=["censored"])

    dirty_mae, dirty_bias = _mae_and_bias(dirty, truth)
    clean_mae, clean_bias = _mae_and_bias(clean, truth)
    return {
        "dirty_mae": dirty_mae,
        "clean_mae": clean_mae,
        "dirty_bias": dirty_bias,
        "clean_bias": clean_bias,
    }


def main() -> None:
    gap = compute_cleaning_gap()
    print("=" * 64)
    print("CLEANING-VS-TRUTH CHECK  (data/_truth/truth_demand.csv)")
    print("=" * 64)
    print(f"Dirty (raw-observable)  MAE vs truth: {gap['dirty_mae']:.3f}  "
          f"(bias {gap['dirty_bias']:+.3f})")
    print(f"Clean (Phase-2 cleaned) MAE vs truth: {gap['clean_mae']:.3f}  "
          f"(bias {gap['clean_bias']:+.3f})")
    if gap["clean_mae"] >= gap["dirty_mae"]:
        raise SystemExit(
            f"Cleaning check FAILED: clean demand (MAE {gap['clean_mae']:.3f}) is not "
            f"closer to truth than raw demand (MAE {gap['dirty_mae']:.3f})."
        )
    print("Cleaning check: PASS -- cleaning moves observed demand toward true_demand.")


if __name__ == "__main__":
    main()
