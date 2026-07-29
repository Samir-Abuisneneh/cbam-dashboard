"""Loading input tables.

Three tables feed the model, and they are at different stages of maturity:

  corridor_logistics.csv  REAL. Derived from Gayu's maritime notebooks, with
                          cargo tonnage the one remaining assumption.
  emissions_table.csv     PLACEHOLDER. Awaiting Riya.
  commercial_inputs.csv   PLACEHOLDER. No owner assigned.

Anything still synthetic is marked PLACEHOLDER in its source column, so a real
run cannot quietly inherit made-up numbers.
"""

from pathlib import Path

import pandas as pd

from .config import regulatory_constants as rc
from .config import vessel_logistics as vl
from .validation import unit_checks

DATA_DIR = Path(__file__).parent / "data"
PLACEHOLDER_DIR = DATA_DIR / "placeholder"

HH = rc.HALIFAX_HAMBURG
NF = rc.NINGBO_FELIXSTOWE


def _placeholder_emissions() -> pd.DataFrame:
    """Embedded emissions. Hydrogen is real, from Riya. Ammonia is still placeholder.

    Hydrogen figures are kgCO2/kg H2, numerically identical to tCO2e per tonne.
    Same for ammonia.

    Hydrogen source: Riya, `Assumptions Table(Sheet1).csv`, delivered 26 July 2026.
    Two ranges in her table (Ningbo green and blue) are collapsed to their
    midpoint, per her own instruction in the group chat. She flagged that the
    Canada green and blue figures may still be revised, having mislaid two
    further values she meant to check, so treat those two as provisional.

    The two "cbam_default" rows are not literature LCA figures. They are the
    actual IR 2025/2621 default embedded emissions values for hydrogen (CN
    2804 10 00), country-specific as the regulation requires. Unlike the
    literature pathways, these should be run with using_default_values=True so
    the mark-up (10% in 2026) applies on top of them, since that mark-up is a
    penalty for using regulatory defaults instead of verified actual emissions,
    not something to apply to a literature LCA figure that already assumes it
    represents genuine production.

    Riya's table has no origin carbon price column, but this has since been
    looked up separately and is no longer invented. Canada: CAD 110/tCO2e
    (2026 federal OBPS rate), converted to EUR at the 23 July 2026 ECB
    reference rate, treated as an upper bound because OBPS only charges above
    a facility-specific benchmark and EverWind's actual performance against it
    is unknown. China: EUR 0, because hydrogen production is not yet covered
    by China's national ETS at all, so there is nothing to deduct. See
    regulatory_constants.py for full sourcing on both.
    """
    ca = rc.ORIGIN_CARBON_PRICE_CANADA_EUR_PER_TCO2E  # EUR 68.63, upper bound, see above
    cn = rc.ORIGIN_CARBON_PRICE_CHINA_EUR_PER_TCO2E  # EUR 0.00, hydrogen not yet in scope

    rows = [
        # corridor, product, pathway, tCO2e/t, origin price, method, source
        (HH, "hydrogen", "green_electrolysis", 1.23, ca,
         "Alkaline electrolysis",
         "Riya, https://link.springer.com/article/10.1007/s11708-025-1008-2 "
         "(well-to-gate LCA). PROVISIONAL - Riya flagged a possible revised figure."),
        (HH, "hydrogen", "grey_smr", 10.07, ca,
         "SMR",
         "Riya, https://link.springer.com/article/10.1007/s11708-025-1008-2"),
        (HH, "hydrogen", "blue_smr_ccs", 4.89, ca,
         "SMR + CCS",
         "Riya, https://link.springer.com/article/10.1007/s11708-025-1008-2 "
         "PROVISIONAL - Riya flagged a possible revised figure."),
        (HH, "hydrogen", "cbam_default", 10.82, ca,
         "IR 2025/2621 default, Canada",
         "Riya, CBAM Default Values (IR 2025/2621). Use with using_default_values=True."),
        (NF, "hydrogen", "green_electrolysis", 2.245, cn,
         "PEM electrolysis",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0360319925010602 "
         "midpoint of published range 1.45-3.04"),
        (NF, "hydrogen", "coal_gasification", 19.11, cn,
         "Coal gasification",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0360544225018249 "
         "(GREET-based LCA)"),
        (NF, "hydrogen", "blue_ccs", 6.37, cn,
         "unspecified - not stated in source",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0360319925010602 "
         "midpoint of published range 4.54-8.20. Production method not given; "
         "confirm with Riya before citing as SMR+CCS, China's blue route is more "
         "likely coal-based with CCS."),
        (NF, "hydrogen", "cbam_default", 26.64, cn,
         "IR 2025/2621 default, China",
         "Riya, CBAM Default Values (IR 2025/2621). Use with using_default_values=True."),
        # Ammonia: still placeholder emissions. Riya's table has none yet; her
        # own note says the ammonia table exists but China has not been added.
        # Origin price is a country-level fact, not a product-level one, so
        # these rows get the same real Canada/China figures as hydrogen above.
        (HH, "ammonia", "grey_smr", 2.7, ca, "SMR",
         "PLACEHOLDER emissions - awaiting Riya, Part C literature ranges"),
        (HH, "ammonia", "blue_smr_ccs", 1.2, ca, "SMR + CCS",
         "PLACEHOLDER emissions - awaiting Riya, Part C literature ranges"),
        (HH, "ammonia", "green_electrolysis", 0.1, ca, "Electrolysis",
         "PLACEHOLDER emissions - awaiting Riya, Part C literature ranges"),
        (NF, "ammonia", "grey_smr", 2.8, cn, "SMR",
         "PLACEHOLDER emissions - awaiting Riya, Part C literature ranges"),
        (NF, "ammonia", "coal_gasification", 7.0, cn, "Coal gasification",
         "PLACEHOLDER emissions - awaiting Riya, Part C literature ranges"),
        (NF, "ammonia", "green_electrolysis", 0.1, cn, "Electrolysis",
         "PLACEHOLDER emissions - awaiting Riya, Part C literature ranges"),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "corridor",
            "product",
            "pathway",
            "embedded_emissions_tco2e_per_tonne",
            "origin_carbon_price_eur_per_tco2e",
            "production_method",
            "source",
        ],
    )


def _gayu_logistics(vessel: str = "gas_carrier", speed_scenario: str = "base") -> pd.DataFrame:
    """Real voyage data derived from Gayu's maritime notebooks.

    Everything except `cargo_tonnes` traces to her published figures and is
    checked by `validation/gayu_reproduction.py`. Cargo tonnage is the one
    remaining assumption, and it is flagged in the source column because every
    per-tonne result scales linearly with it.
    """
    rows = []
    for corridor in (HH, NF):
        for route in vl.ROUTE_SCENARIOS:
            if route == "cape" and corridor not in vl.DISTANCE_NM_CAPE:
                continue
            profile = vl.corridor_profile(corridor, vessel, speed_scenario, route)
            rows.append(
                {
                    "corridor": corridor,
                    "vessel_set": profile["vessel_set"],
                    "vessel_class": profile["vessel_class"],
                    "route_scenario": route,
                    "speed_scenario": profile["speed_scenario"],
                    "distance_nm": float(profile["distance_nm"]),
                    "service_speed_knots": profile["service_speed_knots"],
                    "voyage_days": profile["voyage_days"],
                    "fuel_consumption_t_per_nm": round(
                        profile["voyage_fuel_total_t"] / profile["distance_nm"], 6
                    ),
                    "voyage_fuel_total_t": profile["voyage_fuel_total_t"],
                    "voyage_co2_t": profile["voyage_co2_t"],
                    "port_in_port_emissions_t": profile["port_in_port_emissions_t"],
                    "voyage_energy_mj": profile["voyage_energy_mj"],
                    "fueleu_actual_intensity_gco2e_mj": profile[
                        "fueleu_actual_intensity_gco2e_mj"
                    ],
                    "source": "Gayu FINAL_shipping_maritime_cost_model.ipynb",
                }
            )
    return pd.DataFrame(rows)


def _placeholder_commercial() -> pd.DataFrame:
    """Synthetic production, conversion and shipping costs.

    No owner is assigned for this table. See data/README.md.
    """
    per_pathway = {
        ("hydrogen", "grey_smr"): 1500.0,
        ("hydrogen", "blue_smr_ccs"): 2200.0,
        ("hydrogen", "blue_ccs"): 2200.0,
        ("hydrogen", "green_electrolysis"): 4000.0,
        ("hydrogen", "coal_gasification"): 1300.0,
        ("hydrogen", "cbam_default"): 1500.0,  # priced as grey; default is an emissions figure, not a route
        ("ammonia", "grey_smr"): 350.0,
        ("ammonia", "blue_smr_ccs"): 450.0,
        ("ammonia", "green_electrolysis"): 700.0,
        ("ammonia", "coal_gasification"): 300.0,
    }
    conversion = {"hydrogen": 1200.0, "ammonia": 150.0}
    shipping = {(HH, "hydrogen"): 800.0, (HH, "ammonia"): 120.0,
                (NF, "hydrogen"): 1400.0, (NF, "ammonia"): 210.0}

    emissions = _placeholder_emissions()
    rows = []
    for _, r in emissions.iterrows():
        rows.append(
            {
                "corridor": r["corridor"],
                "product": r["product"],
                "pathway": r["pathway"],
                "production_cost_eur_per_tonne": per_pathway[(r["product"], r["pathway"])],
                "conversion_cost_eur_per_tonne": conversion[r["product"]],
                "shipping_cost_eur_per_tonne": shipping[(r["corridor"], r["product"])],
                "source": "PLACEHOLDER - no owner assigned, see data/README.md",
            }
        )
    return pd.DataFrame(rows)


def write_placeholder_data() -> None:
    """Write the three input tables to data/placeholder/.

    The logistics table is no longer synthetic; it is generated from Gayu's
    figures. It is written here alongside the two that still are, so a single
    directory holds a runnable set.
    """
    PLACEHOLDER_DIR.mkdir(parents=True, exist_ok=True)
    _placeholder_emissions().to_csv(PLACEHOLDER_DIR / "emissions_table.csv", index=False)
    _gayu_logistics().to_csv(PLACEHOLDER_DIR / "corridor_logistics.csv", index=False)
    _placeholder_commercial().to_csv(PLACEHOLDER_DIR / "commercial_inputs.csv", index=False)


def load_inputs(directory: Path = None, validate: bool = True):
    """Load the three input tables.

    Defaults to data/ if the real tables are present, otherwise falls back to
    data/placeholder/ and says so.
    """
    if directory is None:
        real = DATA_DIR / "emissions_table.csv"
        directory = DATA_DIR if real.exists() else PLACEHOLDER_DIR

    directory = Path(directory)
    if not (directory / "emissions_table.csv").exists():
        write_placeholder_data()
        directory = PLACEHOLDER_DIR

    emissions = pd.read_csv(directory / "emissions_table.csv")
    logistics = pd.read_csv(directory / "corridor_logistics.csv")
    commercial = pd.read_csv(directory / "commercial_inputs.csv")

    if validate:
        unit_checks.validate_emissions_table(emissions)
        unit_checks.validate_logistics_table(logistics)
        unit_checks.validate_commercial_table(commercial)
        unit_checks.validate_join(emissions, logistics, commercial)

    return emissions, logistics, commercial


def using_placeholder_data(directory: Path = None) -> bool:
    emissions, _, _ = load_inputs(directory, validate=False)
    return emissions["source"].str.startswith("PLACEHOLDER").any()
