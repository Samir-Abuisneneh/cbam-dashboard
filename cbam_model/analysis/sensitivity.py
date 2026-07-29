"""One-at-a-time sensitivity analysis on the maritime layer.

Answers the question most likely to come up at viva: which assumption actually
drives the result. Each parameter is varied while everything else is held
constant, and the change in per-voyage carbon cost is recorded and ranked.

This runs on the maritime layer only, because that is the layer built entirely
from sourced data. A sweep over the CBAM layer would mostly be measuring the
placeholder emissions still standing in for Riya's table.

Limitation to state in the methodology: this is a one-at-a-time sweep, so it
captures each parameter's individual leverage but not interactions. Carbon price
and voyage emissions enter multiplicatively, so their joint effect exceeds the
sum of the two individual effects.
"""

import pandas as pd

from ..config import regulatory_constants as rc
from ..config import vessel_logistics as vl
from ..model import total_cost

# Parameters swept, and how each is perturbed. These are the levers that
# actually exist in Gayu's pipeline: engine power and load set fuel burn, speed
# sets voyage time, and the carbon factor and price convert that into cost.
SWEPT_PARAMETERS = (
    "main_engine_power_kw",
    "service_speed_knots",
    "engine_load_fraction",
    "sfoc_g_per_kwh",
    "vlsfo_carbon_factor",
    "carbon_price",
    "port_days",
    "fueleu_actual_intensity_gco2e_mj",
)


def _profile_with(corridor, vessel, route, overrides):
    """Rebuild a voyage profile with one input perturbed."""
    power = (
        vl.GAS_CARRIER["main_engine_power_kw"]
        if vessel == "gas_carrier"
        else vl.CONTAINER_SHIPS[corridor]["main_engine_power_kw"]
    )
    speed = (
        vl.SPEED_SCENARIOS_KNOTS["base"]
        if vessel == "gas_carrier"
        else vl.CONTAINER_SHIPS[corridor]["service_speed_knots"]
    )
    power = overrides.get("main_engine_power_kw", power)
    speed = overrides.get("service_speed_knots", speed)
    load = overrides.get("engine_load_fraction", vl.ENGINE_LOAD_FRACTION)
    sfoc = overrides.get("sfoc_g_per_kwh", vl.SFOC_G_PER_KWH)
    factor = overrides.get("vlsfo_carbon_factor", vl.VLSFO_CARBON_FACTOR)
    port_days = overrides.get("port_days", vl.PORT_DAYS)

    distance = (
        vl.DISTANCE_NM_CAPE[corridor]
        if route == "cape" and corridor in vl.DISTANCE_NM_CAPE
        else vl.DISTANCE_NM[corridor]
    )
    days = vl.voyage_days(distance, speed)
    daily = round(power * load * sfoc * vl.HOURS_PER_DAY / 1_000_000, 1)
    fuel = round(days * daily, 1)
    co2 = round(fuel * factor, 1)
    aux_daily = round(daily * vl.AUXILIARY_SHARE_OF_CONSUMPTION, 2)
    port_co2 = round(round(aux_daily * port_days, 2) * factor, 2)

    return {
        "corridor": corridor,
        "vessel_set": vessel,
        "vessel_class": vl.GAS_CARRIER["vessel_class"]
        if vessel == "gas_carrier"
        else vl.CONTAINER_SHIPS[corridor]["vessel_class"],
        "route_scenario": route,
        "speed_scenario": "base",
        "distance_nm": distance,
        "service_speed_knots": speed,
        "voyage_days": days,
        "voyage_fuel_total_t": fuel,
        "voyage_co2_t": co2,
        "port_in_port_emissions_t": port_co2,
        "voyage_energy_mj": fuel * rc.VLSFO_MJ_PER_TONNE,
        "fueleu_actual_intensity_gco2e_mj": overrides.get(
            "fueleu_actual_intensity_gco2e_mj", rc.FUELEU_CONVENTIONAL_WTW_INTENSITY
        ),
    }


def _cost(profile, year, price_scenario, price_multiplier=1.0):
    result = total_cost.maritime_cost_per_voyage(profile, year, price_scenario)
    total = result.total_eur + result.total_gbp
    return total * price_multiplier


def sweep_corridor(
    corridor, year=2026, vessel="gas_carrier", route="suez",
    price_scenario="medium", delta=0.20,
) -> pd.DataFrame:
    """Vary each parameter by plus and minus delta around the base case."""
    base_profile = _profile_with(corridor, vessel, route, {})
    base_total = _cost(base_profile, year, price_scenario)

    rows = []
    for param in SWEPT_PARAMETERS:
        for direction, sign in (("up", 1), ("down", -1)):
            multiplier = 1 + sign * delta
            if param == "carbon_price":
                # Prices are scenario-driven, so scale the resulting cost rather
                # than mutating the price table.
                new_total = _cost(base_profile, year, price_scenario, multiplier)
            else:
                base_value = {
                    "main_engine_power_kw": base_profile["service_speed_knots"],
                }.get(param)
                overrides = {param: _base_value_for(param, corridor, vessel) * multiplier}
                new_total = _cost(
                    _profile_with(corridor, vessel, route, overrides),
                    year, price_scenario,
                )

            change = new_total - base_total
            rows.append(
                {
                    "corridor": corridor,
                    "vessel_set": vessel,
                    "route_scenario": route,
                    "year": year,
                    "price_scenario": price_scenario,
                    "parameter": param,
                    "direction": direction,
                    "delta_pct": sign * delta * 100,
                    "base_cost_per_voyage": base_total,
                    "new_cost_per_voyage": new_total,
                    "abs_change": change,
                    "pct_change": 100 * change / base_total if base_total else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _base_value_for(param, corridor, vessel):
    if param == "main_engine_power_kw":
        return (
            vl.GAS_CARRIER["main_engine_power_kw"]
            if vessel == "gas_carrier"
            else vl.CONTAINER_SHIPS[corridor]["main_engine_power_kw"]
        )
    if param == "service_speed_knots":
        return (
            vl.SPEED_SCENARIOS_KNOTS["base"]
            if vessel == "gas_carrier"
            else vl.CONTAINER_SHIPS[corridor]["service_speed_knots"]
        )
    return {
        "engine_load_fraction": vl.ENGINE_LOAD_FRACTION,
        "sfoc_g_per_kwh": vl.SFOC_G_PER_KWH,
        "vlsfo_carbon_factor": vl.VLSFO_CARBON_FACTOR,
        "port_days": vl.PORT_DAYS,
        "fueleu_actual_intensity_gco2e_mj": rc.FUELEU_CONVENTIONAL_WTW_INTENSITY,
    }[param]


def rank_drivers(sweep: pd.DataFrame) -> pd.DataFrame:
    """Rank parameters by mean absolute percentage effect on per-voyage cost."""
    ranked = (
        sweep.groupby(["corridor", "vessel_set", "year", "parameter"])["pct_change"]
        .apply(lambda s: s.abs().mean())
        .reset_index(name="mean_abs_pct_change")
        .sort_values(
            ["corridor", "vessel_set", "year", "mean_abs_pct_change"],
            ascending=[True, True, True, False],
        )
    )
    ranked["rank"] = (
        ranked.groupby(["corridor", "vessel_set", "year"])["mean_abs_pct_change"]
        .rank(ascending=False, method="dense")
        .astype(int)
    )
    return ranked
