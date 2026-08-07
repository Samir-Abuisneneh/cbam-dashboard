"""Scenario matrix definition."""

from . import regulatory_constants as rc

CORRIDORS = list(rc.CORRIDORS)
PRODUCTS = list(rc.PRODUCTS)
YEARS = [2026, 2027, 2028, 2029, 2030]
PRICE_SCENARIOS = list(rc.PRICE_SCENARIOS)

# The proposed UK ETS extension to international voyages could not bite before
# 2028, so the variant only splits the 2028-2030 runs, and only on the UK corridor.
UK_ETS_VARIANTS = ["current_scope", "proposed_expansion"]

# Bunker fuel the vessel burns. Only FuelEU prices bunker choice, and FuelEU
# applies to the EU corridor alone, so this dimension only splits the
# Halifax-Hamburg runs. Sweeping it on the UK corridor would emit duplicate
# rows, since maritime_cost_per_voyage sets bunker_fuel to "n/a" there.
#
# "conventional" is VLSFO and reproduces Gayu's published figures, so it stays
# first and remains the base case. "green_rfnbo" is the ship bunkering its own
# cargo product, which is the comparison the supervisor asked for: it isolates
# what FuelEU compliance costs with and without green bunker fuel. It is not a
# full re-modelling of the voyage, since the vessel's actual CO2 output is held
# constant (see maritime_cost_per_voyage).
BUNKER_FUELS = ["conventional", "green_rfnbo"]


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
