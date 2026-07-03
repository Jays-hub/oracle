"""The unconstraining-vs-truth check -- Phase 3's own "done when" checkpoint:
does recovered demand track true_demand on the exact days it was censored?

One of the two sanctioned readers of data/_truth/ (data/CONTRACT.md; the other is
forecasting/src/simulate/, which writes it). Sibling to cleaning_check.py -- same
pattern, scoped to the specific rows unconstrain.py actually touches: clean_demand()'s
censored=True rows, not every row in truth_stockouts.csv. Those are not the same
set -- truth_stockouts.csv records every date true_demand exceeded a cap, over the
WHOLE simulated history, but data/raw/eightysix_log.csv (the only observable
stockout signal cleaner.py can read) is populated only for the go-forward window
(config/sim.yaml goforward_days). Historical stockouts left no log entry, so most
of truth_stockouts.csv is invisible to the engine and structurally uncorrectable --
scoring against it would dilute the check with events no method could touch and
mask whether unconstraining works where it CAN act. This module reports both
numbers (observable vs. total) but gates only on the observable subset.

true_demand is read directly from truth_stockouts.csv (generator.py writes it
there at censoring time) -- no separate merge against truth_demand.csv is needed.

Run:  python -m forecasting.src.evaluate.unconstrain_check
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from forecasting.src.data.cleaner import clean_demand
from forecasting.src.models.unconstrain import unconstrain_demand

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TRUTH_DIR = _REPO_ROOT / "data" / "_truth"


def _assert_truth_only(path: Path) -> None:
    if Path(path).name != "_truth":
        raise ValueError(
            f"unconstrain_check reads the data/_truth/ store only; refused non-truth path: {path}"
        )


def _load_truth_stockouts(truth_dir: Path = _DEFAULT_TRUTH_DIR) -> pd.DataFrame:
    _assert_truth_only(truth_dir)
    df = pd.read_csv(Path(truth_dir) / "truth_stockouts.csv")
    df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    return df[["business_date", "item_id", "service_period", "true_demand"]]


def compute_unconstrain_gap(truth_dir: Path = _DEFAULT_TRUTH_DIR) -> dict[str, float]:
    """Compare capped (observed) vs. recovered (unconstrained) demand against
    true_demand, restricted to the censoring events clean_demand() could actually
    OBSERVE (censored=True) -- an inner join against truth_stockouts.csv, not a
    left join over the whole file (see module docstring for why).

    Returns capped/recovered MAE and bias over the observable subset, plus the
    total truth_stockouts row count for transparency on how much of the true
    censoring history is invisible to the engine. A working unconstrainer should
    show recovered_mae < capped_mae on the observable rows -- capped demand is a
    systematically negative-biased lower bound on every one of them by
    construction (observed_demand == cap < true_demand), so recovery should
    narrow that gap, not necessarily close it completely.
    """
    truth = _load_truth_stockouts(truth_dir)
    clean = clean_demand()
    recovered = unconstrain_demand(clean)

    observable = clean.loc[clean["censored"], ["business_date", "item_id", "service_period", "demand"]]
    observable = observable.rename(columns={"demand": "observed"})
    fixed = recovered.rename(columns={"demand": "recovered"})[
        ["business_date", "item_id", "service_period", "recovered"]
    ]

    merged = observable.merge(
        truth, on=["business_date", "item_id", "service_period"], how="inner"
    ).merge(fixed, on=["business_date", "item_id", "service_period"], how="left")
    if len(merged) != len(observable):
        raise RuntimeError(
            "unconstrain_check: some clean_demand() censored=True row(s) have no matching "
            "truth_stockouts entry -- eightysix_log/truth_stockouts reconciliation is broken."
        )
    if merged["recovered"].isna().any():
        raise RuntimeError(
            "unconstrain_check: observable censored row(s) missing from "
            "unconstrain_demand() output -- date/item/period grid mismatch."
        )

    capped_err = merged["observed"] - merged["true_demand"]
    recovered_err = merged["recovered"] - merged["true_demand"]
    return {
        "n_observable_rows": int(len(merged)),
        "n_total_truth_stockouts": int(len(truth)),
        "capped_mae": float(capped_err.abs().mean()),
        "capped_bias": float(capped_err.mean()),
        "recovered_mae": float(recovered_err.abs().mean()),
        "recovered_bias": float(recovered_err.mean()),
    }


def main() -> None:
    gap = compute_unconstrain_gap()
    print("=" * 64)
    print("UNCONSTRAIN-VS-TRUTH CHECK  (data/_truth/truth_stockouts.csv)")
    print("=" * 64)
    print(
        f"{gap['n_observable_rows']} of {gap['n_total_truth_stockouts']} true censoring events "
        f"were observable (go-forward window only -- the '86-board reality', see module docstring)"
    )
    print(
        f"Capped (observed)   MAE vs truth: {gap['capped_mae']:.3f}  "
        f"(bias {gap['capped_bias']:+.3f})"
    )
    print(
        f"Recovered (P3)      MAE vs truth: {gap['recovered_mae']:.3f}  "
        f"(bias {gap['recovered_bias']:+.3f})"
    )
    if gap["recovered_mae"] >= gap["capped_mae"]:
        raise SystemExit(
            f"Unconstrain check FAILED: recovered demand (MAE {gap['recovered_mae']:.3f}) is "
            f"not closer to truth than capped observed demand (MAE {gap['capped_mae']:.3f}) "
            f"on the observable rows."
        )
    print("Unconstrain check: PASS -- recovery moves capped demand toward true_demand.")


if __name__ == "__main__":
    main()
