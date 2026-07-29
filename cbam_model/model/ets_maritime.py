"""Maritime ETS cost functions for both regimes.

The asymmetry between these two functions is the point of the study. The EU
charges half of an extra-EEA voyage's emissions. The UK charges none of the
voyage and all of the time in port.
"""

from ..config import regulatory_constants as rc
from ..config.unresolved import is_unresolved


def eu_ets_maritime_cost(
    voyage_co2_t: float,
    year: int,
    ets_price_eur: float,
    coverage_fraction: float = rc.EU_ETS_EXTRA_EEA_COVERAGE,
    port_in_port_emissions_t: float = 0.0,
) -> float:
    """EU ETS maritime cost in EUR.

    Args:
        voyage_co2_t: Total voyage emissions, tCO2, before any coverage
            fraction is applied.
        year: Selects the phase-in fraction. 100% from 2026 onward.
        coverage_fraction: 0.50 for voyages to or from a port outside the EEA,
            1.00 for intra-EEA voyages. Halifax-Hamburg is extra-EEA, so 0.50.
        port_in_port_emissions_t: Emissions at berth in the EU port. These fall
            under the intra-EEA 100% coverage rather than the 50% voyage rate,
            so they are charged separately at full coverage.
    """
    phase_in = rc.eu_ets_maritime_phase_in(year)
    voyage = voyage_co2_t * coverage_fraction * phase_in
    at_berth = port_in_port_emissions_t * rc.EU_ETS_INTRA_EEA_COVERAGE * phase_in
    return (voyage + at_berth) * ets_price_eur


def uk_ets_maritime_cost(
    port_in_port_emissions_t: float,
    year: int,
    uk_ets_price_gbp,
    voyage_co2_t: float = 0.0,
    include_intl_expansion: bool = False,
    first_period_fraction_2026: float = 1.0,
) -> float:
    """UK ETS maritime cost in GBP.

    Scope, re-verified against the Environment Agency guidance of 22 June 2026
    plus six corroborating sources after two earlier drafts of this project got
    it wrong:

      - UK port to UK port voyages: 100% covered. Not applicable here, both
        modelled corridors are international.
      - Emissions while physically in a UK port, meaning berth, hotelling and
        in-port movements: 100% covered, regardless of where the ship arrived
        from.
      - The international ocean voyage leg: 0% covered.

    So for Ningbo-Felixstowe the ocean crossing contributes nothing, and the
    only UK ETS cost is Felixstowe berth time.

    Args:
        include_intl_expansion: Applies the PROPOSED 50% coverage of
            international voyages. The consultation closed in January 2026 with
            no legislative decision, so this is not law. Only ever set True
            inside a scenario explicitly labelled as policy-uncertain, and never
            for a baseline result.
        first_period_fraction_2026: The first UK ETS compliance period is six
            months, 1 July to 31 December 2026. Defaults to 1.0 because the
            functional unit here is a single voyage, and a single voyage either
            falls inside the compliance period or outside it rather than being
            half liable. Set to 0.5 only when scaling to a full calendar year of
            evenly distributed sailings, which is a modelling assumption rather
            than a regulatory value.
    """
    if is_unresolved(uk_ets_price_gbp):
        uk_ets_price_gbp._fail()

    if year < 2026:
        return 0.0

    chargeable_t = port_in_port_emissions_t * rc.UK_ETS_IN_PORT_COVERAGE

    if include_intl_expansion:
        if year < rc.UK_ETS_INTL_EXPANSION_EARLIEST_YEAR:
            raise ValueError(
                f"The proposed UK ETS international extension could not apply before "
                f"{rc.UK_ETS_INTL_EXPANSION_EARLIEST_YEAR}, but year={year} was given."
            )
        chargeable_t += voyage_co2_t * rc.UK_ETS_INTL_EXPANSION_PROPOSED
    else:
        chargeable_t += voyage_co2_t * rc.UK_ETS_INTL_VOYAGE_COVERAGE  # zero, kept
        # explicit so the
        # scope choice is
        # visible in the code

    cost = chargeable_t * uk_ets_price_gbp

    if year == 2026:
        cost *= first_period_fraction_2026

    return cost
