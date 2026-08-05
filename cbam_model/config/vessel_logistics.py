"""Vessel and corridor parameters from Gayu's maritime cost notebooks.

Source notebooks (Student 2, received 25 July 2026):
  FINAL_shipping_maritime_cost_model.ipynb        core gas carrier model
  FINAL_container_ship_cost_model.ipynb           MCG named-vessel variant
  gas_carrier_vs_container_ship_comparison.ipynb  side by side

These values supersede the figures in the original build spec wherever the two
disagree. `validation/gayu_reproduction.py` checks that this model reproduces
her published outputs exactly, so any drift shows up as a test failure rather
than a quiet divergence.

The gas carrier is the primary case. Hydrogen and ammonia would realistically
move as chartered bulk cargo, and no dedicated liquid hydrogen carrier fleet
exists commercially, so the VLGC/VLAC class that carries ammonia today stands in
for both products. The container ship set exists because MCG's corridor
reference document named two specific vessels.
"""

from . import regulatory_constants as rc

HH = rc.HALIFAX_HAMBURG
NF = rc.NINGBO_FELIXSTOWE


# ---------------------------------------------------------------------------
# Distances
# ---------------------------------------------------------------------------
# Eurostat SeaRoute (Gaffuri 2021), a routing tool using the Oak Ridge Global
# Shipping Lane Network and Dijkstra's shortest-path algorithm, with port
# coordinates from the NGA World Port Index. Reproduced from Gayu's notebooks.
#
# These replace the build spec's figures, which were substantially wrong on the
# Atlantic corridor:
#   Halifax-Hamburg    spec said ~6,300 nm, actual 2,962 nm
#   Ningbo-Felixstowe  spec said ~11,200 nm, actual 10,403 nm
#   Cape diversion     spec said +3,500 nm, actual +4,412 nm
#
# The Halifax-Hamburg error is a factor of more than two and would have
# overstated that corridor's voyage emissions by the same margin.

PORT_COORDINATES = {  # longitude, latitude. NGA World Port Index.
    "halifax": [-63.5833, 44.6500],
    "hamburg": [9.9333, 53.5500],
    "ningbo": [121.5500, 29.8833],
    "felixstowe": [1.3167, 51.9500],
}

DISTANCE_NM = {
    HH: 2962,
    NF: 10403,
}

# Cape of Good Hope diversion, midpoint of two independent published estimates:
# Notteboom, Haralambides & Cullinane (2024), Maritime Economics & Logistics,
# 4,575 nm for a comparable Shanghai-Rotterdam route; and OECD/ITF (2024),
# roughly 8,500 nm added to a Far East-Europe round trip, so about 4,250 nm
# one way.
CAPE_DIVERSION_ADDITION_NM = 4412
DISTANCE_NM_CAPE = {NF: DISTANCE_NM[NF] + CAPE_DIVERSION_ADDITION_NM}  # 14,815


# ---------------------------------------------------------------------------
# Vessels
# ---------------------------------------------------------------------------

# Gas carrier, primary case. Engine power from Vorkapic, Martincic-Ipsic &
# Piltaver (2024), Journal of Marine Science and Engineering, a peer-reviewed
# study of a real VLGC propulsion system. Speed from Seo, An, Park et al.
# (2024), Sustainability, a techno-economic study of the same vessel class.
GAS_CARRIER = {
    "vessel_class": "VLGC/VLAC",
    "main_engine_power_kw": 12400,
    "service_speed_knots": 14.8,
}

# Speed is genuinely uncertain and drives everything downstream, so Gayu carries
# three scenarios: the paper's base case plus the bounds it tested.
SPEED_SCENARIOS_KNOTS = {"lower": 13.0, "base": 14.8, "upper": 17.0}

# Container ship variant, from MCG's corridor reference document. Manufacturer
# and technical-archive sources rather than peer-reviewed papers.
CONTAINER_SHIPS = {
    HH: {
        "vessel_class": "ACL G4-class ConRo",
        "main_engine_power_kw": 22000,
        "service_speed_knots": 18.0,
    },
    NF: {
        "vessel_class": "HMM Algeciras-class / Megamax-24",
        "main_engine_power_kw": 61225,
        "service_speed_knots": 22.4,
    },
}


# ---------------------------------------------------------------------------
# Fuel and emissions
# ---------------------------------------------------------------------------

SFOC_G_PER_KWH = 185  # South Coast AQMD (2022), slow-speed diesel engines
ENGINE_LOAD_FRACTION = 0.75  # working assumption, not a cited figure. Typical
# engines of this type run at 70-85%.
VLSFO_CARBON_FACTOR = 3.151  # tCO2 per tonne fuel. IMO MEPC 82/6/38.
# Note: the build spec used 3.114. Gayu's IMO figure supersedes it.

PORT_DAYS = 3.0  # Seo et al. (2024) base-case port time, 72 hours
AUXILIARY_SHARE_OF_CONSUMPTION = 0.15  # IMO GreenVoyage2050. Gayu flags this as
# the weakest-sourced number in her model,
# a general industry figure rather than a
# measured at-berth rate for this vessel.

HOURS_PER_DAY = 24

# CH4 and N2O, added to Gayu's model 5 August 2026 (her notebook's section 5b,
# "This section is new"). From 1 January 2026 EU ETS maritime scope expands
# beyond CO2 to cover methane and nitrous oxide on a CO2e basis (EMSA, EU ETS
# maritime extension page: https://www.emsa.europa.eu/reducing-emissions/
# extension-ets.html). The UK ETS maritime extension mirrors this from 1 July
# 2026 with identical factors (SI 2026/392, Schedule 2A, Table C1/C2), so one
# set of constants serves both regimes.
#
# Tank-to-wake CH4 and N2O factors: IMO (2024), Resolution MEPC.391(81), 2024
# Guidelines on Life Cycle GHG Intensity of Marine Fuels, Annex 10, Appendix 2,
# p.49. The table gives identical non-CO2 factors for "ALL ICEs" across HFO,
# LFO and MDO/MGO, so the HFO-vs-LFO question that matters for
# VLSFO_CARBON_FACTOR above does not affect these two figures.
CH4_G_PER_G_FUEL = 0.00005
N2O_G_PER_G_FUEL = 0.00018

# Global warming potentials, same guidelines Section 2.4, IPCC AR5-aligned.
# Matches UK SI 2026/392, Schedule 2A, Table C1.
GWP_CH4 = 28
GWP_N2O = 265

# Scenario dimensions that come from Gayu's own notebooks rather than from the
# build spec. Carrying all three means the maritime results span the same range
# she reports rather than collapsing to a single base case.
VESSEL_SETS = ("gas_carrier", "container")
ROUTE_SCENARIOS = ("suez", "cape")  # cape only differs for Ningbo-Felixstowe


def daily_fuel_tonnes(power_kw, load=ENGINE_LOAD_FRACTION, sfoc=SFOC_G_PER_KWH):
    """Daily fuel burn in tonnes. Matches Gayu's rounding exactly."""
    return round(power_kw * load * sfoc * HOURS_PER_DAY / 1_000_000, 1)


def voyage_days(distance_nm, speed_knots):
    return round(distance_nm / (speed_knots * HOURS_PER_DAY), 1)


def voyage_fuel_and_co2(distance_nm, power_kw, speed_knots):
    """Returns (voyage_days, fuel_tonnes, co2_tonnes), rounded as Gayu does."""
    days = voyage_days(distance_nm, speed_knots)
    fuel = round(days * daily_fuel_tonnes(power_kw), 1)
    co2 = round(fuel * VLSFO_CARBON_FACTOR, 1)
    return days, fuel, co2


def port_fuel_tonnes(power_kw):
    """Fuel burned by auxiliary engines during the port call."""
    aux_daily = round(daily_fuel_tonnes(power_kw) * AUXILIARY_SHARE_OF_CONSUMPTION, 2)
    return round(aux_daily * PORT_DAYS, 2)


def port_co2_tonnes(power_kw):
    """CO2 (only) from auxiliary engines during the port call.

    This is the only quantity that mattered for UK ETS before the CO2e
    extension (see `port_co2e_tonnes`), since the ocean leg is out of scope.
    """
    return round(port_fuel_tonnes(power_kw) * VLSFO_CARBON_FACTOR, 2)


def voyage_co2e_tonnes(fuel_tonnes, co2_tonnes):
    """CO2e for a full ocean voyage: CO2 plus CH4 and N2O on a GWP basis.

    Matches Gayu's rounding for the voyage-level figures (4dp for the gas
    masses, 2dp for their CO2e, 1dp for the total).
    """
    ch4_t = round(fuel_tonnes * CH4_G_PER_G_FUEL, 4)
    n2o_t = round(fuel_tonnes * N2O_G_PER_G_FUEL, 4)
    ch4_co2e = round(ch4_t * GWP_CH4, 2)
    n2o_co2e = round(n2o_t * GWP_N2O, 2)
    return round(co2_tonnes + ch4_co2e + n2o_co2e, 1)


def port_co2e_tonnes(fuel_tonnes, co2_tonnes):
    """CO2e for the in-port call: CO2 plus CH4 and N2O on a GWP basis.

    Matches Gayu's rounding for the port-level figures (5dp for the gas
    masses, 3dp for their CO2e, 2dp for the total) - one decimal place finer
    than the voyage-level figures throughout, since the port quantities are
    themselves an order of magnitude smaller.
    """
    ch4_t = round(fuel_tonnes * CH4_G_PER_G_FUEL, 5)
    n2o_t = round(fuel_tonnes * N2O_G_PER_G_FUEL, 5)
    ch4_co2e = round(ch4_t * GWP_CH4, 3)
    n2o_co2e = round(n2o_t * GWP_N2O, 3)
    return round(co2_tonnes + ch4_co2e + n2o_co2e, 2)


# ---------------------------------------------------------------------------
# Cargo capacity
# ---------------------------------------------------------------------------
# RESOLVED. Source: Gayu, `cargo_capacity_and_density_v2.ipynb`, 25 July 2026.
#
# This is the join key between the two halves of the study. Maritime cost is per
# voyage, CBAM liability is per tonne of product, and neither converts into the
# other without knowing how many tonnes a voyage carries.
#
# Every input is sourced:
#   84,000 m3 capacity   Seo, An, Park et al. (2024), Sustainability 16(2) 827.
#                        The same peer-reviewed vessel model already used for
#                        service speed and port time, so all three operational
#                        assumptions now come from one consistent source.
#   98% filling limit    IMO International Gas Carrier (IGC) Code, Chapter
#                        15.1.1, the regulatory maximum at reference temperature.
#                        Higher limits are possible under 15.1.3 but require
#                        vessel-specific approval, which is not on record here.
#   682 kg/m3 ammonia    PubChem (US National Institutes of Health), CID 222.
#                        Liquid ammonia at its boiling point, -33.3 C, 1.013 bar.
#   70.8 kg/m3 hydrogen  Seo and Han (2021), Energies 14(24) 8326, which states
#                        the figure directly and corroborates the standard
#                        physical constant with a peer-reviewed source.

VESSEL_CUBIC_CAPACITY_M3 = 84_000
FILLING_LIMIT_FRACTION = 0.98  # IMO IGC Code Ch. 15.1.1
DENSITY_KG_PER_M3 = {"ammonia": 682.0, "hydrogen": 70.8}

USABLE_VOLUME_M3 = VESSEL_CUBIC_CAPACITY_M3 * FILLING_LIMIT_FRACTION  # 82,320

CARGO_TONNES = {
    product: round(USABLE_VOLUME_M3 * density / 1000)
    for product, density in DENSITY_KG_PER_M3.items()
}  # ammonia 56,142 t, hydrogen 5,828 t, a ratio of 9.6x

# CAVEAT to carry into the write-up, not an error in Gayu's work.
#
# The 84,000 m3 figure is an ammonia carrier, which operates at about -33 C. It
# cannot physically carry liquid hydrogen, which needs -253 C cryogenic
# containment. The largest liquid hydrogen carrier built to date is the Suiso
# Frontier at 1,250 m3, and designs under development are around 40,000 m3, so an
# 84,000 m3 liquid hydrogen vessel does not exist and is not near-term.
#
# Applying the ammonia carrier's geometry to hydrogen is therefore a deliberate
# counterfactual: it isolates the effect of cargo density by holding the vessel
# constant. That is a defensible way to answer "what does density alone do to
# per-tonne cost", and it is consistent with Gayu's own note that no commercial
# liquid hydrogen fleet exists. It should be labelled as a counterfactual in the
# results rather than presented as a shipping option available today. Boil-off
# losses for liquid hydrogen are also materially higher and are not modelled.
LH2_VESSEL_IS_COUNTERFACTUAL = True


def corridor_profile(corridor, vessel="gas_carrier", speed_scenario="base", route="suez"):
    """Full voyage profile for one corridor, ready for the cost model."""
    if vessel == "gas_carrier":
        power = GAS_CARRIER["main_engine_power_kw"]
        speed = SPEED_SCENARIOS_KNOTS[speed_scenario]
        vessel_class = GAS_CARRIER["vessel_class"]
    else:
        power = CONTAINER_SHIPS[corridor]["main_engine_power_kw"]
        speed = CONTAINER_SHIPS[corridor]["service_speed_knots"]
        vessel_class = CONTAINER_SHIPS[corridor]["vessel_class"]

    distance = (
        DISTANCE_NM_CAPE[corridor]
        if route == "cape" and corridor in DISTANCE_NM_CAPE
        else DISTANCE_NM[corridor]
    )
    days, fuel, co2 = voyage_fuel_and_co2(distance, power, speed)
    port_fuel = port_fuel_tonnes(power)
    port_co2 = round(port_fuel * VLSFO_CARBON_FACTOR, 2)

    return {
        "corridor": corridor,
        "vessel_set": vessel,
        "vessel_class": vessel_class,
        "route_scenario": route,
        "speed_scenario": speed_scenario if vessel == "gas_carrier" else "service",
        "distance_nm": distance,
        "service_speed_knots": speed,
        "voyage_days": days,
        "voyage_fuel_total_t": fuel,
        "voyage_co2_t": co2,
        "voyage_co2e_t": voyage_co2e_tonnes(fuel, co2),
        "port_in_port_emissions_t": port_co2,
        "port_in_port_emissions_co2e_t": port_co2e_tonnes(port_fuel, port_co2),
        "voyage_energy_mj": fuel * rc.VLSFO_MJ_PER_TONNE,
        "fueleu_actual_intensity_gco2e_mj": rc.FUELEU_CONVENTIONAL_WTW_INTENSITY,
    }
