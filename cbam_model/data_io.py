"""Loading input tables.

Three tables feed the model, and they are at different stages of maturity:

  corridor_logistics.csv  REAL. Derived from Gayu's maritime notebooks, with
                          cargo tonnage the one remaining assumption.
  emissions_table.csv     REAL. From Riya, both products, both countries.
  commercial_inputs.csv   MIXED. Production cost is real, from Riya's 4 August
                          2026 delivery. Conversion and shipping cost are still
                          synthetic with no owner.

Anything still synthetic says PLACEHOLDER in its source column, so a real run
cannot quietly inherit made-up numbers.

NAMING WART, worth knowing before you trust a path: the directory is called
`placeholder/` and the writers are called `_placeholder_*`, but most of what
they now hold is real sourced data. The names date from when all three tables
were synthetic. Renaming touches `load_inputs`, the dashboard and the tests
together, so it has been left alone deliberately rather than half-done.
`using_placeholder_data()` returns False as of 4 August 2026, because no row
in the emissions table carries the PLACEHOLDER marker any more.
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
    for the same country. RESOLVED 4 August 2026: Riya's data is taken as
    final for this project, so this internal-consistency reasoning stands as
    the deciding rule rather than a placeholder choice pending her sign-off.

    Halifax-Hamburg ammonia has no blue (SMR+CCS) row in her table at all, so
    that pathway is dropped here rather than left on an invented number.
    Ningbo-Felixstowe ammonia has only one grey/coal route in her table, so
    the two separate placeholder pathways that used to stand in for it
    (grey_smr and coal_gasification) collapse into one, named coal_gasification
    to match the naming already used for Ningbo hydrogen's equivalent route.

    UPDATED 4 August 2026 from Riya's next delivery ("Assumptions Table
    (Emissions Assumptions)"), same source paper for each figure below unless
    stated, so no internal-consistency trade-off was needed this time:

    - HH hydrogen blue_smr_ccs: 4.89 -> 2.02. Her new sheet gives a single
      value for "SMR + CCS" rather than the earlier figure; same source paper
      as the Canada green/grey rows, so still one internally consistent study.
    - NF hydrogen green_electrolysis: 2.245 -> 2.34 (new midpoint of
      1.51-3.17, up from the previous 1.45-3.04 reading of the same source).
    - NF hydrogen coal_gasification: 19.11 -> 29.02. The new sheet does not
      repeat the earlier GREET-based source (S0360544225018249); it instead
      gives "Coal gasification (without CCS)" at 29.02 from a 2022 paper
      (S0360319921042737), which is the more directly-labelled match for this
      pathway name, so that replaces the old figure and source. SUPERSEDED
      later the same day by the source-consistency switch below; the live
      figure is 20.09, not 29.02.
    - NF ammonia coal_gasification: 4.6 -> 6.15 (midpoint of 6.14-6.16).
      GENUINE ERROR FIX, not just an update: the 4.6 figure (quoted as
      "midpoint of published range 4.4-4.8") came from the same paper
      (S0301479723016365) as this new sheet, but the new sheet shows that
      range actually belongs to a separate "Methane/Natural gas" row
      (4.81-4.83, midpoint 4.82) in the same paper, not to the coal
      gasification row (6.14-6.16, midpoint 6.15) it was labelled as. The old
      value was the natural-gas figure mislabelled as coal gasification, now
      corrected. Her natural-gas ammonia figure (4.82) is not modelled as its
      own separate pathway; it has no production cost anywhere in her
      delivery, so adding it is a scope decision for Samir.

    SOURCE-CONSISTENCY SWITCH, 4 August 2026, agreed with Riya in writing
    ("if that one's better go ahead"). The whole China hydrogen row now comes
    from a single study, S0360319925010602 ("Comprehensive assessment of
    China's hydrogen energy supply chain: Energy, environment, and economy",
    Int. J. Hydrogen Energy 2025), which publishes green, grey and blue with
    both emissions and production cost under one framework:

      - green_electrolysis  2.34 (midpoint 1.51-3.17), USD 5.72-6.62/kg
      - coal_gasification  20.09 ("Fossil-based hydrogen"), USD 1.24-1.45/kg
      - blue_ccs            6.28 ("Coal hydrogen with CCS"), USD 1.87-2.08/kg

    Only green was already on this paper. Grey moves off S0360319921042737
    (29.02) and blue off S0959652622021151 (7.91), and all three production
    costs move off S097308262400214X.

    Why this was worth doing: every headline result for this corridor is a
    *difference* between pathways (grey minus green, grey minus blue). When
    the two sides come from studies with different system boundaries, part of
    that difference is method rather than technology, and the error is
    invisible in the output because each individual number still looks
    sourced and reasonable.

    Two judgement calls inside the switch, both recorded rather than silent:

    1. The paper's grey row is labelled "Fossil-based hydrogen", not "coal
       gasification". The pathway key stays `coal_gasification` because it is
       referenced across the tests, dashboard and output CSVs, but the
       production_method string now says what the paper says. At 20.09
       tCO2e/t the figure is coal-consistent anyway (Chinese SMR sits nearer
       10), so the route is the same one; only the label is broader.
    2. The paper gives two blue routes. CH-CCS (6.28) is used rather than
       NGH-CCS (3.91-8.20) because China's blue hydrogen is coal-based, which
       keeps blue on the same feedstock as the grey row it is compared
       against.

    This also resolves what was previously flagged here as UNRECONCILED: Riya's
    two sheets disagreed on China green hydrogen production cost, USD 4.63/kg
    (ALK electrolysis, S097308262400214X) against USD 5.72-6.62/kg (Wind/PV,
    S0360319925010602), 24-43% apart on the largest cost term for the corridor.
    Taking the whole row from one paper picks the latter and removes the
    conflict rather than leaving it to be stated in the methodology.

    Still present in Riya's delivery and still not modelled as separate
    pathways, since adding routes is a scope decision rather than a correction:
      - NF hydrogen blue "Natural gas hydrogen with CCS (NGH-CCS)" 3.91-8.20,
        USD 2.37-3.59/kg
      - NF hydrogen blue "Coal Gasification with CCS" 13.99, no cost given
      - HH hydrogen green "PEM electrolysis (grid average)" 1.34, no cost

    The four "cbam_default" rows (one per product per country) are not
    literature LCA figures. They are the actual IR 2025/2621 default embedded
    emissions values, country-specific as the regulation requires. Unlike the
    literature pathways, these should be run with using_default_values=True so
    the mark-up (10% in 2026) applies on top of them, since that mark-up is a
    penalty for using regulatory defaults instead of verified actual emissions,
    not something to apply to a literature LCA figure that already assumes it
    represents genuine production.

    Riya's table has no origin carbon price column, but this has since been
    looked up separately and is no longer invented. Canada: federal OBPS
    (Output-Based Pricing System) rate, CAD 95/tCO2e for 2026 as of the
    revised price path published 15 May 2026 (corrected 5 Aug 2026 by Alex,
    Student 4 - the earlier CAD 110 was an extrapolation from a December 2020
    plan that was superseded before it was ever checked against a primary
    source). This column holds the 2026 baseline only, converted to EUR at
    the 23 July 2026 ECB reference rate; `run_cbam_matrix` and
    `run_compliance_matrix` use `regulatory_constants.origin_carbon_price_eur`
    instead, which carries the full year-varying schedule through 2030 and is
    what CBAM figures are actually computed from. Either way it is an upper
    bound, because OBPS only charges above a facility-specific benchmark and
    EverWind's actual performance against it is unknown. China: EUR 0,
    because neither hydrogen nor ammonia production is yet covered by China's
    national ETS, so there is nothing to deduct. See regulatory_constants.py
    for full sourcing on both. Origin price is a country-level fact, not a
    product-level one, so ammonia gets the same Canada/China figures as
    hydrogen.
    """
    ca = rc.ORIGIN_CARBON_PRICE_CANADA_EUR_PER_TCO2E  # EUR 59.27, 2026 baseline, see above
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
        (HH, "hydrogen", "blue_smr_ccs", 2.02, ca,
         "SMR + CCS",
         "Riya, https://link.springer.com/article/10.1007/s11708-025-1008-2 "
         "(updated 4 Aug 2026 delivery; was 4.89)"),
        (HH, "hydrogen", "cbam_default", 10.82, ca,
         "IR 2025/2621 default, Canada",
         "Riya, CBAM Default Values (IR 2025/2621). Use with using_default_values=True."),
        (NF, "hydrogen", "green_electrolysis", 2.34, cn,
         "Electrolytic Water Hydrogen, Wind/PV",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0360319925010602 "
         "midpoint of published range 1.51-3.17 (updated 4 Aug 2026 delivery; "
         "was 2.245, midpoint of 1.45-3.04)"),
        (NF, "hydrogen", "coal_gasification", 20.09, cn,
         "Fossil-based hydrogen (predominantly coal, without CCS)",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0360319925010602 "
         "(single value. Source-consistency switch 4 Aug 2026, agreed with Riya: "
         "replaces 29.02 from S0360319921042737 so China grey, green and blue all "
         "come from one unified-framework study - see module docstring)"),
        (NF, "hydrogen", "blue_ccs", 6.28, cn,
         "Coal hydrogen with CCS (CH-CCS)",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0360319925010602 "
         "(single value. Source-consistency switch 4 Aug 2026, agreed with Riya: "
         "replaces 7.91 from S0959652622021151. CH-CCS chosen over the same paper's "
         "NGH-CCS route because China's blue hydrogen is coal-based, matching the "
         "grey route above)"),
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
        (NF, "ammonia", "coal_gasification", 6.15, cn,
         "Coal gasification",
         "Riya, https://www.sciencedirect.com/science/article/pii/S0301479723016365 "
         "midpoint of published range 6.14-6.16 (2023). CORRECTED 4 Aug 2026: "
         "was 4.6, which the 4 Aug delivery shows was actually the paper's "
         "Methane/Natural gas row (4.81-4.83), mislabelled as coal "
         "gasification - see the module docstring above."),
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
                    "voyage_co2e_t": profile["voyage_co2e_t"],
                    "port_in_port_emissions_t": profile["port_in_port_emissions_t"],
                    "port_in_port_emissions_co2e_t": profile[
                        "port_in_port_emissions_co2e_t"
                    ],
                    "voyage_energy_mj": profile["voyage_energy_mj"],
                    "fueleu_actual_intensity_gco2e_mj": profile[
                        "fueleu_actual_intensity_gco2e_mj"
                    ],
                    "source": "Gayu FINAL_shipping_maritime_cost_model_updated.ipynb "
                    "(5 Aug 2026 delivery, adds CH4/N2O CO2e)",
                }
            )
    return pd.DataFrame(rows)


def _placeholder_commercial() -> pd.DataFrame:
    """Production cost is now real. Conversion and shipping cost are not.

    No owner is formally assigned for this table (see data/README.md), but
    Riya's 4 August 2026 delivery included two production-cost sheets
    ("Production Costs - Literature" and "Production Costs (IEA)") alongside
    the emissions update, so production cost - the largest single term in
    delivered cost - is filled in here from literature/IEA figures rather than
    invented. Conversion cost (liquefaction, cracking, storage) and shipping
    cost (freight rate) still have no source at all and remain placeholders;
    `run_delivered_cost()` stays blocked on those two, not production cost.

    Production cost sourcing, all corridor/product/pathway combinations that
    exist in the emissions table (each USD figure from the "Literature" sheet,
    converted to EUR at the 23 July 2026 ECB rate, `rc.usd_to_eur`):

    - HH hydrogen grey_smr: Canada grey, natural gas reformation, USD 700/t
      (single value).
    - HH hydrogen blue_smr_ccs: Canada blue, SMR, USD 1,100-1,300/t (midpoint
      1,200).
    - HH hydrogen green_electrolysis: Canada green, USD 3,950-4,270/t
      (midpoint 4,110).
    - NF hydrogen coal_gasification: China grey, fossil-based, USD
      1,240-1,450/t (midpoint 1,345).
    - NF hydrogen blue_ccs: China blue, coal + CCS, USD 1,870-2,080/t
      (midpoint 1,975).
    - NF hydrogen green_electrolysis: China green, wind/PV electrolysis, USD
      5,720-6,620/t (midpoint 6,170).

    The three China hydrogen figures above come from the emissions sheet's own
    "Production Cost Mentioned" column (S0360319925010602), not the
    "Production Costs - Literature" sheet (S097308262400214X) the other seven
    use. That is deliberate: it puts China hydrogen cost on the same study as
    China hydrogen emissions. See `_placeholder_emissions` for the full
    reasoning and the values it replaced.
    - HH ammonia grey_smr: Canada grey, USD ~509/t.
    - HH ammonia green_electrolysis: Canada green, USD ~1,057/t.
    - NF ammonia coal_gasification: China grey, coal gasification, USD
      404-545/t (midpoint 474.5).
    - NF ammonia green_electrolysis: China green, USD 822.6/t.

    None of these are corridor/route-specific quotes for EverWind or the
    specific China producer this study models - they are literature LCOH/LCOA
    figures for the country and pathway in general, same limitation as the
    emissions figures. The IEA sheet (year- and method-specific, 2025 vs 2030,
    China and "North America") is not yet used: the model has no
    year-varying production cost mechanism, only a flat figure per pathway, so
    incorporating it means deciding whether production cost should vary by
    scenario year the way carbon prices already do. Left for a deliberate
    decision rather than picked here.

    `cbam_default` rows are priced as their corridor's grey literature pathway,
    same convention as before - `cbam_default` is an emissions figure (the IR
    2025/2621 regulatory default), not an actual production route, so it has
    no production-cost literature of its own.
    """
    usd_per_pathway = {
        ("hydrogen", "grey_smr"): 700.0,
        ("hydrogen", "blue_smr_ccs"): (1100.0 + 1300.0) / 2,
        ("hydrogen", "blue_ccs"): (1870.0 + 2080.0) / 2,
        ("hydrogen", "green_electrolysis_hh"): (3950.0 + 4270.0) / 2,
        ("hydrogen", "green_electrolysis_nf"): (5720.0 + 6620.0) / 2,
        ("hydrogen", "coal_gasification"): (1240.0 + 1450.0) / 2,
        ("ammonia", "grey_smr"): 509.0,
        ("ammonia", "green_electrolysis_hh"): 1057.0,
        ("ammonia", "green_electrolysis_nf"): 822.6,
        ("ammonia", "coal_gasification"): (404.0 + 545.0) / 2,
    }

    def _cost_key(corridor, product, pathway):
        if pathway == "green_electrolysis":
            return (product, "green_electrolysis_hh" if corridor == HH else "green_electrolysis_nf")
        if pathway == "cbam_default":
            return (product, "grey_smr" if corridor == HH else "coal_gasification")
        return (product, pathway)

    conversion = {"hydrogen": 1200.0, "ammonia": 150.0}
    shipping = {(HH, "hydrogen"): 800.0, (HH, "ammonia"): 120.0,
                (NF, "hydrogen"): 1400.0, (NF, "ammonia"): 210.0}

    emissions = _placeholder_emissions()
    rows = []
    for _, r in emissions.iterrows():
        corridor, product, pathway = r["corridor"], r["product"], r["pathway"]
        production_cost_usd = usd_per_pathway[_cost_key(corridor, product, pathway)]
        rows.append(
            {
                "corridor": corridor,
                "product": product,
                "pathway": pathway,
                "production_cost_eur_per_tonne": round(rc.usd_to_eur(production_cost_usd), 1),
                "conversion_cost_eur_per_tonne": conversion[product],
                "shipping_cost_eur_per_tonne": shipping[(corridor, product)],
                "source": (
                    "Production cost: Riya, Assumptions Table (Production Costs - "
                    "Literature), delivered 4 Aug 2026, converted USD to EUR at the "
                    "23 July 2026 ECB reference rate. Conversion and shipping cost: "
                    "PLACEHOLDER - no owner assigned, see data/README.md."
                ),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Ayub et al. (2024) production costs, a second robustness check on Canada
# hydrogen specifically, found by Riya on 5 August 2026.
# ---------------------------------------------------------------------------
# Ayub, H.M.U., Alnouri, S.Y., Stijepovic, M., Stijepovic, V. and Hussein,
# I.A. (2024) 'A cost comparison study for hydrogen production between
# conventional and renewable methods', Process Safety and Environmental
# Protection, 186, pp. 1379-1395. https://doi.org/10.1016/j.psep.2024.04.080
#
# USD per kg H2, Canada column, converted to USD/tonne (x1000) below. Grey
# route is natural gas reforming without CCUS (Table 5); blue is the same
# route with CCUS (Table 6); green is electrolysis, not the paper's separate
# nuclear-energy route (Table 7), to match how `green_electrolysis` is used
# elsewhere in this model.
_AYUB_USD_PER_KG_CANADA = {
    "grey_smr": 0.70,
    "blue_smr_ccs": 0.91,
    "green_electrolysis": 10.80,
}

# The paper also gives a Canada nuclear-energy H2 cost of USD 7.075/kg
# (Table 7). Not mapped to a modelled pathway - "green_electrolysis" here
# specifically means grid/renewable electricity into an electrolyser, and
# nuclear-driven production is a different route this model does not
# otherwise carry - but kept here for anyone checking the source table by
# hand.
AYUB_NUCLEAR_USD_PER_KG_CANADA = 7.075


def ayub_production_costs() -> pd.DataFrame:
    """Canada hydrogen production cost per pathway, from Ayub et al. (2024).

    A second, independent robustness check alongside `iea_production_costs`,
    covering only what that paper covers: Canada (Halifax-Hamburg corridor),
    hydrogen only, three pathways. No China or ammonia figures exist in it, so
    this cannot replace the IEA check, only supplement it on the one corridor
    both the primary literature source and the IEA figures already disagree
    on most.

    Grey production cost agrees almost exactly with the current primary
    figure (USD 700/t vs this paper's USD 700/t). Blue and, especially,
    green diverge substantially - see `docs/` for the three-way comparison
    against the primary literature source and the IEA check. That divergence
    is reported as a genuine finding (production cost uncertainty, not a
    error to resolve by picking a winner), consistent with how the IEA check
    is already used elsewhere in this model.

    Returns the same corridor/product/pathway shape as the commercial table.
    """
    rows = []
    for pathway, usd_per_kg in _AYUB_USD_PER_KG_CANADA.items():
        usd_per_tonne = usd_per_kg * 1000
        rows.append(
            {
                "corridor": HH,
                "product": "hydrogen",
                "pathway": pathway,
                "production_cost_eur_per_tonne": round(rc.usd_to_eur(usd_per_tonne), 1),
                "source": (
                    "Ayub et al. (2024), Process Safety and Environmental Protection, "
                    "186, pp.1379-1395, https://doi.org/10.1016/j.psep.2024.04.080, "
                    f"Canada column, USD {usd_per_kg:.2f}/kg. Found by Riya, 5 Aug 2026. "
                    "ROBUSTNESS CHECK ONLY, not a primary input."
                ),
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


# ---------------------------------------------------------------------------
# IEA production costs, used only as a robustness check on the two cost gaps
# that are still built from separate studies. Not part of the primary inputs.
# ---------------------------------------------------------------------------

IEA_YEARS = (2025, 2030)

# From Riya's "Assumptions Table (Production Costs (IEA))" sheet, delivered
# 4 August 2026. USD per tonne of product. Ranges as published; the model takes
# midpoints, same convention as the literature table.
#
# Three transcription faults in her sheet are corrected here rather than
# carried through, and each is noted so the correction is visible:
#   - one China hydrogen coal row is dated 2026 while every other row is 2025
#     or 2030; read as 2025, since 2030 already has its own row at the same
#     value (1.3 USD/kg).
#   - the 2025 China ammonia "Coal with CCUS" range is written 771-768,
#     high-then-low; read as 768-771.
#   - the origin column spells China as "CHina" on eight rows.
_IEA_USD_PER_TONNE = {
    # (region, product, route): {year: (low, high)}
    ("north_america", "hydrogen", "gas_no_ccus"): {2025: (1100, 2000), 2030: (1100, 2100)},
    ("north_america", "hydrogen", "gas_ccus"): {2025: (1500, 2600), 2030: (1500, 2700)},
    ("north_america", "hydrogen", "electrolysis_wind"): {2025: (5000, 7000), 2030: (3200, 5800)},
    ("north_america", "hydrogen", "electrolysis_solar"): {2025: (6600, 14500), 2030: (4100, 10600)},
    ("china", "hydrogen", "coal_no_ccus"): {2025: (1300, 1300), 2030: (1300, 1300)},
    ("china", "hydrogen", "coal_ccus"): {2025: (1700, 1700), 2030: (1700, 1700)},
    ("china", "hydrogen", "electrolysis_wind"): {2025: (3500, 5400), 2030: (2000, 4600)},
    ("china", "hydrogen", "electrolysis_solar"): {2025: (3400, 8100), 2030: (2100, 6300)},
    ("north_america", "ammonia", "gas_no_ccus"): {2025: (350, 507), 2030: (362, 522)},
    ("north_america", "ammonia", "gas_ccus"): {2025: (421, 610), 2030: (422, 619)},
    ("north_america", "ammonia", "electrolysis_wind"): {2025: (1095, 1467), 2030: (758, 1239)},
    ("north_america", "ammonia", "electrolysis_solar"): {2025: (1371, 2812), 2030: (905, 2096)},
    ("china", "ammonia", "coal_no_ccus"): {2025: (575, 594), 2030: (573, 593)},
    ("china", "ammonia", "coal_ccus"): {2025: (768, 771), 2030: (746, 756)},
    ("china", "ammonia", "electrolysis_wind"): {2025: (816, 1152), 2030: (505, 996)},
    ("china", "ammonia", "electrolysis_solar"): {2025: (769, 1745), 2030: (546, 1303)},
}

# Which IEA route stands in for each modelled pathway. Green maps to onshore
# wind rather than solar PV because both green pathways in the primary data are
# wind-driven: the Canada figure comes from "Levelized cost of green hydrogen
# in Canada: Wind energy-driven water electrolysis" (S0960148125012959), and
# Riya labels the China route "Electrolytic Water Hydrogen, Wind/PV". Solar PV
# is carried in the table above so the sensitivity can be run both ways; it is
# consistently the more expensive of the two.
_IEA_ROUTE_FOR_PATHWAY = {
    ("hydrogen", "grey_smr"): "gas_no_ccus",
    ("hydrogen", "blue_smr_ccs"): "gas_ccus",
    ("hydrogen", "coal_gasification"): "coal_no_ccus",
    ("hydrogen", "blue_ccs"): "coal_ccus",
    ("hydrogen", "green_electrolysis"): "electrolysis_wind",
    ("ammonia", "grey_smr"): "gas_no_ccus",
    ("ammonia", "coal_gasification"): "coal_no_ccus",
    ("ammonia", "green_electrolysis"): "electrolysis_wind",
}

_IEA_REGION_FOR_CORRIDOR = {HH: "north_america", NF: "china"}


def iea_production_costs(year: int = 2030, green_route: str = "wind") -> pd.DataFrame:
    """Production cost per pathway from the IEA sheet, as a robustness check.

    Returns the same corridor/product/pathway shape as the commercial table so
    it can be dropped into `marginal_abatement_cost` in place of the literature
    costs. It carries production cost only; conversion and shipping are absent
    because they are unsourced everywhere and cancel out of the pathway
    differences this is used for.

    Why this exists. Two of the four corridor-product cost gaps are still
    subtractions between separate studies: Canada hydrogen spans three papers
    and China ammonia spans two. Riya confirmed on 4 August 2026 that no single
    study covers the Canadian pathways. The IEA sheet does cover every pathway
    on both corridors under one methodology, so running the abatement result
    against it answers the question the mixed sourcing raises, which is whether
    the finding is an artefact of stitching studies together.

    It is a cross-check and not the primary input for two reasons. The IEA
    figures are regional, "North America" rather than Canada, and they are an
    agency benchmark rather than a peer-reviewed country-specific study. Using
    them as headline would trade a sourcing problem for a geography problem.

    `year` must be one of IEA_YEARS. The IEA publishes 2025 and 2030 only,
    while the model runs 2026-2030 on a flat production cost, so there is no
    year-varying production cost mechanism to feed. 2030 is the default because
    that is the year the abatement analysis is reported for.
    """
    if year not in IEA_YEARS:
        raise ValueError(f"IEA costs are published for {IEA_YEARS}, got {year}")
    if green_route not in ("wind", "solar"):
        raise ValueError(f"green_route must be 'wind' or 'solar', got {green_route!r}")

    emissions = _placeholder_emissions()
    rows = []
    for _, r in emissions.iterrows():
        corridor, product, pathway = r["corridor"], r["product"], r["pathway"]
        route = _IEA_ROUTE_FOR_PATHWAY.get((product, pathway))
        if route is None:
            continue  # cbam_default has no production route of its own
        if route == "electrolysis_wind" and green_route == "solar":
            route = "electrolysis_solar"
        low, high = _IEA_USD_PER_TONNE[
            (_IEA_REGION_FOR_CORRIDOR[corridor], product, route)
        ][year]
        rows.append(
            {
                "corridor": corridor,
                "product": product,
                "pathway": pathway,
                "production_cost_eur_per_tonne": round(
                    rc.usd_to_eur((low + high) / 2), 1
                ),
                "iea_route": route,
                "iea_year": year,
                "source": (
                    f"IEA, via Riya's Assumptions Table (Production Costs (IEA)) "
                    f"sheet delivered 4 Aug 2026. {route}, {year}, published range "
                    f"USD {low}-{high}/t, midpoint converted at the 23 July 2026 "
                    f"ECB reference rate. ROBUSTNESS CHECK ONLY, not a primary input."
                ),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Policy events
# ---------------------------------------------------------------------------

POLICY_EVENT_INSTRUMENT_TYPES = (
    "primary_legislation",
    "regulation",
    "implementing_regulation",
    "statutory_instrument",
    "treaty",
    "court_ruling",
    "plan",
    "consultation",
    "proposal",
    "procedural",
    "market_event",
)

POLICY_EVENT_STATUSES = (
    "in_force",
    "superseded",
    "proposed",
    "pending",
    "historic",
    "not_law",
)

POLICY_EVENT_AFFECTS_MODEL = ("yes", "no", "sensitivity_only")


def load_policy_events(path: Path = None) -> pd.DataFrame:
    """Alex's policy timeline, structured for the model.

    Frano asked in the 6 August 2026 meeting for two parallel tracks rather
    than one narrative timeline: the dated policy events themselves, each
    classified by legal instrument because that governs how likely and how
    fast it lands, and separately the quantified translation of each into a
    number and a date.

    This table carries both. `instrument_type` and `status` are track A;
    `quantified_effect` is track B and is deliberately left empty where the
    numeric translation has not been established, so the gaps are visible
    rather than guessed at.

    `model_parameter` names the constant in `config.regulatory_constants` or
    the input-table column the event bears on, which is what lets a test check
    the timeline and the model have not drifted apart. `affects_model`
    separates events that set a modelled value ("yes") from those that only
    justify a sensitivity ("sensitivity_only") or supply narrative context
    ("no").
    """
    if path is None:
        path = DATA_DIR / "policy_events.csv"
    events = pd.read_csv(Path(path)).fillna("")

    bad_instrument = set(events["instrument_type"]) - set(
        POLICY_EVENT_INSTRUMENT_TYPES
    )
    if bad_instrument:
        raise ValueError(
            f"Unknown instrument_type values: {sorted(bad_instrument)}. "
            f"Expected one of {POLICY_EVENT_INSTRUMENT_TYPES}."
        )

    bad_status = set(events["status"]) - set(POLICY_EVENT_STATUSES)
    if bad_status:
        raise ValueError(
            f"Unknown status values: {sorted(bad_status)}. "
            f"Expected one of {POLICY_EVENT_STATUSES}."
        )

    bad_affects = set(events["affects_model"]) - set(POLICY_EVENT_AFFECTS_MODEL)
    if bad_affects:
        raise ValueError(
            f"Unknown affects_model values: {sorted(bad_affects)}. "
            f"Expected one of {POLICY_EVENT_AFFECTS_MODEL}."
        )

    return events
