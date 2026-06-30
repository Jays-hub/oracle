"""Synthetic restaurant data generator — Phase 1.

Writes data/raw/ (the messy export models read) and data/_truth/ (hidden ground
truth used only by forecasting/src/evaluate/ for scoring). No other module may
write _truth/ or read it except evaluate/.
"""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SIM_CFG = _REPO_ROOT / "config" / "sim.yaml"
_DEFAULT_RAW_DIR = _REPO_ROOT / "data" / "raw"
_DEFAULT_TRUTH_DIR = _REPO_ROOT / "data" / "_truth"


def _assert_not_truth_path(p: Path) -> None:
    if "_truth" in str(p):
        raise ValueError(f"raw_dir must not contain '_truth': {p}")


def _load_cfg(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _era_id_for_date(d: date, eras: list[dict]) -> int:
    eid = 0
    for era in eras:
        if d >= date.fromisoformat(era["start"]):
            eid = era["id"]
    return eid


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def _rand_time(rng: np.random.Generator, hour_start: int, hour_end: int) -> time:
    total_secs = (hour_end - hour_start) * 3600
    secs = int(rng.integers(0, total_secs))
    return (datetime(2000, 1, 1, hour_start) + timedelta(seconds=secs)).time()


class RestaurantSimulator:
    def __init__(self, cfg_path: Path = _DEFAULT_SIM_CFG) -> None:
        self.cfg = _load_cfg(cfg_path)
        self.rng = np.random.default_rng(self.cfg["seed"])
        self._dates = pd.date_range(
            self.cfg["date_range"]["start"],
            self.cfg["date_range"]["end"],
            freq="D",
        )
        self._goforward_cutoff = self._dates[-1].date() - timedelta(
            days=self.cfg["goforward_days"]
        )
        self._eras: list[dict] = self.cfg["menu_eras"]
        self._svc_periods: list[dict] = self.cfg["service_periods"]
        self._item_ids: list[str] = list(self.cfg["item_demand"].keys())
        self._validate_config()

    def _validate_config(self) -> None:
        """Fail loud if any per-item, era-indexed config doesn't cover every menu era.

        Guards the era_id lookups (menu_prices / era_demand_factors / item_name_aliases):
        adding an era to menu_eras without extending every per-item list raises here with a
        named item, not an opaque IndexError/KeyError deep inside generation. Uses >= so
        extra trailing entries (e.g. a test that truncates menu_eras) are harmless.
        """
        n_eras = len(self._eras)
        era_ids = set(range(n_eras))
        prices = self.cfg["menu_prices"]
        era_factors = self.cfg["era_demand_factors"]
        aliases = self.cfg["item_name_aliases"]
        for item_id in self._item_ids:
            if len(aliases.get(item_id, [])) < n_eras:
                raise ValueError(
                    f"item_name_aliases[{item_id}] has {len(aliases.get(item_id, []))} "
                    f"entries; need >= {n_eras} (one per menu era)."
                )
            if len(era_factors.get(item_id, [])) < n_eras:
                raise ValueError(
                    f"era_demand_factors[{item_id}] has {len(era_factors.get(item_id, []))} "
                    f"entries; need >= {n_eras} (one per menu era)."
                )
            missing = era_ids - set(prices.get(item_id, {}).keys())
            if missing:
                raise ValueError(
                    f"menu_prices[{item_id}] missing era ids {sorted(missing)} "
                    f"(need keys 0..{n_eras - 1})."
                )

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    def run(self, raw_dir: Path = _DEFAULT_RAW_DIR, truth_dir: Path = _DEFAULT_TRUTH_DIR) -> None:
        _assert_not_truth_path(raw_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        truth_dir.mkdir(parents=True, exist_ok=True)

        weather_actuals, weather_forecast = self._gen_weather()
        events = self._gen_events()

        # Demand responds to ACTUAL weather; the model is served the forecast at decision
        # time. Driving demand from the forecast would make actuals causally inert and the
        # forecast a perfect predictor — the opposite of the decision-time lesson. (audit #6)
        truth_demand = self._gen_truth_demand(weather_actuals, events)
        truth_stockouts, observed_demand = self._apply_censoring(truth_demand)
        eightysix_log = self._gen_eightysix_log(truth_stockouts)
        pos_sales = self._gen_pos_sales(observed_demand)
        reservations = self._gen_reservations(observed_demand)
        truth_recipes, recipes_stated = self._gen_recipes()
        invoices, truth_spoilage = self._gen_invoices(truth_demand, truth_recipes)

        # Write raw/
        pos_sales.to_csv(raw_dir / "pos_sales.csv", index=False)
        reservations.to_csv(raw_dir / "reservations.csv", index=False)
        invoices.to_csv(raw_dir / "invoices.csv", index=False)
        recipes_stated.to_csv(raw_dir / "recipes_stated.csv", index=False)
        weather_actuals.to_csv(raw_dir / "weather_actuals.csv", index=False)
        weather_forecast.to_csv(raw_dir / "weather_forecast.csv", index=False)
        events.to_csv(raw_dir / "events.csv", index=False)
        eightysix_log.to_csv(raw_dir / "eightysix_log.csv", index=False)

        # Write _truth/
        truth_demand.to_csv(truth_dir / "truth_demand.csv", index=False)
        truth_stockouts.to_csv(truth_dir / "truth_stockouts.csv", index=False)
        truth_recipes.to_csv(truth_dir / "truth_recipes.csv", index=False)
        truth_spoilage.to_csv(truth_dir / "truth_spoilage.csv", index=False)
        self._write_truth_params(truth_dir, raw_dir, pos_sales, truth_demand, truth_stockouts)

    # ------------------------------------------------------------------ #
    #  Weather                                                             #
    # ------------------------------------------------------------------ #

    def _gen_weather(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        wcfg = self.cfg["weather"]
        hi_summer = wcfg["base_temp_high_summer"]
        hi_winter = wcfg["base_temp_high_winter"]
        amp = (hi_summer - hi_winter) / 2.0
        mid = (hi_summer + hi_winter) / 2.0

        rows_act, rows_fct = [], []
        for ts in self._dates:
            d = ts.date()
            day_of_year = d.timetuple().tm_yday
            # Sine: peak ~Jul 15 = day 196
            seasonal = mid + amp * math.sin(2 * math.pi * (day_of_year - 196 + 365) / 365)
            noise = self.rng.normal(0, wcfg["temp_daily_noise_std"])
            temp_high = round(seasonal + noise, 1)
            temp_low = round(temp_high - float(self.rng.uniform(12, 20)), 1)
            precip = 0.0
            if self.rng.random() < wcfg["precip_daily_prob"]:
                precip = round(
                    float(self.rng.gamma(wcfg["precip_gamma_shape"], wcfg["precip_gamma_scale"])),
                    1,
                )
            rows_act.append({"date": d, "temp_high": temp_high, "temp_low": temp_low, "precip_mm": precip})

            # Forecast: issued morning of decision day; diverges from actuals
            ftemp_high = round(temp_high + self.rng.normal(0, wcfg["forecast_temp_noise_std"]), 1)
            ftemp_low = round(ftemp_high - float(self.rng.uniform(12, 20)), 1)
            fprecip = round(
                float(precip * self.rng.lognormal(0, wcfg["forecast_precip_noise_lognormal_sigma"])),
                1,
            ) if precip > 0 else (
                float(self.rng.gamma(1.0, 1.0)) if self.rng.random() < 0.08 else 0.0
            )
            rows_fct.append({
                "date": d,
                "temp_high": ftemp_high,
                "temp_low": ftemp_low,
                "precip_mm": fprecip,
                "forecast_issued_on": d,
            })

        return pd.DataFrame(rows_act), pd.DataFrame(rows_fct)

    # ------------------------------------------------------------------ #
    #  Events                                                              #
    # ------------------------------------------------------------------ #

    def _gen_events(self) -> pd.DataFrame:
        ecfg = self.cfg["events"]
        bands = ecfg["attendance_bands"]
        weights = np.array(ecfg["attendance_weights"], dtype=float)
        weights /= weights.sum()
        rows = []
        # Group dates by month
        months: dict[tuple[int, int], list[date]] = {}
        for ts in self._dates:
            key = (ts.year, ts.month)
            months.setdefault(key, []).append(ts.date())

        for month_dates in months.values():
            n_events = int(self.rng.poisson(ecfg["events_per_month"]))
            weekends = [d for d in month_dates if _is_weekend(d)]
            weekdays = [d for d in month_dates if not _is_weekend(d)]
            pool = weekends if (weekends and self.rng.random() < ecfg["weekend_weight"]) else weekdays
            if not pool:
                pool = month_dates
            chosen = list(
                self.rng.choice(pool, size=min(n_events, len(pool)), replace=False)
            )
            for ev_date in chosen:
                start_hour = int(self.rng.choice([19, 20, 21]))
                band = str(self.rng.choice(bands, p=weights))
                rows.append({
                    "event_date": ev_date,
                    "venue": ecfg["venue"],
                    "start_time": f"{start_hour:02d}:00",
                    "expected_attendance_band": band,
                })
        return pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["event_date", "venue", "start_time", "expected_attendance_band"]
        )

    # ------------------------------------------------------------------ #
    #  Truth demand (Step A)                                               #
    # ------------------------------------------------------------------ #

    def _build_weather_multipliers(self, weather_df: pd.DataFrame) -> dict[date, float]:
        wcfg = self.cfg["weather"]
        fct = weather_df.set_index("date")
        mults: dict[date, float] = {}
        temp_highs = fct["temp_high"].to_dict()

        for ts in self._dates:
            d = ts.date()
            th = temp_highs.get(d, 60.0)
            mult = 1.0
            if fct.loc[d, "precip_mm"] > wcfg["rain_threshold_mm"]:
                mult *= wcfg["rain_demand_factor"]
            if th > wcfg["heat_threshold_f"]:
                mult *= wcfg["heat_demand_factor"]
            # First warm day: today warm, avg of prior 7 days cold
            past_7 = [
                temp_highs.get((ts - timedelta(days=i)).date(), 40.0)
                for i in range(1, 8)
            ]
            if th > wcfg["first_warm_day_trigger_f"] and np.mean(past_7) < wcfg["first_warm_day_cold_window_avg_f"]:
                mult *= wcfg["first_warm_day_factor"]
            mults[d] = mult
        return mults

    def _build_event_multipliers(self, events: pd.DataFrame) -> dict[tuple[date, str], float]:
        ecfg = self.cfg["events"]
        lift_map = ecfg["demand_lift"]
        ev_lookup: dict[date, str] = {}
        for _, row in events.iterrows():
            ev_lookup[row["event_date"]] = row["expected_attendance_band"]

        mults: dict[tuple[date, str], float] = {}
        for ts in self._dates:
            d = ts.date()
            for svc in self._svc_periods:
                mult = 1.0
                if d in ev_lookup:
                    band = ev_lookup[d]
                    # Event lift applies to dinner (evening service) primarily
                    if svc["name"] == "dinner":
                        mult = lift_map[band]
                    else:
                        mult = 1.0 + (lift_map[band] - 1.0) * 0.3
                mults[(d, svc["name"])] = mult
        return mults

    def _gen_truth_demand(
        self, weather_actuals: pd.DataFrame, events: pd.DataFrame
    ) -> pd.DataFrame:
        dow_factors = self.cfg["dow_factors"]
        season_factors = self.cfg["season_factors"]
        item_demand_cfg = self.cfg["item_demand"]
        era_factors = self.cfg["era_demand_factors"]
        aliases = self.cfg["item_name_aliases"]

        weather_mults = self._build_weather_multipliers(weather_actuals)
        event_mults = self._build_event_multipliers(events)

        rows = []
        for ts in self._dates:
            d = ts.date()
            dow_mult = dow_factors[d.weekday()]
            season_mult = season_factors[d.month]
            weather_mult = weather_mults[d]
            era_id = _era_id_for_date(d, self._eras)

            for svc in self._svc_periods:
                svc_name = svc["name"]
                event_mult = event_mults[(d, svc_name)]

                for item_id in self._item_ids:
                    dcfg = item_demand_cfg[item_id]
                    base_mu = dcfg["lunch_mu"] if svc_name == "lunch" else dcfg["dinner_mu"]
                    era_mult = era_factors[item_id][era_id]
                    # Lunch scales down a bit on weekends (brunch replaces)
                    svc_mult = 0.85 if (svc_name == "lunch" and _is_weekend(d)) else 1.0

                    mu = base_mu * dow_mult * season_mult * era_mult * event_mult * weather_mult * svc_mult
                    mu = max(mu, 0.01)

                    r = dcfg["dispersion"]
                    zero_prob = dcfg.get("zero_prob", 0.0)

                    if zero_prob > 0 and self.rng.random() < zero_prob:
                        demand = 0
                    else:
                        p = r / (r + mu)
                        demand = int(self.rng.negative_binomial(r, p))

                    era_alias_list = aliases[item_id]
                    item_name = era_alias_list[era_id] if era_id < len(era_alias_list) else aliases[item_id][-1]

                    rows.append({
                        "business_date": d,
                        "service_period": svc_name,
                        "item_id": item_id,
                        "item_name": item_name,
                        "true_demand": demand,
                    })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ #
    #  Censoring (Step B)                                                  #
    # ------------------------------------------------------------------ #

    def _apply_censoring(
        self, truth_demand: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        caps = self.cfg["capacity_caps"]
        threshold = self.cfg["censoring_threshold"]

        stockout_rows = []
        observed = truth_demand.copy()
        observed["observed_demand"] = observed["true_demand"]

        for item_id in self._item_ids:
            # Effective sellable capacity: the kitchen 86s a touch before the nominal
            # prep cap (the last few portions are unreliable); censoring_threshold scales it.
            effective_cap = int(round(caps[item_id] * threshold))
            # A day is censored ONLY when true demand exceeds the effective cap — the guest
            # then sees the cap and true demand is invisible. Days at-or-below the cap are
            # NOT censored (observed == true) and must never enter truth_stockouts, or the
            # Phase-3 unconstraining answer key is polluted with non-events.
            mask = (observed["item_id"] == item_id) & (observed["true_demand"] > effective_cap)
            for idx in observed.index[mask]:
                td = int(observed.at[idx, "true_demand"])
                observed.at[idx, "observed_demand"] = effective_cap
                stockout_rows.append({
                    "business_date": observed.at[idx, "business_date"],
                    "service_period": observed.at[idx, "service_period"],
                    "item_id": item_id,
                    "item_name": observed.at[idx, "item_name"],
                    "cap": effective_cap,
                    "true_demand": td,
                    "observed_demand": effective_cap,
                })

        truth_stockouts = pd.DataFrame(stockout_rows) if stockout_rows else pd.DataFrame(
            columns=["business_date", "service_period", "item_id", "item_name",
                     "cap", "true_demand", "observed_demand"]
        )
        return truth_stockouts, observed

    # ------------------------------------------------------------------ #
    #  Eightysix log                                                       #
    # ------------------------------------------------------------------ #

    def _gen_eightysix_log(self, truth_stockouts: pd.DataFrame) -> pd.DataFrame:
        rows = []
        dinner_cfg = next(s for s in self._svc_periods if s["name"] == "dinner")
        for _, row in truth_stockouts.iterrows():
            d = row["business_date"]
            if isinstance(d, (pd.Timestamp, datetime)):
                d = d.date() if hasattr(d, "date") else d
            # Only populate go-forward window; historical board was wiped nightly
            if d >= self._goforward_cutoff:
                svc = next(
                    (s for s in self._svc_periods if s["name"] == row["service_period"]),
                    dinner_cfg,
                )
                t = _rand_time(self.rng, svc["hour_start"] + 1, svc["hour_end"])
                rows.append({
                    "business_date": d,
                    "item_name": row["item_name"],
                    "time_86d": str(t),
                })
        return pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["business_date", "item_name", "time_86d"]
        )

    # ------------------------------------------------------------------ #
    #  POS sales (Step C)                                                  #
    # ------------------------------------------------------------------ #

    def _gen_pos_sales(self, observed_demand: pd.DataFrame) -> pd.DataFrame:
        pcfg = self.cfg["pollution"]
        menu_prices = self.cfg["menu_prices"]
        categories = {
            "braised_short_rib": "Entree", "pan_seared_salmon": "Entree",
            "half_roast_chicken": "Entree", "house_burger": "Entree",
            "ribeye_steak_12oz": "Entree", "duck_confit": "Entree",
            "butter_poached_cod": "Entree", "wild_mushroom_risotto": "Entree",
            "classic_caesar_salad": "Starter", "pappardelle_bolognese": "Pasta",
            "tuna_tartare": "Starter",
        }
        regular_servers = [f"S{i:03d}" for i in range(3, 21)]

        rows = []
        check_counter = 0
        line_counter = 0

        for _, drow in observed_demand.iterrows():
            d = drow["business_date"]
            svc_name = drow["service_period"]
            item_id = drow["item_id"]
            item_name = drow["item_name"]
            demand = int(drow["observed_demand"])
            if demand == 0:
                continue

            era_id = _era_id_for_date(
                d.date() if hasattr(d, "date") else d, self._eras
            )
            price = menu_prices[item_id][era_id]
            svc = next(s for s in self._svc_periods if s["name"] == svc_name)
            cat = categories.get(item_id, "Other")

            for _ in range(demand):
                check_counter += 1
                line_counter += 1
                sold_at = datetime.combine(
                    d.date() if hasattr(d, "date") else d,
                    _rand_time(self.rng, svc["hour_start"], svc["hour_end"]),
                )
                server = str(self.rng.choice(regular_servers))
                rows.append({
                    "check_id": f"CHK{check_counter:07d}",
                    "line_id": f"L{line_counter:08d}",
                    "business_date": d,
                    "sold_at": sold_at,
                    "item_name": item_name,
                    "category": cat,
                    "menu_price": price,
                    "qty": 1,
                    "modifiers": "",
                    "discount_amount": 0.0,
                    "comp_flag": None,
                    "void_flag": False,
                    "server_id": server,
                })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        n = len(df)
        # Comps
        n_comp = int(n * pcfg["comp_rate"])
        comp_idx = self.rng.choice(df.index, size=n_comp, replace=False)
        for idx in comp_idx:
            discount = round(float(df.at[idx, "menu_price"]) * float(self.rng.uniform(0.5, 1.0)), 2)
            df.at[idx, "discount_amount"] = discount
            df.at[idx, "comp_flag"] = bool(self.rng.random() < pcfg["comp_flagged_rate"])

        # Staff meals (add new rows rather than relabelling real sales)
        n_staff = int(n * pcfg["staff_meal_rate"])
        staff_items = ["classic_caesar_salad", "house_burger", "pappardelle_bolognese"]
        for _ in range(n_staff):
            s_item = str(self.rng.choice(staff_items))
            # pick a random existing date
            ref_row = df.iloc[int(self.rng.integers(0, len(df)))]
            ref_date = ref_row["business_date"]
            era_id = _era_id_for_date(
                ref_date.date() if hasattr(ref_date, "date") else ref_date,
                self._eras,
            )
            s_price = menu_prices[s_item][era_id]
            staff_alias = self.cfg["item_name_aliases"][s_item][era_id]
            s_server = str(self.rng.choice(pcfg["staff_server_ids"]))
            svc = next(s for s in self._svc_periods if s["name"] == "lunch")
            check_counter += 1
            line_counter += 1
            sold_at = datetime.combine(
                ref_date.date() if hasattr(ref_date, "date") else ref_date,
                _rand_time(self.rng, svc["hour_start"], svc["hour_end"]),
            )
            df.loc[len(df)] = {
                "check_id": f"CHK{check_counter:07d}",
                "line_id": f"L{line_counter:08d}",
                "business_date": ref_date,
                "sold_at": sold_at,
                "item_name": staff_alias,
                "category": categories.get(s_item, "Other"),
                "menu_price": s_price,
                "qty": 1,
                "modifiers": "Staff",
                "discount_amount": s_price,
                "comp_flag": None,
                "void_flag": False,
                "server_id": s_server,
            }

        # Voids
        n_void = int(n * pcfg["void_rate"])
        void_idx = self.rng.choice(df.index[:n], size=n_void, replace=False)
        df.loc[void_idx, "void_flag"] = True

        return df.sort_values(["business_date", "sold_at"]).reset_index(drop=True)

    # ------------------------------------------------------------------ #
    #  Reservations (Step D)                                               #
    # ------------------------------------------------------------------ #

    def _gen_reservations(self, observed_demand: pd.DataFrame) -> pd.DataFrame:
        rcfg = self.cfg["reservations"]
        party_weights = np.array(rcfg["party_size_weights"], dtype=float)
        party_weights /= party_weights.sum()
        party_sizes = list(range(1, len(party_weights) + 1))

        daily_covers = (
            observed_demand.groupby(["business_date", "service_period"])["observed_demand"]
            .sum()
            .reset_index()
        )

        rows = []
        for _, crow in daily_covers.iterrows():
            d = crow["business_date"]
            svc_name = crow["service_period"]
            total_covers = int(crow["observed_demand"])
            if total_covers == 0:
                continue

            coverage = rcfg["weekend_coverage"] if _is_weekend(
                d.date() if hasattr(d, "date") else d
            ) else rcfg["weeknight_coverage"]
            reservation_covers = int(total_covers * coverage)

            svc = next(s for s in self._svc_periods if s["name"] == svc_name)
            allocated = 0
            while allocated < reservation_covers:
                psize = int(self.rng.choice(party_sizes, p=party_weights))
                if allocated + psize > reservation_covers + 4:
                    psize = max(1, reservation_covers - allocated)
                days_ahead = int(self.rng.integers(1, 15))
                base_date = d.date() if hasattr(d, "date") else d
                created_at = datetime.combine(base_date - timedelta(days=days_ahead),
                                              time(int(self.rng.integers(9, 21))))
                reserved_for = datetime.combine(
                    base_date,
                    _rand_time(self.rng, svc["hour_start"], svc["hour_end"]),
                )
                r_rand = self.rng.random()
                if r_rand < rcfg["no_show_rate"]:
                    status = "no_show"
                elif r_rand < rcfg["no_show_rate"] + rcfg["cancellation_rate"]:
                    status = "cancelled"
                else:
                    status = "seated"
                source = str(self.rng.choice(["resy", "phone"], p=[0.7, 0.3]))
                rows.append({
                    "reservation_id": str(uuid.uuid4())[:12],
                    "created_at": created_at,
                    "reserved_for": reserved_for,
                    "party_size": psize,
                    "status": status,
                    "source": source,
                })
                allocated += psize

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ #
    #  Recipes (Step E)                                                    #
    # ------------------------------------------------------------------ #

    def _gen_recipes(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        true_r = self.cfg["true_recipes"]
        noise_cfg = self.cfg["stated_recipe_noise"]
        ingr_cfg = self.cfg["ingredients"]
        # prep_type comes from items config (read via config.py), but we embed it here
        prep_types = {
            "braised_short_rib": "batch", "pan_seared_salmon": "batch",
            "half_roast_chicken": "batch", "house_burger": "batch",
            "ribeye_steak_12oz": "batch", "duck_confit": "batch",
            "butter_poached_cod": "batch", "wild_mushroom_risotto": "made_to_order",
            "classic_caesar_salad": "made_to_order", "pappardelle_bolognese": "made_to_order",
            "tuna_tartare": "made_to_order",
        }
        display_names = {
            "braised_short_rib": "Braised Short Rib", "pan_seared_salmon": "Pan-Seared Salmon",
            "half_roast_chicken": "Half Roast Chicken", "house_burger": "House Burger",
            "ribeye_steak_12oz": "Ribeye Steak 12oz", "duck_confit": "Duck Confit",
            "butter_poached_cod": "Butter Poached Cod",
            "wild_mushroom_risotto": "Wild Mushroom Risotto",
            "classic_caesar_salad": "Classic Caesar Salad",
            "pappardelle_bolognese": "Pappardelle Bolognese",
            "tuna_tartare": "Tuna Tartare",
        }

        truth_rows, stated_rows = [], []
        for item_id, lines in true_r.items():
            dish_name = display_names[item_id]
            pt = prep_types[item_id]
            for line in lines:
                ing_id = line["ingredient_id"]
                ing_name = ingr_cfg[ing_id]["name"]
                qty = float(line["qty"])
                unit = line["unit"]
                truth_rows.append({
                    "dish_name": dish_name,
                    "ingredient": ing_name,
                    "ingredient_id": ing_id,
                    "qty_per_portion": qty,
                    "unit": unit,
                    "prep_type": pt,
                })

                # Degrade for stated version
                if self.rng.random() < noise_cfg["drop_line_prob"]:
                    continue  # silently omit
                is_by_feel = self.rng.random() < noise_cfg["by_feel_prob"]
                sigma = noise_cfg["by_feel_sigma"] if is_by_feel else noise_cfg["spec_sheet_sigma"]
                noise = float(self.rng.lognormal(0, sigma))
                stated_qty = round(qty * noise, 3) if qty > 0.01 else qty
                # Mix units: occasionally convert to oz/g
                stated_unit = unit
                if unit == "lb" and self.rng.random() < 0.3:
                    stated_qty = round(stated_qty * 16, 1)
                    stated_unit = "oz"
                confidence = "by_feel" if is_by_feel else "spec_sheet"
                stated_rows.append({
                    "dish_name": dish_name,
                    "ingredient": ing_name,
                    "qty_per_portion": stated_qty,
                    "unit": stated_unit,
                    "prep_type": pt,
                    "confidence": confidence,
                })

        return pd.DataFrame(truth_rows), pd.DataFrame(stated_rows)

    # ------------------------------------------------------------------ #
    #  Invoices + spoilage (Step F)                                        #
    # ------------------------------------------------------------------ #

    def _gen_invoices(
        self, truth_demand: pd.DataFrame, truth_recipes: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        icfg = self.cfg["invoices"]
        scfg = self.cfg["spoilage"]
        ingr_cfg = self.cfg["ingredients"]
        perishables = set(scfg["perishable_ingredient_ids"])

        # Ingredient depletion per day
        recipe_qty: dict[tuple[str, str], float] = {}
        for _, r in truth_recipes.iterrows():
            key = (r["dish_name"], r["ingredient_id"])
            recipe_qty[key] = float(r["qty_per_portion"])

        dish_to_item: dict[str, str] = {
            "Braised Short Rib": "braised_short_rib",
            "Pan-Seared Salmon": "pan_seared_salmon",
            "Half Roast Chicken": "half_roast_chicken",
            "House Burger": "house_burger",
            "Ribeye Steak 12oz": "ribeye_steak_12oz",
            "Duck Confit": "duck_confit",
            "Butter Poached Cod": "butter_poached_cod",
            "Wild Mushroom Risotto": "wild_mushroom_risotto",
            "Classic Caesar Salad": "classic_caesar_salad",
            "Pappardelle Bolognese": "pappardelle_bolognese",
            "Tuna Tartare": "tuna_tartare",
        }

        daily_demand_by_item: dict[tuple[date, str], int] = {}
        for _, row in truth_demand.iterrows():
            d = row["business_date"]
            if hasattr(d, "date"):
                d = d.date()
            key = (d, row["item_id"])
            daily_demand_by_item[key] = daily_demand_by_item.get(key, 0) + int(row["true_demand"])

        # Aggregate per-ingredient depletion per ordering week
        order_days = set(icfg["order_dow"])
        ingredient_depletion_since_last: dict[str, float] = {
            ing: 0.0 for ing in ingr_cfg
        }

        supplier_map = {
            "beef_short_rib": "US Foods", "salmon_fillet": "US Foods",
            "whole_chicken": "US Foods", "ground_beef": "US Foods",
            "beef_ribeye": "US Foods", "duck_leg": "US Foods",
            "cod_fillet": "US Foods", "arborio_rice": "Local Produce Co",
            "mushroom_mix": "Local Produce Co", "romaine_lettuce": "Local Produce Co",
            "pappardelle": "US Foods", "beef_ragu": "US Foods",
            "tuna_ahi": "US Foods", "butter": "US Foods",
            "heavy_cream": "US Foods", "parmesan": "US Foods",
            "garlic": "Local Produce Co", "white_wine": "Local Produce Co",
        }
        desc_map = {
            "beef_short_rib": "Beef Short Ribs BNLS",
            "salmon_fillet": "Atlantic Salmon Fillet 8oz",
            "whole_chicken": "Whole Chicken Air-Chilled",
            "ground_beef": "Ground Beef 80/20 Bulk",
            "beef_ribeye": "USDA Choice Ribeye 12oz",
            "duck_leg": "Duck Leg Confit-Ready",
            "cod_fillet": "Atlantic Cod Fillet 6oz",
            "arborio_rice": "Arborio Rice 25lb",
            "mushroom_mix": "Mixed Mushroom Blend",
            "romaine_lettuce": "Romaine Hearts 6-ct",
            "pappardelle": "Pappardelle Egg Pasta Dry",
            "beef_ragu": "House Ragu Frozen",
            "tuna_ahi": "Ahi Tuna Loin Sashimi-Grade",
            "butter": "Unsalted Butter 36ct",
            "heavy_cream": "Heavy Cream 1qt",
            "parmesan": "Parmesan Reggiano Wedge",
            "garlic": "Fresh Garlic 5lb",
            "white_wine": "Cooking Wine Chablis 750ml",
        }
        pack_size_map = {
            "beef_short_rib": (10, "lb"), "salmon_fillet": (1, "each"),
            "whole_chicken": (1, "each"), "ground_beef": (5, "lb"),
            "beef_ribeye": (1, "each"), "duck_leg": (1, "each"),
            "cod_fillet": (1, "each"), "arborio_rice": (25, "lb"),
            "mushroom_mix": (5, "lb"), "romaine_lettuce": (1, "case"),
            "pappardelle": (5, "lb"), "beef_ragu": (5, "lb"),
            "tuna_ahi": (1, "each"), "butter": (36, "each"),
            "heavy_cream": (1, "qt"), "parmesan": (5, "lb"),
            "garlic": (5, "lb"), "white_wine": (12, "bottle"),
        }
        unit_cost_map = {
            "beef_short_rib": 8.50, "salmon_fillet": 12.00,
            "whole_chicken": 4.20, "ground_beef": 5.80,
            "beef_ribeye": 18.00, "duck_leg": 9.50,
            "cod_fillet": 11.00, "arborio_rice": 0.90,
            "mushroom_mix": 4.50, "romaine_lettuce": 2.80,
            "pappardelle": 2.20, "beef_ragu": 6.00,
            "tuna_ahi": 22.00, "butter": 0.45,
            "heavy_cream": 3.50, "parmesan": 14.00,
            "garlic": 2.40, "white_wine": 8.00,
        }

        # True recipes for depletion calculation: item_id -> list of {ing_id, qty}
        true_recipe_lookup: dict[str, list[tuple[str, float]]] = {}
        for _, r in truth_recipes.iterrows():
            item_id = dish_to_item.get(r["dish_name"])
            if item_id:
                true_recipe_lookup.setdefault(item_id, []).append(
                    (r["ingredient_id"], float(r["qty_per_portion"]))
                )

        invoice_rows, spoilage_rows = [], []
        inv_counter = 0
        week_start: date | None = None
        weekly_purchases: dict[str, float] = {ing: 0.0 for ing in ingr_cfg}

        for ts in self._dates:
            d = ts.date()

            # Accumulate daily depletion
            for item_id, lines in true_recipe_lookup.items():
                day_demand = daily_demand_by_item.get((d, item_id), 0)
                for ing_id, qty in lines:
                    ingredient_depletion_since_last[ing_id] = (
                        ingredient_depletion_since_last.get(ing_id, 0.0) + day_demand * qty
                    )

            if d.weekday() not in order_days:
                continue

            # New ordering week
            if week_start is None:
                week_start = d
            delivery_date = d + timedelta(days=1)

            for ing_id in ingr_cfg:
                depletion = ingredient_depletion_since_last.get(ing_id, 0.0)
                if depletion < 0.01:
                    ingredient_depletion_since_last[ing_id] = 0.0
                    continue
                noise = float(self.rng.lognormal(0, icfg["order_noise_std"]))
                order_qty = depletion * icfg["over_order_bias"] * noise
                pack, pack_unit = pack_size_map[ing_id]
                n_packs = max(1, math.ceil(order_qty / pack))
                base_cost = unit_cost_map[ing_id]
                # Price fluctuates week to week
                unit_cost = round(base_cost * float(self.rng.lognormal(0, 0.04)), 2)
                ext_cost = round(unit_cost * n_packs, 2)
                inv_counter += 1
                invoice_rows.append({
                    "invoice_id": f"INV{inv_counter:06d}",
                    "supplier": supplier_map[ing_id],
                    "delivery_date": delivery_date,
                    "product_desc": desc_map[ing_id],
                    "pack_size": pack,
                    "unit": pack_unit,
                    "qty_ordered": n_packs,
                    "unit_cost": unit_cost,
                    "ext_cost": ext_cost,
                })
                weekly_purchases[ing_id] = weekly_purchases.get(ing_id, 0.0) + n_packs * pack

                if ing_id in perishables:
                    spoil_qty = round(n_packs * pack * scfg["weekly_spoilage_rate"], 3)
                    if spoil_qty > 0:
                        spoilage_rows.append({
                            "ingredient": ingr_cfg[ing_id]["name"],
                            "ingredient_id": ing_id,
                            "period_start": week_start,
                            "period_end": d,
                            "spoilage_qty": spoil_qty,
                            "unit": pack_unit,
                        })

                ingredient_depletion_since_last[ing_id] = 0.0

            week_start = d

        return pd.DataFrame(invoice_rows), pd.DataFrame(spoilage_rows)

    # ------------------------------------------------------------------ #
    #  Truth params                                                        #
    # ------------------------------------------------------------------ #

    def _write_truth_params(
        self,
        truth_dir: Path,
        raw_dir: Path,
        pos_sales: pd.DataFrame,
        truth_demand: pd.DataFrame,
        truth_stockouts: pd.DataFrame,
    ) -> None:
        params = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "seed": self.cfg["seed"],
            "date_range": self.cfg["date_range"],
            "goforward_days": self.cfg["goforward_days"],
            "total_pos_rows": len(pos_sales),
            "total_demand_rows": len(truth_demand),
            "total_stockout_rows": len(truth_stockouts),
            "item_ids": self._item_ids,
            "n_menu_eras": len(self._eras),
            "pollution": self.cfg["pollution"],
            "capacity_caps": self.cfg["capacity_caps"],
            "censoring_threshold": self.cfg["censoring_threshold"],
        }
        (truth_dir / "truth_params.yaml").write_text(
            yaml.dump(params, default_flow_style=False), encoding="utf-8"
        )


def run(
    sim_cfg: Path = _DEFAULT_SIM_CFG,
    raw_dir: Path = _DEFAULT_RAW_DIR,
    truth_dir: Path = _DEFAULT_TRUTH_DIR,
) -> None:
    """Top-level entry point. Called by tests and CLI."""
    RestaurantSimulator(sim_cfg).run(raw_dir, truth_dir)


if __name__ == "__main__":
    run()
