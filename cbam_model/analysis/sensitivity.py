"""One-at-a-time sensitivity analysis on the maritime layer.

Answers the question most likely to come up at viva: which assumption actually
drives the result. Each parameter is varied while everything else is held
constant, and the change in per-voyage carbon cost is recorded and ranked.

This runs on the maritime layer only. That was originally because the CBAM
layer sat on placeholder emissions, which is no longer true: Riya's figures are
real for both products and both corridors. Extending the sweep to the CBAM
layer is now worth doing and is not done here, so the ranking below covers
voyage parameters only and should not be read as ranking the whole model.

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
    port_fuel = round(aux_daily * port_days, 2)
    port_co2 = round(port_fuel * factor, 2)

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
        "voyage_co2e_t": vl.voyage_co2e_tonnes(fuel, co2),
        "port_in_port_emissions_t": port_co2,
        "port_in_port_emissions_co2e_t": vl.port_co2e_tonnes(port_fuel, port_co2),
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


# ---------------------------------------------------------------------------
# Compliance layer sweep, added 4 August 2026
# ---------------------------------------------------------------------------
# The maritime sweep above ranks voyage parameters against per-voyage cost.
# That was the whole model when the CBAM layer sat on placeholder emissions.
# It is not any more, and by 2030 CBAM dominates every other term, so a ranking
# that omits it is not a ranking of what actually drives the result.
#
# This sweeps the headline metric instead: total compliance cost per tonne of
# product, which carries both layers. It works off the lower-level cost
# functions rather than `total_cost.maritime_cost_per_voyage`, because the
# carbon price has to be injected directly. Scaling the output instead would be
# wrong on the EU corridor: `eu_cbam_cost` computes
# `cert_price - origin_carbon_price`, which is not linear in the price once the
# origin price is nonzero, and Canada's is EUR 68.63.

COMPLIANCE_SWEPT_PARAMETERS = (
    "embedded_emissions_tco2e_per_tonne",
    "origin_carbon_price_eur_per_tco2e",
    "cargo_tonnes",
    "carbon_price",
    "main_engine_power_kw",
    "service_speed_knots",
    "engine_load_fraction",
    "sfoc_g_per_kwh",
    "vlsfo_carbon_factor",
    "port_days",
    "fueleu_actual_intensity_gco2e_mj",
)


def _compliance_total_per_tonne(
    corridor, product, pathway, year, profile, embedded, origin_price, cargo_t, price
):
    """Total compliance cost per tonne, in the corridor's own currency.

    Deliberately mirrors `total_cost.compliance_cost_per_tonne` rather than
    calling it, so an explicit carbon price can be supplied.
    """
    from ..model import cbam, ets_maritime, fueleu

    voyage_co2e = profile.get("voyage_co2e_t", profile["voyage_co2_t"])
    port_co2e = profile.get(
        "port_in_port_emissions_co2e_t", profile["port_in_port_emissions_t"]
    )
    if rc.CORRIDOR_REGIME[corridor] == "EU":
        ets = ets_maritime.eu_ets_maritime_cost(
            voyage_co2e, year, price,
            rc.EU_ETS_CORRIDOR_COVERAGE[corridor], 0.0,
        )
        fe = fueleu.fueleu_cost(
            profile["fueleu_actual_intensity_gco2e_mj"], profile["voyage_energy_mj"], year
        )
        cbam_pt = cbam.eu_cbam_cost(
            embedded,
            year,
            price,
            origin_price,
            cbam.is_cbam_default_pathway(pathway),
            # Follows the model default, so the sweep ranks drivers of the same
            # number the results chapter reports. `embedded` here is per tonne
            # of product, which is the basis the benchmark is defined on.
            benchmark_tco2e_per_tonne=rc.eu_product_benchmark(product),
        )
        maritime_pt = (ets + fe) / cargo_t
    else:
        ets = ets_maritime.uk_ets_maritime_cost(
            port_co2e, year, price,
            voyage_co2_t=voyage_co2e,
        )
        cbam_pt = cbam.uk_cbam_cost(embedded, year, price)
        maritime_pt = ets / cargo_t
    return maritime_pt + cbam_pt


def sweep_compliance(
    corridor, product, pathway, emissions_row=None, year=2030,
    vessel="gas_carrier", route="suez", price_scenario="medium", delta=0.20,
    uk_price_variant="frozen",
) -> pd.DataFrame:
    """Vary each parameter by +/- delta and measure the effect on compliance
    cost per tonne of product, which is the study's headline metric.

    Defaults to 2030 rather than 2026 because the CBAM factor is still tiny in
    2026 (2.5%), which would understate how much the emissions inputs matter.
    """
    from .. import data_io

    if emissions_row is None:
        emissions, _, _ = data_io.load_inputs()
        match = emissions[
            (emissions["corridor"] == corridor)
            & (emissions["product"] == product)
            & (emissions["pathway"] == pathway)
        ]
        if match.empty:
            raise ValueError(f"No emissions row for {corridor}/{product}/{pathway}")
        emissions_row = match.iloc[0]

    base = {
        "embedded_emissions_tco2e_per_tonne": float(
            emissions_row["embedded_emissions_tco2e_per_tonne"]
        ),
        "origin_carbon_price_eur_per_tco2e": float(
            emissions_row["origin_carbon_price_eur_per_tco2e"]
        ),
        "cargo_tonnes": float(vl.CARGO_TONNES[product]),
        "carbon_price": (
            rc.eu_ets_price(year, price_scenario)
            if rc.CORRIDOR_REGIME[corridor] == "EU"
            else rc.uk_ets_price(year, price_scenario, uk_price_variant)
        ),
    }

    def total(overrides):
        profile = _profile_with(
            corridor, vessel, route,
            {k: v for k, v in overrides.items() if k not in base},
        )
        return _compliance_total_per_tonne(
            corridor, product, pathway, year, profile,
            overrides.get("embedded_emissions_tco2e_per_tonne",
                          base["embedded_emissions_tco2e_per_tonne"]),
            overrides.get("origin_carbon_price_eur_per_tco2e",
                          base["origin_carbon_price_eur_per_tco2e"]),
            overrides.get("cargo_tonnes", base["cargo_tonnes"]),
            overrides.get("carbon_price", base["carbon_price"]),
        )

    base_total = total({})
    currency = "EUR" if rc.CORRIDOR_REGIME[corridor] == "EU" else "GBP"

    rows = []
    for param in COMPLIANCE_SWEPT_PARAMETERS:
        start = base.get(param)
        if start is None:
            start = _base_value_for(param, corridor, vessel)
        if start == 0:
            # Origin carbon price is zero on the China corridor, so scaling it
            # does nothing. Recorded as zero leverage rather than skipped, so
            # the ranking shows it was tested.
            for direction, sign in (("up", 1), ("down", -1)):
                rows.append({
                    "corridor": corridor, "product": product, "pathway": pathway,
                    "year": year, "price_scenario": price_scenario, "currency": currency,
                    "parameter": param, "direction": direction,
                    "delta_pct": sign * delta * 100,
                    "base_cost_per_tonne": base_total, "new_cost_per_tonne": base_total,
                    "abs_change": 0.0, "pct_change": 0.0,
                })
            continue
        for direction, sign in (("up", 1), ("down", -1)):
            new_total = total({param: start * (1 + sign * delta)})
            change = new_total - base_total
            rows.append({
                "corridor": corridor, "product": product, "pathway": pathway,
                "year": year, "price_scenario": price_scenario, "currency": currency,
                "parameter": param, "direction": direction,
                "delta_pct": sign * delta * 100,
                "base_cost_per_tonne": base_total, "new_cost_per_tonne": new_total,
                "abs_change": change,
                "pct_change": 100 * change / base_total if base_total else 0.0,
            })
    return pd.DataFrame(rows)


def rank_compliance_drivers(sweep: pd.DataFrame) -> pd.DataFrame:
    """Rank parameters by mean absolute percentage effect on per-tonne cost."""
    ranked = (
        sweep.groupby(["corridor", "product", "pathway", "year", "parameter"])["pct_change"]
        .apply(lambda s: s.abs().mean())
        .reset_index(name="mean_abs_pct_change")
        .sort_values(
            ["corridor", "product", "pathway", "year", "mean_abs_pct_change"],
            ascending=[True, True, True, True, False],
        )
    )
    ranked["rank"] = (
        ranked.groupby(["corridor", "product", "pathway", "year"])["mean_abs_pct_change"]
        .rank(ascending=False, method="dense")
        .astype(int)
    )
    return ranked


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
