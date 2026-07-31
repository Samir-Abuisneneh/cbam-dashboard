"""Loading input tables.

Three tables feed the model, and they are at different stages of maturity:

  corridor_logistics.csv  REAL. Derived from Gayu's maritime notebooks, with
                          cargo tonnage the one remaining assumption.
  emissions_table.csv     REAL. From Riya, both products, both countries.
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
    """Embedded emissions. Hydrogen and ammonia are both real, from Riya.

    Figures are kgCO2/kg product, numerically identical to tCO2e per tonne.

    Source: Riya, `Assumptions Table(Sheet1).csv`, delivered 29 July 2026 - the
    revision that finally includes the ammonia table and both countries'
    CBAM defaults, superseding the 26 July hydrogen-only delivery and closing
    out the two figures she'd previously flagged as provisional (Canada green
    and blue hydrogen are now taken as final).

    Ranges in her table are collapsed to their midpoint, per her own
    instruction in the group chat: Ningbo hydrogen green (1.45-3.04), Ningbo
    ammonia green (0.596-1.04) and Ningbo ammonia coal/grey (4.4-4.8).

    Ningbo blue hydrogen: her table lists two candidate rows for this ("Coal
    hydrogen with CCS", 4.92-10.90, and "CCS-equipped fossil hydrogen",
    4.54-8.20). Taking the coal-specific one, since China's blue route is more
    likely coal-based with CCS - matching her own grey/coal_gasification
    pathway for the same corridor - rather than the generic fossil-hydrogen
    figure used previously.

    Canada green and blue hydrogen also gained a second candidate row each in
    this delivery - green: "PEM electrolysis (grid average)", 1.34, alongside
    the original "Alkaline electrolysis (grid average)", 1.23; blue: "SMR/ATR/
    NGD + CCS (natural gas-producing regions)", 3.91-8.20, alongside the
    original single-value "SMR + CCS", 4.89. Both PEM and the second blue row
    are dropped in favour of the originals, unlike the Ningbo blue case above,
    because the originals are the only Canada hydrogen figures that come from
    the same source paper as the Canada grey (SMR) row, keeping green/grey/
    blue internally consistent as one LCA study rather than mixing studies
    for the same country. This has not been confirmed with Riya as her
    intended canonical figure now that alternatives exist - ask her directly
    before treating it as settled, the same way the Ningbo choice above should
    be.

    Halifax-Hamburg ammonia has no blue (SMR+CCS) row in her table at all, so
    that pathway is dropped here rather than left on an invented number.
    Ningbo-Felixstowe ammonia has only one grey/coal route in her table, so
    the two separate placeholder pathways that used to stand in for it
    (grey_smr and coal_gasification) collapse into one, named coal_gasification
    to match the naming already used for Ningbo hydrogen's equivalent route.

    The four "cbam_default" rows (one per product per country) are not
    literature LCA figures. They are the actual IR 2025/2621 default embedded
    emissions values, country-specific as the regulation requires. Unlike the
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
    is unknown. China: EUR 0, because neither hydrogen nor ammonia production
    is yet covered by China's national ETS, so there is nothing to deduct. See
    regulatory_constants.py for full sourcing on both. Origin price is a
    country-level fact, not a product-level one, so ammonia gets the same
    Canada/China figures as hydrogen.
    """
    ca = rc.ORIGIN_CARBON_PRICE_CANADA_EUR_PER_TCO2E  # EUR 68.63, upper bound, see above
    cn = rc.ORIGIN_CARBON_PRICE_CHINA_EUR_PER_TCO2E  # EUR 0.00, neither product yet in scope

    rows = [
        # corridor, product, pathway, tCO2e/t, origin price, method, source
        (HH, "hydrogen", "green_electrolysis", 1.23, ca,
         "Alkaline electrolysis",
         "Riya, https://link.springer.com/article/10.1007/s11708-025-1008-2 "
         "(well-to-gate LCA)."),
        (HH, "hydrogen", "grey_smr", 10.07, ca,
         "SMR",
         "Riya, https://link.springer.com/article/10.1007/s11708-025-1008-2"),
        (HH, "hydrogen", "blue_smr_ccs", 4.89, ca,
         "SMR + CCS",
         "Riya, https://link.springer.com/article/10.1007/s11708-025-1008-2"),
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
        (NF, "hydrogen", "blue_ccs", 7.91, cn,
         "Coal hydrogen with CCS",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0959652622021151 "
         "midpoint of published range 4.92-10.90."),
        (NF, "hydrogen", "cbam_default", 26.64, cn,
         "IR 2025/2621 default, China",
         "Riya, CBAM Default Values (IR 2025/2621). Use with using_default_values=True."),
        (HH, "ammonia", "grey_smr", 2.18, ca,
         "Natural gas ammonia",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0360319924054375#abs0020"),
        (HH, "ammonia", "green_electrolysis", 0.62, ca,
         "Electrolysis",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0360319924054375#abs0020"),
        (HH, "ammonia", "cbam_default", 1.98, ca,
         "IR 2025/2621 default, Canada",
         "Riya, CBAM Default Values (IR 2025/2621). Use with using_default_values=True."),
        (NF, "ammonia", "coal_gasification", 4.6, cn,
         "Coal gasification",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0301479723016365 "
         "midpoint of published range 4.4-4.8 (2023)."),
        (NF, "ammonia", "green_electrolysis", 0.818, cn,
         "Renewable electrolysis + Haber-Bosch",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0301479723016365 "
         "midpoint of published range 0.596-1.04 (2023)."),
        (NF, "ammonia", "cbam_default", 4.36, cn,
         "IR 2025/2621 default, China",
         "Riya, CBAM Default Values (IR 2025/2621). Use with using_default_values=True."),
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
        ("ammonia", "green_electrolysis"): 700.0,
        ("ammonia", "coal_gasification"): 300.0,
        ("ammonia", "cbam_default"): 350.0,  # priced as grey; default is an emissions figure, not a route
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
