"""Order-of-magnitude cross-check against an external published result.

Ramsook, Boodlal and Maharaj (2025), "Navigating carbon border adjustments: A
case study of Trinidad and Tobago's ammonia exports", European Journal of
Energy Research 5(6). https://doi.org/10.24018/ejenergy.2025.5.6.177

STATUS: NOT YET CALIBRATED. Do not cite the output of this module as a
validation result until the two inputs marked below have been read out of the
paper itself.

Why this is not just a matter of running it
-------------------------------------------
The published headline is that T&T ammonia exports face a CBAM burden of around
22% of export revenue by 2034. Reproducing that number requires three inputs:
the emissions intensity, the carbon price and the revenue base. Only the carbon
price is known here.

Running the check with a plausible-looking ammonia price of EUR 450/t and the
grey SMR intensity of 2.7 tCO2e/t from Part C produces a burden of roughly 98%,
not 22%. That is a factor of four, so something structural differs rather than
a rounding or units issue. Three candidate explanations, in rough order of
likelihood:

  1. Revenue base. T&T ships most of its ammonia to the United States, not the
     EU. If the 22% is expressed against total export revenue while CBAM only
     bites on the EU-bound share, the two figures are simply not measuring the
     same thing, and the model is not wrong.
  2. Emissions intensity. Backing out from a EUR 450/t price, a 22% burden
     implies about 0.6 tCO2e per tonne, which is a blue ammonia figure rather
     than a grey one. T&T has significant gas-based capacity with some carbon
     capture.
  3. Product price. Holding 2.7 tCO2e/t, a 22% burden implies an ammonia price
     above EUR 2,000/t, which is not a defensible number outside the 2022 spike.

Resolving this is worth doing properly. If explanation 1 holds, it is a useful
methodological point for the write-up about how CBAM burden ratios are
reported, and it belongs in the discussion chapter.
"""

from ..model.cbam import eu_cbam_cost

# From Part C of the handoff. Grey ammonia via SMR, 2.5-2.9 tCO2e/t.
ASSUMED_EMISSIONS_TCO2E_PER_TONNE = 2.7

# T&T has no domestic carbon price on ammonia production.
TT_ORIGIN_CARBON_PRICE = 0.0

# NOT SOURCED. Placeholder only. Read the actual figure out of Ramsook et al.
UNSOURCED_AMMONIA_PRICE_EUR_PER_TONNE = 450.0

RAMSOOK_2034_BURDEN_SHARE = 0.22
TOLERANCE_PCT_POINTS = 5.0

CALIBRATED = False  # flip to True only once the two inputs are read from the paper


def run_reference_check(
    ets_price_eur: float = 126.0,
    ammonia_price_eur_per_tonne: float = UNSOURCED_AMMONIA_PRICE_EUR_PER_TONNE,
    emissions_tco2e_per_tonne: float = ASSUMED_EMISSIONS_TCO2E_PER_TONNE,
) -> dict:
    """Compare the modelled 2034 CBAM burden share against Ramsook et al.

    2034 is chosen because the CBAM factor reaches 100% that year, which takes
    the phase-in schedule out of the comparison and leaves only emissions
    intensity, carbon price and product value.

    Returns a dict rather than raising, so the result can be reported honestly
    in the methodology chapter whether or not it agrees.
    """
    cbam_eur_per_tonne = eu_cbam_cost(
        embedded_emissions_tco2e=emissions_tco2e_per_tonne,
        year=2034,
        cert_price_eur=ets_price_eur,
        origin_carbon_price_eur_per_tco2e=TT_ORIGIN_CARBON_PRICE,
        using_default_values=True,
    )
    modelled_share = cbam_eur_per_tonne / ammonia_price_eur_per_tonne
    gap_pct_points = abs(modelled_share - RAMSOOK_2034_BURDEN_SHARE) * 100

    # Invert the calculation so the divergence is diagnosable rather than just
    # a failed assertion.
    implied_price = cbam_eur_per_tonne / RAMSOOK_2034_BURDEN_SHARE
    implied_emissions = (
        RAMSOOK_2034_BURDEN_SHARE * ammonia_price_eur_per_tonne
    ) / (ets_price_eur * 1.30)  # 1.30 is the 2028-onward default value mark-up

    return {
        "calibrated": CALIBRATED,
        "modelled_cbam_eur_per_tonne": cbam_eur_per_tonne,
        "modelled_burden_share": modelled_share,
        "ramsook_burden_share": RAMSOOK_2034_BURDEN_SHARE,
        "gap_pct_points": gap_pct_points,
        "agrees": gap_pct_points <= TOLERANCE_PCT_POINTS,
        "implied_ammonia_price_eur_per_tonne": implied_price,
        "implied_emissions_tco2e_per_tonne": implied_emissions,
        "assumptions": {
            "ets_price_eur_per_tco2e": ets_price_eur,
            "ammonia_price_eur_per_tonne": ammonia_price_eur_per_tonne,
            "ammonia_price_is_sourced": False,
            "emissions_tco2e_per_tonne": emissions_tco2e_per_tonne,
            "year": 2034,
            "cbam_factor": 1.00,
            "default_value_markup_applied": True,
        },
    }


def format_reference_check(result: dict) -> str:
    if not result["calibrated"]:
        header = (
            "Reference case, Ramsook et al. (2025), T&T ammonia 2034\n"
            "  STATUS: NOT CALIBRATED. The ammonia export price below is a\n"
            "  placeholder, not a figure from the paper. Treat the comparison as a\n"
            "  diagnostic, not as validation evidence.\n"
        )
    else:
        header = "Reference case, Ramsook et al. (2025), T&T ammonia 2034\n"

    return (
        f"{header}"
        f"  Modelled CBAM cost:      EUR {result['modelled_cbam_eur_per_tonne']:.2f}/t\n"
        f"  Modelled burden:         {result['modelled_burden_share']:.1%} of export value\n"
        f"  Published burden:        {result['ramsook_burden_share']:.1%}\n"
        f"  Gap:                     {result['gap_pct_points']:.1f} percentage points\n"
        f"\n"
        f"  To reconcile, one of these would have to hold:\n"
        f"    ammonia price of EUR {result['implied_ammonia_price_eur_per_tonne']:,.0f}/t "
        f"(vs EUR {result['assumptions']['ammonia_price_eur_per_tonne']:,.0f} assumed), or\n"
        f"    emissions of {result['implied_emissions_tco2e_per_tonne']:.2f} tCO2e/t "
        f"(vs {result['assumptions']['emissions_tco2e_per_tonne']:.2f} assumed), or\n"
        f"    the published 22% is measured against total export revenue while CBAM\n"
        f"    applies only to the EU-bound share.\n"
        f"\n"
        f"  Next step: read the emissions intensity, ammonia price and revenue base\n"
        f"  out of Ramsook et al. directly, set CALIBRATED = True, and re-run.\n"
    )
