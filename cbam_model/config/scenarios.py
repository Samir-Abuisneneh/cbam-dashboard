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

# Display labels for the three UK carbon price paths, one per entry in
# `rc.UK_ETS_PRICE_VARIANTS`.
#
# These live here rather than in the dashboard because a scenario label is not
# decoration, it is the only thing telling a reader which of three price paths
# a number came from, and two of the three are explicitly not law. Keeping them
# beside the variants they name is what lets
# `test_every_uk_price_variant_has_its_own_label` check the two lists agree.
#
# THE BUG THIS EXISTS TO PREVENT, which is not hypothetical. The dashboard used
# to build this selector by branching `if v == "frozen" ... else <linkage
# label>`. When "desnz" was added on 6 August 2026 it fell into the else arm,
# so DESNZ prices were displayed on screen captioned as the EU-UK linkage
# scenario, and the caption below the selector claimed the price was held flat
# at the 2026 determination when it was not. Both statements were false about
# the numbers actually on the page.
UK_PRICE_VARIANT_LABELS = {
    "frozen": "Frozen at the 2026 determination (baseline)",
    "linked": "EU-UK ETS linkage: converges to EU price (NOT law)",
    "desnz": "DESNZ traded carbon values (official, real 2025 prices)",
}
