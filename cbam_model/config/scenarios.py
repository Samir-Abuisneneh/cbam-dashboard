"""Scenario matrix definition."""

from . import regulatory_constants as rc

CORRIDORS = list(rc.CORRIDORS)
PRODUCTS = list(rc.PRODUCTS)
YEARS = [2026, 2027, 2028, 2029, 2030]
PRICE_SCENARIOS = list(rc.PRICE_SCENARIOS)

# The proposed UK ETS extension to international voyages could not bite before
# 2028, so the variant only splits the 2028-2030 runs, and only on the UK corridor.
UK_ETS_VARIANTS = ["current_scope", "proposed_expansion"]


def enumerate_cases():
    """Yield (corridor, product, year, price_scenario, uk_ets_variant) tuples.

    The UK ETS variant is only meaningful for the UK corridor from 2028 onward.
    Every other case is fixed to "current_scope" so the matrix does not double
    up on identical runs.
    """
    for corridor in CORRIDORS:
        for product in PRODUCTS:
            for year in YEARS:
                for price_scenario in PRICE_SCENARIOS:
                    is_uk = rc.CORRIDOR_REGIME[corridor] == "UK"
                    splits_on_variant = (
                        is_uk and year >= rc.UK_ETS_INTL_EXPANSION_EARLIEST_YEAR
                    )
                    variants = UK_ETS_VARIANTS if splits_on_variant else ["current_scope"]
                    for variant in variants:
                        yield corridor, product, year, price_scenario, variant


# Scenario labels for the write-up. The proposed-expansion runs are policy
# uncertain and must be captioned as such wherever they appear in the results
# chapter.
VARIANT_LABELS = {
    "current_scope": "UK ETS as currently legislated (in-port emissions only)",
    "proposed_expansion": (
        "UK ETS with proposed 50% international voyage coverage "
        "(NOT LAW: consultation closed Jan 2026, no legislative decision)"
    ),
}
