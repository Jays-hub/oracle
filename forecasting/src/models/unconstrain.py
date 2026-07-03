"""Phase-3 demand unconstraining -- recovers true demand on censored (sold-out)
day-items so the modeling target stops silently understating popular dishes.

The problem: clean_demand() (Phase 2) tags a day-item censored=True when the
kitchen 86'd it, but the observed `demand` value on that row is a LOWER BOUND on
true demand -- the guest who would have ordered dish #23 after the kitchen ran out
at #22 is invisible in the POS log. Feeding that capped value straight into the
point model's target (as Phase 2 does) systematically teaches the model to
under-forecast exactly the items it sells out of -- worst on the highest-Cu,
highest-margin dishes (construction_roadmap.md Phase 3 "Why now").

The method (Tobit-flavored censored regression / demand unconstraining, revenue-
management practice -- construction_roadmap.md Phase 3 "Practices" (b)): fit a
count distribution (Negative Binomial, or Poisson when the data shows no
overdispersion) to this item's own UNCENSORED history via method of moments, then
take the CONDITIONAL expectation of that distribution above the observed cap,
E[D | D > cap] -- not the plain unconditional mean of past demand. That
distinction is the whole game: a censored day is, by definition, a day true
demand exceeded a threshold most days don't reach, so it is a selected sample from
the right tail. Averaging it in with ordinary days (the first version of this
module tried exactly that) undershoots almost completely -- empirically, on this
project's real generated data, a plain historical mean corrected essentially
nothing (avg lift ~0.00 across 66 real censoring events; recovered MAE vs. the
hidden ground-truth stockout log stayed at the uncorrected 5.076, bias -5.076).
The tail expectation instead asks "given that today already beat every typical day
badly enough to sell out, how high does the distribution say it plausibly went?"
-- which cut MAE from 5.076 to 3.090 (bias -1.699) in the same experiment
(docs/phase_decisions/P3.md "Key Design Decisions" has the full before/after).

Distribution fit granularity: mean and variance are estimated from an
EXPANDING-WINDOW of this item's own UNCENSORED history at the (item_id,
service_period, day_of_week) grain -- same "typical Friday dinner" idea
baselines.py's Lag7Baseline already uses -- computed using only rows strictly
BEFORE the row being corrected (`.shift(1)` after `.expanding()`, mirroring
FeaturePipeline._add_lag_features's shift-then-roll discipline). Falls back to the
coarser (item_id, service_period) grain, ignoring day_of_week, when there isn't
yet enough same-weekday history to fit a stable variance. Recovered demand =
max(observed, estimate): a censored observation is a lower bound, so the
correction can only raise the target, never lower it -- the one constraint that
must hold structurally, not just usually.

Why expanding-window, not a single global fit over the whole series: a global fit
using the WHOLE series (including dates after the row being corrected) would let a
row early in the series get corrected using information from the future -- exactly
the class of leakage rule 02-feature-eng forbids for features, and just as real
here even though this is a target-correction step, not a feature. The expanding
window makes each row's correction a function of only its own past -- provably
safe to slice into any walk-forward fold afterward. See
test_correction_is_prefix_stable for the concrete invariant this buys.

Known, unavoidable limitation (see docs/phase_decisions/P3.md): the "uncensored"
comparison history this module fits against is itself not fully clean.
data/raw/eightysix_log.csv (the only observable stockout signal) is populated
only for the go-forward window (config/sim.yaml goforward_days) -- older days'
silent 86 events left no log entry, so some rows tagged censored=False in
clean_demand() are, in truth, already-capped sales the engine has no way to
detect. This is the "86-board reality" named in Practices (c): the data evaporates
nightly, which is why capture (Phase 1) had to come first. It biases every
distribution fit here slightly low; there is no fix available from data/raw/ alone.

Why NOT conditioned on menu era: era_demand_factors in sim.yaml move demand by at
most about +/-10% per item across eras -- a second-order effect next to the
day-of-week swing (dow_factors span 0.65-1.35). Adding era conditioning would
fragment the already-thin per-weekday history further for a small accuracy gain;
deferred, see docs/phase_decisions/P3.md.

Firewall (rule 01): never reads or references the hidden ground-truth store -- this
module operates only on clean_demand()'s already-observable output. Oracle-side
verification lives in forecasting/src/evaluate/unconstrain_check.py (the sanctioned
oracle reader), one directory this module never imports (rule 01 / .importlinter's
engine-truth-firewall contract).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

_FINE_KEY = ["item_id", "service_period", "day_of_week"]
_COARSE_KEY = ["item_id", "service_period"]


def _expanding_prior_mean(s: pd.Series) -> pd.Series:
    """Mean of non-null values strictly before each position (shift excludes self)."""
    return s.expanding(min_periods=1).mean().shift(1)


def _expanding_prior_var(s: pd.Series) -> pd.Series:
    """Sample variance (ddof=1) of non-null values strictly before each position."""
    return s.expanding(min_periods=2).var().shift(1)


def _expanding_prior_count(s: pd.Series) -> pd.Series:
    """Count of non-null values strictly before each position."""
    return s.notna().astype(int).cumsum().shift(1)


def _tail_conditional_mean(mean: float, var: float, cap: float) -> float:
    """E[D | D > cap] under a method-of-moments count distribution fit to
    (mean, var): Negative Binomial when the history is overdispersed (var > mean
    -- the common case for restaurant demand, see config/sim.yaml's own "NegBin
    demand" comment), Poisson otherwise (var <= mean, or too little history to
    show overdispersion). This is the textbook censored-regression treatment of a
    right-censored count observation: the expectation of the unobserved tail above
    the censoring point, not the unconditional mean.
    """
    if mean <= 0:
        return cap
    if var > mean:
        r = mean**2 / (var - mean)
        p = r / (r + mean)
        dist = stats.nbinom(r, p)
    else:
        dist = stats.poisson(mean)
    tail_prob = dist.sf(cap)
    if tail_prob < 1e-9:
        # cap is far beyond what this distribution considers plausible for this
        # item/day -- dividing by a near-zero tail probability is not reliable.
        # A minimal nudge above cap is the honest "we can't say much more than
        # 'higher'" answer rather than an unstable extrapolation.
        return cap + 1.0
    return float(dist.expect(lambda k: k, lb=cap + 1, conditional=True))


def unconstrain_demand(demand_df: pd.DataFrame, min_history: int = 8) -> pd.DataFrame:
    """Recover true demand on censored day-items via censored-regression-style
    (Tobit-flavored) demand unconstraining.

    Parameters
    ----------
    demand_df   : clean_demand()'s output --
                  [business_date, item_id, service_period, demand (int), censored (bool)]
    min_history : minimum prior UNCENSORED same-(item, service_period, day_of_week)
                  observations required to fit the fine-grained distribution;
                  below that, falls back to the coarser (item, service_period)
                  grain (ignoring day_of_week); with fewer than `min_history` prior
                  uncensored observations even at the coarse grain, the row is
                  left unchanged -- there is no reliable basis for a distribution
                  fit yet (only possible very early in an item's history).

    Returns
    -------
    Same schema as the input: [business_date, item_id, service_period, demand,
    censored]. `demand` is float64 throughout (a mix of untouched integer-valued
    sales and fractional recovered estimates can't share an int column) -- rows
    this function could not correct (uncensored, or censored with insufficient
    prior history) keep their original numeric value, just re-typed. Row order:
    sorted by (business_date, item_id, service_period), matching clean_demand()'s
    own convention.
    """
    required = {"business_date", "item_id", "service_period", "demand", "censored"}
    missing = required - set(demand_df.columns)
    if missing:
        raise ValueError(f"unconstrain_demand: missing required columns: {missing}")

    df = demand_df.copy()
    df["business_date"] = pd.to_datetime(df["business_date"])
    df = df.sort_values(["item_id", "service_period", "business_date"]).reset_index(drop=True)
    df["day_of_week"] = df["business_date"].dt.dayofweek

    # NaN out censored positions so the expanding stats -- which skip NaN when
    # computing mean/var -- only ever fit against genuine (uncensored) sales.
    masked = df["demand"].astype(float).where(~df["censored"])
    fine_groups = [df["item_id"], df["service_period"], df["day_of_week"]]
    coarse_groups = [df["item_id"], df["service_period"]]

    fine_mean = masked.groupby(fine_groups).transform(_expanding_prior_mean)
    fine_var = masked.groupby(fine_groups).transform(_expanding_prior_var)
    fine_count = masked.groupby(fine_groups).transform(_expanding_prior_count)
    coarse_mean = masked.groupby(coarse_groups).transform(_expanding_prior_mean)
    coarse_var = masked.groupby(coarse_groups).transform(_expanding_prior_var)
    coarse_count = masked.groupby(coarse_groups).transform(_expanding_prior_count)

    use_fine = fine_count >= min_history
    use_coarse = ~use_fine & (coarse_count >= min_history)
    correctable = df["censored"] & (use_fine | use_coarse)

    estimate = pd.Series(np.nan, index=df.index)
    for i in df.index[correctable]:
        if use_fine.loc[i]:
            m, v = fine_mean.loc[i], fine_var.loc[i]
        else:
            m, v = coarse_mean.loc[i], coarse_var.loc[i]
        v = float(v) if pd.notna(v) else 0.0
        estimate.loc[i] = _tail_conditional_mean(float(m), v, float(df.loc[i, "demand"]))

    can_correct = estimate.notna()
    corrected = df["demand"].astype(float)
    corrected = corrected.where(
        ~can_correct, np.maximum(df["demand"].astype(float), estimate)
    )

    n_censored = int(df["censored"].sum())
    n_corrected = int(can_correct.sum())
    n_uncorrectable = n_censored - n_corrected
    avg_lift = (
        float((corrected[can_correct] - df.loc[can_correct, "demand"]).mean())
        if n_corrected else 0.0
    )
    print(
        f"[unconstrain] {n_censored} censored rows: {n_corrected} corrected "
        f"(avg +{avg_lift:.2f} demand), {n_uncorrectable} left unchanged "
        f"(insufficient prior uncensored history)"
    )

    out = df[["business_date", "item_id", "service_period", "censored"]].copy()
    out["demand"] = corrected
    out["business_date"] = out["business_date"].dt.date
    return out[["business_date", "item_id", "service_period", "demand", "censored"]].sort_values(
        ["business_date", "item_id", "service_period"]
    ).reset_index(drop=True)
