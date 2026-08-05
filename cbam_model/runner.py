"""Scenario runners, one per layer.

`run_maritime_matrix` is entirely Gayu's data and carries no assumptions of mine.
`run_cbam_matrix` is Riya's emissions plus the border rules. Both products and
both corridors now run on her real sourced figures, not placeholders.

The two are joined by `run_compliance_matrix` using Gayu's cargo tonnage.
`run_delivered_cost` remains blocked, but only on conversion and freight cost;
production cost is real as of Riya's 4 August 2026 delivery.
"""

import warnings

import pandas as pd

from .config import regulatory_constants as rc
from .config import scenarios
from .config import vessel_logistics as vl
from .config.unresolved import UnresolvedConstantError
from .model import total_cost
from . import data_io


def run_maritime_matrix(
    years=tuple(scenarios.YEARS),
    vessel_sets=vl.VESSEL_SETS,
    speed_scenarios=("lower", "base", "upper"),
    routes=vl.ROUTE_SCENARIOS,
    include_eu_berth_emissions: bool = False,
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """Maritime carbon cost per voyage, across Gayu's own scenario dimensions.

    Speed scenarios apply to the gas carrier only; the container ships have a
    single published service speed each. The Cape of Good Hope routing only
    differs for Ningbo-Felixstowe, so the Atlantic corridor is not duplicated
    across it.
    """
    rows = []
    for corridor in rc.CORRIDORS:
        for vessel in vessel_sets:
            speeds = speed_scenarios if vessel == "gas_carrier" else ("base",)
            for speed in speeds:
                for route in routes:
                    if route == "cape" and corridor not in vl.DISTANCE_NM_CAPE:
                        continue
                    profile = vl.corridor_profile(corridor, vessel, speed, route)
                    for year in years:
                        for price_scenario in rc.PRICE_SCENARIOS:
                            variants = ["current_scope"]
                            if (
                                rc.CORRIDOR_REGIME[corridor] == "UK"
                                and year >= rc.UK_ETS_INTL_EXPANSION_EARLIEST_YEAR
                            ):
                                variants = scenarios.UK_ETS_VARIANTS
                            for variant in variants:
                                # Bunker choice is only priced by FuelEU, which
                                # is EU-only, so the UK corridor runs the base
                                # case alone rather than duplicate rows.
                                bunkers = (
                                    scenarios.BUNKER_FUELS
                                    if rc.CORRIDOR_REGIME[corridor] == "EU"
                                    else ["conventional"]
                                )
                                for bunker in bunkers:
                                    rows.append(
                                        total_cost.maritime_cost_per_voyage(
                                            profile,
                                            year,
                                            price_scenario,
                                            variant,
                                            include_eu_berth_emissions,
                                            bunker_fuel=bunker,
                                            uk_price_variant=uk_price_variant,
                                        ).as_dict()
                                    )
    return pd.DataFrame(rows)


def run_cbam_matrix(
    emissions=None,
    years=tuple(scenarios.YEARS),
    uk_cbam_rate_override=None,
    using_default_values: bool = None,
    skip_unresolved: bool = True,
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """CBAM liability per tonne of product.

    `using_default_values` defaults to None, which lets `cbam_cost_per_tonne`
    derive it per row from the pathway (the IR 2025/2621 mark-up applies only
    to `cbam_default` rows, never to literature pathways). Pass an explicit
    True/False only to force every row the same way, which is rarely correct
    once literature and default pathways are mixed in the same run.
    """
    if emissions is None:
        emissions, _, _ = data_io.load_inputs()

    rows = []
    skipped = 0
    for _, e in emissions.iterrows():
        for year in years:
            for price_scenario in rc.PRICE_SCENARIOS:
                try:
                    rows.append(
                        total_cost.cbam_cost_per_tonne(
                            corridor=e["corridor"],
                            product=e["product"],
                            pathway=e["pathway"],
                            year=year,
                            price_scenario=price_scenario,
                            embedded_emissions_tco2e_per_tonne=e[
                                "embedded_emissions_tco2e_per_tonne"
                            ],
                            # Year-varying, not the emissions table's flat
                            # 2026-baseline column - see
                            # rc.origin_carbon_price_eur's docstring.
                            origin_carbon_price_eur_per_tco2e=rc.origin_carbon_price_eur(
                                e["corridor"], year
                            ),
                            using_default_values=using_default_values,
                            uk_cbam_rate_override=uk_cbam_rate_override,
                            uk_price_variant=uk_price_variant,
                        ).as_dict()
                    )
                except UnresolvedConstantError:
                    if not skip_unresolved:
                        raise
                    skipped += 1

    if skipped:
        warnings.warn(
            f"\n  {skipped} of {skipped + len(rows)} CBAM cases were skipped due to an "
            f"unresolved regulatory constant (see the raised error upstream for which "
            f"one). UK CBAM's rate mechanism and the GBP/EUR rate are both resolved as "
            f"of 1 August 2026 and no longer a source of skips; this now only fires for "
            f"a not-yet-sourced constant added later.",
            stacklevel=2,
        )

    return pd.DataFrame(rows)


def run_compliance_matrix(
    emissions=None,
    years=tuple(scenarios.YEARS),
    vessel_set: str = "gas_carrier",
    speed_scenario: str = "base",
    route: str = "suez",
    uk_cbam_rate_override=None,
    skip_unresolved: bool = True,
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """Total carbon compliance cost per tonne of product, both layers joined.

    Uses Gayu's cargo tonnage to convert her per-voyage maritime costs onto the
    per-tonne basis that CBAM works in. Defaults to the gas carrier base case
    on the Suez routing, since that is the primary scenario; the maritime matrix
    covers the full spread.
    """
    if emissions is None:
        emissions, _, _ = data_io.load_inputs()

    rows = []
    skipped = 0
    for corridor in rc.CORRIDORS:
        profile = vl.corridor_profile(corridor, vessel_set, speed_scenario, route)
        corridor_rows = emissions[emissions["corridor"] == corridor]
        for year in years:
            for price_scenario in rc.PRICE_SCENARIOS:
                variants = ["current_scope"]
                if (
                    rc.CORRIDOR_REGIME[corridor] == "UK"
                    and year >= rc.UK_ETS_INTL_EXPANSION_EARLIEST_YEAR
                ):
                    variants = scenarios.UK_ETS_VARIANTS
                for variant in variants:
                    maritime = total_cost.maritime_cost_per_voyage(
                        profile, year, price_scenario, variant,
                        uk_price_variant=uk_price_variant,
                    )
                    for _, e in corridor_rows.iterrows():
                        try:
                            cbam_row = total_cost.cbam_cost_per_tonne(
                                corridor=corridor,
                                product=e["product"],
                                pathway=e["pathway"],
                                year=year,
                                price_scenario=price_scenario,
                                embedded_emissions_tco2e_per_tonne=e[
                                    "embedded_emissions_tco2e_per_tonne"
                                ],
                                # Year-varying, not the emissions table's flat
                                # 2026-baseline column - see
                                # rc.origin_carbon_price_eur's docstring.
                                origin_carbon_price_eur_per_tco2e=rc.origin_carbon_price_eur(
                                    corridor, year
                                ),
                                uk_cbam_rate_override=uk_cbam_rate_override,
                                uk_price_variant=uk_price_variant,
                            )
                        except UnresolvedConstantError:
                            if not skip_unresolved:
                                raise
                            skipped += 1
                            continue
                        rows.append(
                            total_cost.compliance_cost_per_tonne(maritime, cbam_row)
                        )

    if skipped:
        warnings.warn(
            f"\n  {skipped} of {skipped + len(rows)} compliance cases were skipped due "
            f"to an unresolved regulatory constant (see the raised error upstream for "
            f"which one).",
            stacklevel=2,
        )

    return pd.DataFrame(rows)


def run_delivered_cost(compliance=None, commercial=None):
    """Add production, conversion and freight to give a full delivered cost.

    Still blocked, but for a different reason than before. Cargo tonnage has
    landed, so the two carbon layers now join. What is missing is the commercial
    side, which no student owns.
    """
    raise UnresolvedConstantError(
        "\n\n  Delivered cost is still blocked, but the blocker has moved.\n\n"
        "  RESOLVED: cargo tonnage, from Gayu's cargo_capacity_and_density_v2.ipynb.\n"
        "    56,142 t ammonia, 5,828 t hydrogen. Compliance cost per tonne now runs,\n"
        "    via run_compliance_matrix().\n\n"
        "  STILL MISSING: production, conversion and freight cost per tonne.\n"
        "    No student owns these in the data contracts. They are three of the six\n"
        "    terms in a delivered cost, and production cost is the largest single\n"
        "    component. See data/README.md.\n"
    )


def summarise_maritime(maritime: pd.DataFrame) -> pd.DataFrame:
    """Headline maritime carbon cost per voyage, base case only.

    Base case is conventional VLSFO bunkers; the green-bunker rows are a
    separate comparison and would double up the EU corridor here.
    """
    base = maritime[
        (maritime["speed_scenario"].isin(["base", "service"]))
        & (maritime["route_scenario"] == "suez")
        & (maritime["uk_ets_variant"].isin(["n/a", "current_scope"]))
        & (maritime["bunker_fuel"].isin(["conventional", "n/a"]))
    ]
    return base[
        [
            "corridor", "vessel_set", "year", "price_scenario", "distance_nm",
            "voyage_days", "voyage_co2_t", "eu_ets_cost_eur", "fueleu_cost_eur",
            "uk_ets_cost_gbp", "total_eur", "total_gbp",
        ]
    ].sort_values(["year", "corridor", "vessel_set", "price_scenario"])
