"""Reproduce the published outputs of Gayu's maritime cost notebooks exactly.

Gayu's notebooks are the agreed source of truth for everything maritime:
distances, vessel specifications, fuel burn, voyage CO2, and the EU ETS, UK ETS
and FuelEU costs that follow from them. This module holds her published figures
as literal expected values and checks that this model reproduces them.

The point is to make divergence loud. If someone later changes the VLSFO carbon
factor, the engine load assumption or the FuelEU formula, these checks fail and
name the quantity that moved, rather than the integrated model quietly drifting
away from the maritime work it is built on.

Figures transcribed from the notebook outputs, 25 July 2026.
"""

from ..config import regulatory_constants as rc
from ..config import vessel_logistics as vl
from ..model import ets_maritime, fueleu

HH = rc.HALIFAX_HAMBURG
NF = rc.NINGBO_FELIXSTOWE

# --- Gayu's published gas carrier figures -----------------------------------
EXPECTED_GAS_CARRIER = {
    "distance_hh_nm": 2962,
    "distance_nf_suez_nm": 10403,
    "distance_nf_cape_nm": 14815,
    "daily_fuel_t": 41.3,
    "hh_voyage_days": 8.3,
    "hh_fuel_t": 342.8,
    "hh_co2_t": 1080.2,
    "nf_voyage_days": 29.3,
    "nf_fuel_t": 1210.1,
    "nf_co2_t": 3813.0,
    "port_co2_t": 58.51,
    "eu_ets_cost_eur_mid": 43208,
    "uk_ets_cost_gbp_official": 2891,
    "fueleu_penalty_eur": 13229,
}

# --- Gayu's published container ship figures --------------------------------
EXPECTED_CONTAINER = {
    "hh_daily_fuel_t": 73.3,
    "nf_daily_fuel_t": 203.9,
    "hh_voyage_days": 6.9,
    "hh_fuel_t": 505.8,
    "hh_co2_t": 1593.8,
    "nf_voyage_days": 19.4,
    "nf_co2_t": 12464.4,
    "port_co2_t": 289.17,
    "eu_ets_cost_eur_mid": 63752,
    "uk_ets_cost_gbp_official": 14288,
    "fueleu_penalty_eur": 19519,
}


# --- Gayu's published cargo capacity figures --------------------------------
# Source: cargo_capacity_and_density_v2.ipynb
EXPECTED_CARGO = {
    "usable_volume_m3": 82_320,
    "ammonia_cargo_tonnes": 56_142,
    "hydrogen_cargo_tonnes": 5_828,
    "ratio_ammonia_to_hydrogen": 9.6,
    # Her worked example: EU ETS only, mid price, Halifax-Hamburg.
    "eu_ets_per_tonne_ammonia": 0.77,
    "eu_ets_per_tonne_hydrogen": 7.41,
}


def _close(a, b, tol=0.51):
    """Gayu rounds at each step, so allow half a unit of her last decimal."""
    return abs(a - b) <= tol


def check_cargo_capacity() -> list:
    """Reproduce the cargo capacity notebook, including her worked example."""
    e = EXPECTED_CARGO
    eu_ets_per_voyage = EXPECTED_GAS_CARRIER["eu_ets_cost_eur_mid"]

    checks = [
        ("Usable cargo volume (m3)", vl.USABLE_VOLUME_M3, e["usable_volume_m3"]),
        ("Ammonia cargo (t)", vl.CARGO_TONNES["ammonia"], e["ammonia_cargo_tonnes"]),
        ("Hydrogen cargo (t)", vl.CARGO_TONNES["hydrogen"], e["hydrogen_cargo_tonnes"]),
        (
            "Ammonia / hydrogen mass ratio",
            vl.CARGO_TONNES["ammonia"] / vl.CARGO_TONNES["hydrogen"],
            e["ratio_ammonia_to_hydrogen"],
        ),
        (
            "EU ETS per tonne ammonia (EUR)",
            eu_ets_per_voyage / vl.CARGO_TONNES["ammonia"],
            e["eu_ets_per_tonne_ammonia"],
        ),
        (
            "EU ETS per tonne hydrogen (EUR)",
            eu_ets_per_voyage / vl.CARGO_TONNES["hydrogen"],
            e["eu_ets_per_tonne_hydrogen"],
        ),
    ]
    return [(name, got, want, _close(got, want, 0.06)) for name, got, want in checks]


def check_gas_carrier() -> list:
    """Returns a list of (quantity, modelled, expected, ok) tuples."""
    hh = vl.corridor_profile(HH, "gas_carrier", "base")
    nf = vl.corridor_profile(NF, "gas_carrier", "base")
    nf_cape = vl.corridor_profile(NF, "gas_carrier", "base", route="cape")

    eu_ets = ets_maritime.eu_ets_maritime_cost(
        hh["voyage_co2_t"], 2026, rc.eu_ets_price(2026, "medium"),
        rc.EU_ETS_EXTRA_EEA_COVERAGE, port_in_port_emissions_t=0.0,
    )
    uk_ets = ets_maritime.uk_ets_maritime_cost(
        nf["port_in_port_emissions_t"], 2026, rc.UK_ETS_PRICE_2026_OFFICIAL,
        voyage_co2_t=nf["voyage_co2_t"], first_period_fraction_2026=1.0,
    )
    fueleu_penalty = fueleu.fueleu_cost(
        rc.FUELEU_CONVENTIONAL_WTW_INTENSITY, hh["voyage_energy_mj"], 2026,
        target_intensity_gco2e_mj=89.34,
    )

    e = EXPECTED_GAS_CARRIER
    checks = [
        ("Halifax-Hamburg distance (nm)", hh["distance_nm"], e["distance_hh_nm"]),
        ("Ningbo-Felixstowe Suez distance (nm)", nf["distance_nm"], e["distance_nf_suez_nm"]),
        ("Ningbo-Felixstowe Cape distance (nm)", nf_cape["distance_nm"], e["distance_nf_cape_nm"]),
        ("Daily fuel burn (t/day)", vl.daily_fuel_tonnes(12400), e["daily_fuel_t"]),
        ("HH voyage days", hh["voyage_days"], e["hh_voyage_days"]),
        ("HH voyage fuel (t)", hh["voyage_fuel_total_t"], e["hh_fuel_t"]),
        ("HH voyage CO2 (t)", hh["voyage_co2_t"], e["hh_co2_t"]),
        ("NF voyage days", nf["voyage_days"], e["nf_voyage_days"]),
        ("NF voyage fuel (t)", nf["voyage_fuel_total_t"], e["nf_fuel_t"]),
        ("NF voyage CO2 (t)", nf["voyage_co2_t"], e["nf_co2_t"]),
        ("Port call CO2 (t)", nf["port_in_port_emissions_t"], e["port_co2_t"]),
        ("EU ETS cost, mid price (EUR)", eu_ets, e["eu_ets_cost_eur_mid"]),
        ("UK ETS cost, official price (GBP)", uk_ets, e["uk_ets_cost_gbp_official"]),
        ("FuelEU penalty (EUR)", fueleu_penalty, e["fueleu_penalty_eur"]),
    ]
    return [(name, got, want, _close(got, want)) for name, got, want in checks]


def check_container_ship() -> list:
    hh = vl.corridor_profile(HH, "container", "base")
    nf = vl.corridor_profile(NF, "container", "base")

    eu_ets = ets_maritime.eu_ets_maritime_cost(
        hh["voyage_co2_t"], 2026, rc.eu_ets_price(2026, "medium"),
        rc.EU_ETS_EXTRA_EEA_COVERAGE, port_in_port_emissions_t=0.0,
    )
    uk_ets = ets_maritime.uk_ets_maritime_cost(
        nf["port_in_port_emissions_t"], 2026, rc.UK_ETS_PRICE_2026_OFFICIAL,
        voyage_co2_t=nf["voyage_co2_t"], first_period_fraction_2026=1.0,
    )
    fueleu_penalty = fueleu.fueleu_cost(
        rc.FUELEU_CONVENTIONAL_WTW_INTENSITY, hh["voyage_energy_mj"], 2026,
        target_intensity_gco2e_mj=89.34,
    )

    e = EXPECTED_CONTAINER
    checks = [
        ("HH daily fuel (t/day)", vl.daily_fuel_tonnes(22000), e["hh_daily_fuel_t"]),
        ("NF daily fuel (t/day)", vl.daily_fuel_tonnes(61225), e["nf_daily_fuel_t"]),
        ("HH voyage days", hh["voyage_days"], e["hh_voyage_days"]),
        ("HH voyage fuel (t)", hh["voyage_fuel_total_t"], e["hh_fuel_t"]),
        ("HH voyage CO2 (t)", hh["voyage_co2_t"], e["hh_co2_t"]),
        ("NF voyage days", nf["voyage_days"], e["nf_voyage_days"]),
        ("NF voyage CO2 (t)", nf["voyage_co2_t"], e["nf_co2_t"]),
        ("Port call CO2 (t)", nf["port_in_port_emissions_t"], e["port_co2_t"]),
        ("EU ETS cost, mid price (EUR)", eu_ets, e["eu_ets_cost_eur_mid"]),
        ("UK ETS cost, official price (GBP)", uk_ets, e["uk_ets_cost_gbp_official"]),
        ("FuelEU penalty (EUR)", fueleu_penalty, e["fueleu_penalty_eur"]),
    ]
    return [(name, got, want, _close(got, want)) for name, got, want in checks]


def format_report() -> str:
    lines = ["Reproduction of Gayu's maritime notebooks", ""]
    for title, checks in (
        ("Gas carrier (VLGC/VLAC), primary case", check_gas_carrier()),
        ("Container ship (MCG named vessels)", check_container_ship()),
        ("Cargo capacity and density", check_cargo_capacity()),
    ):
        lines.append(f"  {title}")
        for name, got, want, ok in checks:
            mark = "ok  " if ok else "FAIL"
            lines.append(f"    [{mark}] {name:<38} modelled {got:>12,.2f}  Gayu {want:>12,.2f}")
        lines.append("")
    n_fail = sum(
        1
        for _, _, _, ok in (
            check_gas_carrier() + check_container_ship() + check_cargo_capacity()
        )
        if not ok
    )
    lines.append(f"  {n_fail} mismatch(es)." if n_fail else "  All figures reproduce.")
    return "\n".join(lines)
