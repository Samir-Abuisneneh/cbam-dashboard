"""CBAM cost functions for both regimes.

All costs are returned in the currency of the price argument passed in: EUR for
the EU functions, GBP for the UK function. Conversion happens once, in
`total_cost.py`.
"""

from ..config import regulatory_constants as rc
from ..config.unresolved import is_unresolved, UnresolvedConstantError


CBAM_DEFAULT_PATHWAY_NAME = "cbam_default"


def is_cbam_default_pathway(pathway: str) -> bool:
    """Whether a pathway row represents an IR 2025/2621 regulatory default value.

    The 10/20/30 percent mark-up in `apply_default_value_markup` is a penalty
    for using a regulatory default instead of a verified actual emissions
    figure. It must never be applied to a literature LCA pathway (green
    electrolysis, grey SMR, blue SMR+CCS, coal gasification), which already
    represents a claimed actual production route rather than a fallback
    default.
    """
    return pathway == CBAM_DEFAULT_PATHWAY_NAME


def apply_default_value_markup(embedded_emissions_tco2e: float, year: int) -> float:
    """Apply the IR 2025/2621 mark-up to default embedded emissions values.

    Only applies where the declarant is using regulatory default values rather
    than verified actual emissions data. Do not apply to verified actuals.
    """
    return embedded_emissions_tco2e * (1 + rc.default_value_markup(year))


def eu_cbam_cost(
    embedded_emissions_tco2e: float,
    year: int,
    cert_price_eur: float,
    origin_carbon_price_eur_per_tco2e: float = 0.0,
    using_default_values: bool = False,
) -> float:
    """EU CBAM certificate cost in EUR for one shipment.

    Args:
        embedded_emissions_tco2e: Embedded emissions of the shipment, tCO2e.
        year: Import year, which selects the CBAM factor.
        cert_price_eur: Certificate price, EUR/tCO2e.
        origin_carbon_price_eur_per_tco2e: Carbon price effectively paid in the
            country of origin, EUR/tCO2e. Zero if none.
        using_default_values: If True, the IR 2025/2621 mark-up is applied.

    Note on the origin carbon price adjustment:
        The build spec wrote this as a flat subtraction of
        `origin_carbon_price` from the total cost. That is a unit error. The
        origin carbon price is a price per tonne (EUR/tCO2e), not a cost, so
        subtracting it directly from a EUR total takes roughly the price of one
        tonne of CO2 off a shipment-scale figure. The adjustment has to scale
        with the same emissions and the same CBAM factor as the liability it is
        offsetting, which is what this implementation does. Under
        Regulation (EU) 2023/956 Article 9 the origin carbon price reduces the
        number of certificates to be surrendered, so it enters on the same
        basis as the obligation itself and the result floors at zero.
    """
    if year < 2026:
        return 0.0

    emissions = embedded_emissions_tco2e
    if using_default_values:
        emissions = apply_default_value_markup(emissions, year)

    factor = rc.cbam_factor(year)
    chargeable_tco2e = emissions * factor

    net_price = cert_price_eur - origin_carbon_price_eur_per_tco2e
    return max(0.0, chargeable_tco2e * net_price)


def uk_cbam_cost(
    embedded_emissions_tco2e: float,
    year: int,
    uk_carbon_price_gbp: float,
    rate_fraction=None,
) -> float:
    """UK CBAM liability in GBP for one shipment.

    The UK scheme is a tax rather than a certificate-surrender system, and in
    year one it uses a single flat default value per CN code with no
    country differentiation.

    Liability = embedded_emissions x rate_fraction x UK ETS price, where
    rate_fraction = 1 - (baseline free allocation % x Article 16(14) factor)
    per the draft CBAM (Calculation of CBAM Rate...) Regulations 2026 and
    Finance Act 2026 s.149(4) - see `regulatory_constants.uk_cbam_rate_fraction`
    for the full derivation.

    Args:
        rate_fraction: Overrides the real computed rate_fraction for a
            clearly labelled what-if. Leave as None for a baseline result.
    """
    if year < rc.UK_CBAM_START_YEAR:
        return 0.0  # zero-CBAM baseline year for Ningbo-Felixstowe in 2026

    fraction = rc.uk_cbam_rate_fraction(year) if rate_fraction is None else rate_fraction

    if is_unresolved(uk_carbon_price_gbp):
        uk_carbon_price_gbp._fail()

    return embedded_emissions_tco2e * fraction * uk_carbon_price_gbp


def cbam_cost_for_corridor(
    corridor: str,
    embedded_emissions_tco2e: float,
    year: int,
    eu_cert_price_eur: float,
    uk_carbon_price_gbp=None,
    origin_carbon_price_eur_per_tco2e: float = 0.0,
    using_default_values: bool = False,
    uk_rate_fraction=None,
) -> float:
    """Dispatch to the right CBAM regime. Returns cost in the regime's currency."""
    regime = rc.CORRIDOR_REGIME[corridor]
    if regime == "EU":
        return eu_cbam_cost(
            embedded_emissions_tco2e,
            year,
            eu_cert_price_eur,
            origin_carbon_price_eur_per_tco2e,
            using_default_values,
        )
    return uk_cbam_cost(
        embedded_emissions_tco2e, year, uk_carbon_price_gbp, uk_rate_fraction
    )
