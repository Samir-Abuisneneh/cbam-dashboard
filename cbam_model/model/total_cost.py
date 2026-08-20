"""Cost assembly, in two layers plus the join between them.

Gayu's maritime data is per voyage. CBAM liability is per tonne of product,
because embedded emissions are expressed per tonne. Converting between the two
requires the cargo tonnage of a voyage, which her notebooks did not originally
state because they never needed it.

    maritime_cost_per_voyage    EU ETS, UK ETS and FuelEU. Entirely Gayu's data.
    cbam_cost_per_tonne         EU and UK CBAM. Riya's emissions plus the border rules.
    compliance_cost_per_tonne   The two joined, using her cargo capacity notebook.

The join was unblocked by `cargo_capacity_and_density_v2.ipynb` (25 July 2026),
so `compliance_cost_per_tonne` runs end to end. `delivered_cost` sits one step
beyond it. Production, conversion and freight cost are a scope boundary, not a
pending input: this study reports carbon compliance cost per tonne, not
delivered cost. `delivered_cost` exists so a caller can supply those figures
themselves; it raises rather than guessing at a default.

Currencies are never mixed here. EU-regime costs are EUR, UK-regime costs are
GBP, and no exchange rate is applied in this module, matching how Gayu presents
her tables. `analysis/outputs.py` converts where a single-currency comparison is
explicitly labelled, using the `_gbp_equivalent` naming convention.
"""

from dataclasses import asdict, dataclass

from ..config import regulatory_constants as rc
from ..config.unresolved import is_unresolved
from . import cbam, ets_maritime, fueleu


@dataclass
class MaritimeCost:
    """Carbon cost of one voyage. EUR for the EU corridor, GBP for the UK one."""

    corridor: str
    # Two distinct things, and they were conflated until 7 August 2026:
    # `vessel_set` is the scenario dimension ("gas_carrier" / "container", see
    # `vessel_logistics.VESSEL_SETS`), `vessel_class` is the display name of
    # the actual ship ("VLGC/VLAC"). This dataclass used to fill `vessel_set`
    # from the profile's `vessel_class`, so the same column name meant the
    # class in maritime and compliance frames and the set in sensitivity
    # frames. Anything joining or filtering across the two silently matched
    # nothing.
    vessel_set: str
    vessel_class: str
    route_scenario: str
    speed_scenario: str
    year: int
    price_scenario: str
    uk_ets_variant: str
    distance_nm: float
    voyage_days: float
    voyage_co2_t: float
    port_co2_t: float
    voyage_co2e_t: float = 0.0
    port_co2e_t: float = 0.0
    uk_price_variant: str = "frozen"
    bunker_fuel: str = "conventional"
    eu_ets_cost_eur: float = 0.0
    fueleu_cost_eur: float = 0.0
    uk_ets_cost_gbp: float = 0.0
    total_eur: float = 0.0
    total_gbp: float = 0.0

    def as_dict(self):
        return asdict(self)


@dataclass
class CbamCost:
    """CBAM liability per tonne of product. EUR for the EU, GBP for the UK."""

    corridor: str
    product: str
    pathway: str
    year: int
    price_scenario: str
    embedded_emissions_tco2e_per_tonne: float
    uk_price_variant: str = "frozen"
    eu_cbam_cost_eur_per_tonne: float = 0.0
    uk_cbam_cost_gbp_per_tonne: float = 0.0

    def as_dict(self):
        return asdict(self)


def maritime_cost_per_voyage(
    profile: dict,
    year: int,
    price_scenario: str,
    uk_ets_variant: str = "current_scope",
    include_eu_berth_emissions: bool = False,
    bunker_fuel: str = "conventional",
    uk_price_variant: str = "frozen",
) -> MaritimeCost:
    """Carbon cost of one voyage, from Gayu's voyage profile.

    Args:
        profile: output of `vessel_logistics.corridor_profile`.
        include_eu_berth_emissions: EU ETS does cover emissions at berth in an
            EEA port at 100%, but Gayu's notebooks cost the voyage only. Default
            False so results reproduce hers exactly. Setting True adds the
            Hamburg port call and makes the EU figure slightly more complete
            than her published number.
        bunker_fuel: "conventional" (VLSFO, the default - matches Gayu's
            published figures) or "green_rfnbo" (the ship bunkers its own
            cargo product as fuel instead). Only affects FuelEU, which only
            applies to the EU corridor; UK ETS and EU ETS cost the voyage's
            actual CO2 regardless of bunker fuel choice, since the vessel
            still burns VLSFO for propulsion in both scenarios in this
            model - "green_rfnbo" isolates the FuelEU compliance-cost effect
            of green bunker fuel, not a full re-modelling of the voyage.
    """
    corridor = profile["corridor"]
    regime = rc.CORRIDOR_REGIME[corridor]

    cost = MaritimeCost(
        corridor=corridor,
        vessel_set=profile["vessel_set"],
        vessel_class=profile["vessel_class"],
        route_scenario=profile["route_scenario"],
        speed_scenario=profile.get("speed_scenario", "base"),
        year=year,
        price_scenario=price_scenario,
        uk_ets_variant=uk_ets_variant if regime == "UK" else "n/a",
        distance_nm=profile["distance_nm"],
        voyage_days=profile["voyage_days"],
        voyage_co2_t=profile["voyage_co2_t"],
        port_co2_t=profile["port_in_port_emissions_t"],
        voyage_co2e_t=profile.get("voyage_co2e_t", profile["voyage_co2_t"]),
        port_co2e_t=profile.get(
            "port_in_port_emissions_co2e_t", profile["port_in_port_emissions_t"]
        ),
        uk_price_variant=uk_price_variant if regime == "UK" else "n/a",
        bunker_fuel=bunker_fuel if regime == "EU" else "n/a",
    )

    if regime == "EU":
        eu_price = rc.eu_ets_price(year, price_scenario)
        # CO2e (CO2 + CH4 + N2O), not CO2 alone - EU ETS maritime scope has
        # covered all three since 1 January 2026 (Gayu's notebook, 5 Aug 2026).
        cost.eu_ets_cost_eur = ets_maritime.eu_ets_maritime_cost(
            cost.voyage_co2e_t,
            year,
            eu_price,
            rc.EU_ETS_CORRIDOR_COVERAGE[corridor],
            cost.port_co2e_t if include_eu_berth_emissions else 0.0,
        )
        if bunker_fuel == "green_rfnbo":
            fueleu_actual_intensity = fueleu.effective_intensity_with_rfnbo(
                rc.FUELEU_GREEN_BUNKER_WTW_INTENSITY, rfnbo_energy_share=1.0, year=year
            )
        else:
            fueleu_actual_intensity = profile["fueleu_actual_intensity_gco2e_mj"]
        cost.fueleu_cost_eur = fueleu.fueleu_cost(
            fueleu_actual_intensity,
            profile["voyage_energy_mj"],
            year,
        )
        cost.total_eur = cost.eu_ets_cost_eur + cost.fueleu_cost_eur
    else:
        # CO2e, not CO2 alone - UK ETS maritime scope mirrors the EU's CH4/N2O
        # coverage from 1 July 2026 (SI 2026/392, Schedule 2A).
        cost.uk_ets_cost_gbp = ets_maritime.uk_ets_maritime_cost(
            cost.port_co2e_t,
            year,
            rc.uk_ets_price(year, price_scenario, uk_price_variant),
            voyage_co2_t=cost.voyage_co2e_t,
            include_intl_expansion=(uk_ets_variant == "proposed_expansion"),
        )
        cost.total_gbp = cost.uk_ets_cost_gbp

    return cost


def cbam_cost_per_tonne(
    corridor: str,
    product: str,
    pathway: str,
    year: int,
    price_scenario: str,
    embedded_emissions_tco2e_per_tonne: float,
    origin_carbon_price_eur_per_tco2e: float = 0.0,
    using_default_values: bool | None = None,
    uk_cbam_rate_override=None,
    uk_price_variant: str = "frozen",
    cbam_mechanism: str | None = None,
) -> CbamCost:
    """CBAM liability per tonne of product landed.

    Args:
        using_default_values: Whether the IR 2025/2621 mark-up applies. Leave
            as None (the default) to derive this from `pathway`: the mark-up
            applies only to the `cbam_default` pathway, never to literature
            LCA pathways. Pass an explicit True/False only to override that
            per-row behaviour deliberately, e.g. in a reference-case check.
        cbam_mechanism: EU free-allocation treatment, see
            `regulatory_constants.EU_CBAM_MECHANISMS`. This function is safe to
            use with "benchmark_shielded" because its emissions argument is per
            tonne of product by construction, which is the basis the benchmark
            is defined on.
    """
    if using_default_values is None:
        using_default_values = cbam.is_cbam_default_pathway(pathway)

    regime = rc.CORRIDOR_REGIME[corridor]
    cost = CbamCost(
        corridor=corridor,
        product=product,
        pathway=pathway,
        year=year,
        price_scenario=price_scenario,
        embedded_emissions_tco2e_per_tonne=embedded_emissions_tco2e_per_tonne,
        uk_price_variant=uk_price_variant if regime == "UK" else "n/a",
    )

    if regime == "EU":
        mechanism = rc.EU_CBAM_DEFAULT_MECHANISM if cbam_mechanism is None else cbam_mechanism
        cost.eu_cbam_cost_eur_per_tonne = cbam.eu_cbam_cost(
            embedded_emissions_tco2e_per_tonne,
            year,
            rc.eu_ets_price(year, price_scenario),
            origin_carbon_price_eur_per_tco2e,
            using_default_values,
            mechanism,
            # Looked up per product, so the caller cannot pair a hydrogen row
            # with an ammonia benchmark. Only read when the benchmark
            # mechanism is selected, so an unknown product does not break the
            # default path.
            rc.cbam_benchmark(product)
            if mechanism == "benchmark_shielded"
            else None,
            product,
        )
    else:
        cost.uk_cbam_cost_gbp_per_tonne = cbam.uk_cbam_cost(
            embedded_emissions_tco2e_per_tonne,
            year,
            rc.uk_ets_price(year, price_scenario, uk_price_variant),
            uk_cbam_rate_override,
            # Emissions table stores origin prices in EUR; UK regime is GBP.
            rc.eur_to_gbp(origin_carbon_price_eur_per_tco2e),
        )

    return cost


def compliance_cost_per_tonne(
    maritime: MaritimeCost,
    cbam_per_tonne: CbamCost,
    cargo_tonnes=None,
) -> dict:
    """Total carbon compliance cost per tonne of product landed.

    Joins the maritime layer to the CBAM layer using Gayu's cargo tonnage. This
    is the complete regulatory cost of moving one tonne of product along the
    corridor: CBAM at the border, plus that tonne's share of the voyage's ETS
    and FuelEU liability.

    It is not a delivered cost. Production, conversion and freight are a scope
    boundary, not a pending input: they are invariant to production pathway,
    so they cancel out of every within-corridor comparison this study makes.
    What this does answer is the question the dissertation is actually named
    after, which is what carbon regulation costs per tonne on each corridor.
    """
    product = cbam_per_tonne.product
    if cargo_tonnes is None:
        cargo_tonnes = _cargo_tonnes()[product]
    if is_unresolved(cargo_tonnes):
        cargo_tonnes._fail()
    if cargo_tonnes <= 0:
        raise ValueError("cargo_tonnes must be positive")

    regime = rc.CORRIDOR_REGIME[maritime.corridor]
    currency = "EUR" if regime == "EU" else "GBP"

    eu_ets_pt = maritime.eu_ets_cost_eur / cargo_tonnes
    fueleu_pt = maritime.fueleu_cost_eur / cargo_tonnes
    uk_ets_pt = maritime.uk_ets_cost_gbp / cargo_tonnes
    maritime_pt = eu_ets_pt + fueleu_pt + uk_ets_pt
    cbam_pt = (
        cbam_per_tonne.eu_cbam_cost_eur_per_tonne
        if regime == "EU"
        else cbam_per_tonne.uk_cbam_cost_gbp_per_tonne
    )

    return {
        "corridor": maritime.corridor,
        "product": product,
        "pathway": cbam_per_tonne.pathway,
        "year": maritime.year,
        "price_scenario": maritime.price_scenario,
        "route_scenario": maritime.route_scenario,
        "speed_scenario": maritime.speed_scenario,
        "vessel_set": maritime.vessel_set,
        "vessel_class": maritime.vessel_class,
        "uk_ets_variant": maritime.uk_ets_variant,
        # Both scenario dimensions have to travel with the row. Without them a
        # saved compliance table cannot be told apart from one run under a
        # different scenario, which is exactly how a labelled what-if ends up
        # quoted as a baseline result.
        "uk_price_variant": maritime.uk_price_variant,
        "bunker_fuel": maritime.bunker_fuel,
        "currency": currency,
        "cargo_tonnes": cargo_tonnes,
        "embedded_emissions_tco2e_per_tonne": (
            cbam_per_tonne.embedded_emissions_tco2e_per_tonne
        ),
        "cbam_cost_per_tonne": cbam_pt,
        "eu_ets_cost_per_tonne": eu_ets_pt,
        "fueleu_cost_per_tonne": fueleu_pt,
        "uk_ets_cost_per_tonne": uk_ets_pt,
        "maritime_cost_per_tonne": maritime_pt,
        "total_compliance_cost_per_tonne": cbam_pt + maritime_pt,
    }


def delivered_cost(
    compliance: dict,
    production_cost_per_tonne=None,
    conversion_cost_per_tonne=None,
    shipping_cost_per_tonne=None,
) -> dict:
    """Add the commercial terms to give a full delivered cost per tonne.

    Out of scope for this study by design: production, conversion and freight
    cost are never modelled here (see `compliance_cost_per_tonne`), so there
    is no default to fall back on and none is supplied. A caller who wants a
    delivered cost has to bring those three figures themselves.
    """
    commercial = {
        "production_cost_per_tonne": production_cost_per_tonne,
        "conversion_cost_per_tonne": conversion_cost_per_tonne,
        "shipping_cost_per_tonne": shipping_cost_per_tonne,
    }
    missing = [k for k, v in commercial.items() if v is None]
    if missing:
        raise ValueError(
            f"Delivered cost needs {', '.join(missing)}. These are out of scope "
            f"for this study by design, so there is no default to fall back on. "
            f"Compliance cost per tonne is available without them via "
            f"compliance_cost_per_tonne(). See data/README.md."
        )

    out = dict(compliance)
    out.update(commercial)
    out["total_delivered_cost_per_tonne"] = compliance[
        "total_compliance_cost_per_tonne"
    ] + sum(commercial.values())
    return out


def _cargo_tonnes():
    """Gayu's cargo tonnage, imported lazily to avoid a circular import."""
    from ..config import vessel_logistics as vl

    return vl.CARGO_TONNES
