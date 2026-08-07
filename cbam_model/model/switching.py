"""Corridor switching economics under asset specificity.

WHY THIS MODULE EXISTS
----------------------
Everything else in this model answers "what does it cost this year". That is a
spot comparison, and a spot comparison implicitly assumes a firm can move
between corridors costlessly and instantly. It cannot.

Under Transaction Cost Economics (Williamson), the barrier is asset
specificity: the investments that make a corridor usable are largely
non-redeployable. Route concessions and transport rights, port access and
berthing arrangements, insurance cover written against a named route, and
fixed shore infrastructure such as terminals and pipelines are all specific to
the corridor they were built for. They cannot be lifted and moved when the
regulatory arithmetic changes. Offtake in this trade is contracted over long
horizons, on the order of a decade, precisely because nobody finances
specific assets against a one-year commitment.

The consequence is that the cost ranking in `corridor_cost_comparison` is not
by itself a decision rule. A firm choosing a corridor is buying the whole
remaining tenor of that corridor's cost path, not this year's price.

WHAT THIS MODULE DOES NOT KNOW
------------------------------
The magnitude of the switching cost. No source for it exists in this study and
none is claimed. That is deliberate, and it is why the primary output is a
**breakeven threshold** rather than a verdict: the model reports the largest
corridor-specific sunk cost at which switching would still pay, and the
write-up argues about whether real switching costs plausibly sit above or below
that line. A threshold is a defensible finding without a sourced cost figure.
A point estimate would not be.

UNITS, AND THIS IS THE EASIEST THING HERE TO GET WRONG
------------------------------------------------------
Compliance costs arrive as GBP per tonne of product, per year. Discounting a
stream of those gives a present value in GBP per tonne of *annual* volume, not
GBP per tonne shipped. A switching cost is a one-off capital sum in GBP, so to
compare it against that present value it has to be divided by the contracted
annual volume in tonnes first.

Every threshold this module returns is therefore named
`..._gbp_per_tonne_annual_volume` and means: the sunk cost of switching,
divided by annual contracted tonnage. Comparing a raw capital sum against these
figures overstates the switching barrier by whatever the annual tonnage is,
which for a gas carrier trade is three to four orders of magnitude.
"""

# Real discount rate. 8% is the conventional mid-point for energy
# infrastructure appraisal and is used here as a parameter to be swept, not as
# a sourced figure for this trade. `corridor_lock_in` reports the rate it used
# in an output column so no result is ever read without it.
DEFAULT_DISCOUNT_RATE = 0.08

# Contract tenor in years. Frano's framing in the 6 August 2026 supervisory
# meeting: these are large commitments and nobody underwrites specific assets
# against a one-year deal, so think in terms of roughly a decade.
DEFAULT_CONTRACT_TENOR_YEARS = 10

# How to treat tenor years that run past the end of the modelled horizon.
#
# The model runs 2026-2030. A ten-year tenor struck in 2026 runs to 2035, so
# five of its years have no modelled cost. Neither treatment is free of
# assumption and they err in opposite directions, so both are reported:
#
#   "truncate"   Evaluate only the years the model actually covers. Makes no
#                claim about the future and is the default for that reason. It
#                understates tenor, so it understates the cost of being locked
#                into the wrong corridor.
#
#   "hold_final" Hold the final modelled year's cost flat across the remaining
#                tenor. NOT NEUTRAL, and the direction has to be stated
#                wherever it is used: the EU-UK gap is *narrowing* across
#                2027-2030 as the UK CBAM rate fraction climbs toward the EU
#                CBAM factor, so freezing the 2030 gap projects a persistent EU
#                advantage that the modelled trend is actively eroding. It
#                flatters the EU corridor.
#
# The EU CBAM factor is also still ramping after 2030 (0.485 in 2030 to 1.00 in
# 2034), which neither treatment captures. Both are therefore conservative
# about absolute cost levels and differ only in what they assume about the gap.
BEYOND_HORIZON_METHODS = ("truncate", "hold_final")


def discount_factors(n_years: int, discount_rate: float = DEFAULT_DISCOUNT_RATE):
    """Discount factors for years 0..n_years-1, decision year discounted at t=0.

    The decision year is undiscounted because the commitment is made at the
    start of it. Shifting to t=1 would scale every result by 1/(1+r) uniformly
    and change no ranking, but it would make the breakeven thresholds
    incomparable with a capital cost incurred at signature.
    """
    if n_years < 0:
        raise ValueError(f"n_years must be non-negative, got {n_years}")
    if discount_rate <= -1:
        raise ValueError(f"discount_rate must exceed -1, got {discount_rate}")
    return [1.0 / ((1.0 + discount_rate) ** t) for t in range(n_years)]


def present_value(annual_values, discount_rate: float = DEFAULT_DISCOUNT_RATE) -> float:
    """Present value of a stream of annual values, first value undiscounted."""
    values = list(annual_values)
    return sum(v * f for v, f in zip(values, discount_factors(len(values), discount_rate), strict=False))


def extend_to_tenor(
    annual_values,
    tenor_years: int = DEFAULT_CONTRACT_TENOR_YEARS,
    beyond_horizon: str = "truncate",
):
    """Stretch or clip a modelled cost series to the contract tenor.

    See `BEYOND_HORIZON_METHODS` for what each method assumes and which way it
    errs. Returns the series actually used, so callers can report its length
    rather than the nominal tenor.
    """
    if beyond_horizon not in BEYOND_HORIZON_METHODS:
        raise ValueError(
            f"Unknown beyond_horizon method {beyond_horizon!r}. "
            f"Expected one of {BEYOND_HORIZON_METHODS}."
        )
    values = list(annual_values)
    if not values:
        return []
    if tenor_years <= len(values):
        return values[:tenor_years]
    if beyond_horizon == "truncate":
        return values
    return values + [values[-1]] * (tenor_years - len(values))


def committed_present_cost(
    annual_costs,
    tenor_years: int = DEFAULT_CONTRACT_TENOR_YEARS,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    beyond_horizon: str = "truncate",
) -> float:
    """Present value of committing to one corridor's cost path for the tenor.

    This is the quantity a firm actually chooses between when asset specificity
    forbids a costless exit, and it is what makes the decision differ from the
    single-year ranking.
    """
    used = extend_to_tenor(annual_costs, tenor_years, beyond_horizon)
    return present_value(used, discount_rate)


def breakeven_switching_cost(
    incumbent_annual_costs,
    alternative_annual_costs,
    tenor_years: int = DEFAULT_CONTRACT_TENOR_YEARS,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    beyond_horizon: str = "truncate",
) -> float:
    """Largest sunk switching cost at which moving corridor still pays.

    Returns GBP per tonne of annual contracted volume, floored at zero. See the
    units note in the module docstring: this is not GBP per tonne shipped.

    A zero means the alternative is not cheaper over the tenor at all, so no
    switching cost however small would justify the move. That is a different
    statement from "the switch is marginal", and the two must not be conflated
    in the write-up.
    """
    incumbent = committed_present_cost(
        incumbent_annual_costs, tenor_years, discount_rate, beyond_horizon
    )
    alternative = committed_present_cost(
        alternative_annual_costs, tenor_years, discount_rate, beyond_horizon
    )
    return max(0.0, incumbent - alternative)


def switch_verdict(
    breakeven_gbp_per_tonne_annual_volume: float,
    switching_cost_gbp_per_tonne_annual_volume: float,
    marginal_band: float = 0.10,
) -> str:
    """Three-state verdict on whether a corridor switch is justified.

    Mirrors the three-state banding `analysis.outputs._abatement_verdict`
    already uses, and for the same reason: this project has a documented case
    of a bare boolean reporting "justified" on a 1% margin. A verdict inside
    the band is reported as marginal, not as a decision.
    """
    if breakeven_gbp_per_tonne_annual_volume <= 0:
        return "never_justified"
    if switching_cost_gbp_per_tonne_annual_volume <= 0:
        return "justified"

    margin = (
        breakeven_gbp_per_tonne_annual_volume
        - switching_cost_gbp_per_tonne_annual_volume
    ) / switching_cost_gbp_per_tonne_annual_volume

    if abs(margin) <= marginal_band:
        return "marginal"
    return "justified" if margin > 0 else "locked_in"
