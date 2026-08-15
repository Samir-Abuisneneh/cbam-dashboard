"""CBAM cost functions for both regimes.

All costs are returned in the currency of the price argument passed in: EUR for
the EU functions, GBP for the UK function. Conversion happens once, in
`total_cost.py`.
"""


from ..config import regulatory_constants as rc
from ..config.unresolved import is_unresolved

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


def apply_default_value_markup(
    embedded_emissions_tco2e: float, year: int, product: str
) -> float:
    """Apply the IR 2025/2621 mark-up to default embedded emissions values.

    Only applies where the declarant is using regulatory default values rather
    than verified actual emissions data. Do not apply to verified actuals.

    `product` selects the mark-up schedule: fertiliser goods carry a flat 1%,
    everything else ramps 10/20/30. See
    `regulatory_constants.default_value_markup`.
    """
    return embedded_emissions_tco2e * (1 + rc.default_value_markup(year, product))


def eu_cbam_cost(
    embedded_emissions_tco2e: float,
    year: int,
    cert_price_eur: float,
    origin_carbon_price_eur_per_tco2e: float = 0.0,
    using_default_values: bool = False,
    mechanism: str | None = None,
    benchmark_tco2e_per_tonne: float | None = None,
    product: str | None = None,
) -> float:
    """EU CBAM certificate cost in EUR for one shipment.

    Args:
        embedded_emissions_tco2e: Embedded emissions of the shipment, tCO2e.
        year: Import year, which selects the CBAM factor.
        cert_price_eur: Certificate price, EUR/tCO2e.
        origin_carbon_price_eur_per_tco2e: Carbon price effectively paid in the
            country of origin, EUR/tCO2e. Zero if none.
        using_default_values: If True, the IR 2025/2621 mark-up is applied.
            `product` is then required, because the mark-up schedule differs
            between fertiliser goods and everything else.
        product: "ammonia", "hydrogen", etc. Required when
            `using_default_values` is True.
        mechanism: How free allocation is netted off. See
            `regulatory_constants.EU_CBAM_MECHANISMS`. Defaults to
            `EU_CBAM_DEFAULT_MECHANISM`.
        benchmark_tco2e_per_tonne: CBAM benchmark from IR 2025/2620 Annex
            point 5. Required by, and only used by, the "benchmark_shielded"
            mechanism. NOT the EU ETS product benchmark: the two coincide for
            ammonia and differ by 56.8% for hydrogen. Pass
            `regulatory_constants.cbam_benchmark(product)`.

    UNIT WARNING on the benchmark mechanism. The benchmark is defined per tonne
    of product, so it can only be netted off `embedded_emissions_tco2e` when
    that argument is itself expressed per tonne of product. Every caller in
    this model passes it that way, but a caller passing whole-shipment
    emissions would get a benchmark netted off a shipment-scale figure and a
    silently near-zero deduction. There is no way to detect that from inside
    this function, so it is the caller's contract to honour.

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

    mechanism = rc.EU_CBAM_DEFAULT_MECHANISM if mechanism is None else mechanism
    if mechanism not in rc.EU_CBAM_MECHANISMS:
        raise ValueError(
            f"Unknown EU CBAM mechanism {mechanism!r}. "
            f"Expected one of {rc.EU_CBAM_MECHANISMS}."
        )

    emissions = embedded_emissions_tco2e
    if using_default_values:
        if product is None:
            raise ValueError(
                "using_default_values=True requires product, because the "
                "IR 2025/2621 mark-up is 1% flat for fertiliser goods and "
                "10/20/30 for everything else. Defaulting it would silently "
                "overstate ammonia by up to 28.7%."
            )
        emissions = apply_default_value_markup(emissions, year, product)

    factor = rc.cbam_factor(year)

    if mechanism == "factor_scaled":
        chargeable_tco2e = emissions * factor
    else:
        if benchmark_tco2e_per_tonne is None:
            raise ValueError(
                "The benchmark_shielded mechanism requires "
                "benchmark_tco2e_per_tonne. Pass "
                "regulatory_constants.cbam_benchmark(product), and read "
                "the unit warning in this function's docstring first."
            )
        # IR 2025/2620, Annex Equations 1 and 6:
        #     FAA  = SEFA x M,  SEFA = CBAM_y x CSCF_y x BM
        # CBAM_y is the Article 10a(1a) factor, the share of free allocation
        # still remaining, which is 1 - cbam_factor(year) in this model's terms.
        # Certificates are due on full embedded emissions net of that
        # adjustment. Floors at zero: recital 16 confirms the adjustment may
        # exceed embedded emissions, leaving no certificates due, and never
        # produces a credit.
        free_allocation_share = 1.0 - factor
        chargeable_tco2e = max(
            0.0,
            emissions
            - benchmark_tco2e_per_tonne * free_allocation_share * rc.cbam_cscf(year),
        )

    net_price = cert_price_eur - origin_carbon_price_eur_per_tco2e
    return max(0.0, chargeable_tco2e * net_price)


def uk_cbam_cost(
    embedded_emissions_tco2e: float,
    year: int,
    uk_carbon_price_gbp: float,
    rate_fraction=None,
    origin_carbon_price_gbp_per_tco2e: float = 0.0,
) -> float:
    """UK CBAM liability in GBP for one shipment.

    The UK scheme is a tax rather than a certificate-surrender system, and in
    year one it uses a single flat default value per CN code with no
    country differentiation.

    THE DEFAULT VALUE THIS MODEL FEEDS IN IS A STAND-IN, AND THE UK CORRIDOR'S
    `cbam_default` RESULTS INHERIT THAT.

    UK CBAM defaults are a single global average per CN code, weighted by the
    production volumes of the UK's main trading partners. The government
    considered jurisdiction-specific values and rejected them as "deemed
    infeasible by 2027". HMRC has committed to publishing the figures before
    the regime starts and, as of 15 August 2026, has not: ammonia-specific
    values are expected late 2026, after this study is submitted.

    So there is no correct number to use. The emissions table supplies the EU's
    China-specific IR 2025/2621 default (4.36 tCO2e/t for ammonia) on the
    Ningbo-Felixstowe corridor instead. That is not what UK law specifies.

    The direction of the resulting error is inferable even though its size is
    not. A global average is diluted by cleaner origins, so it sits below a
    value set specifically for a high-intensity exporter. Substituting China's
    own EU default therefore most likely OVERSTATES UK CBAM liability on this
    corridor rather than understating it. That is the opposite of the direction
    a reader might assume, which is why it is written down here.

    This is also the mechanism the Centre for Inclusive Trade Policy quantifies:
    using global averages rather than country-specific defaults understated
    emissions from high-intensity origins by 1.48 MtCO2e across four sectors in
    2023, around GBP 1.62bn. The study should cite that finding rather than
    present the observation as its own.

    Liability = embedded_emissions x rate_fraction x (UK ETS price - origin
    carbon price), where rate_fraction = 1 - (baseline free allocation % x
    Article 16(14) factor) per the draft CBAM (Calculation of CBAM Rate and
    Determination of Carbon Price Relief) Regulations 2026 and Finance Act
    2026 s.149(4). See `regulatory_constants.uk_cbam_rate_fraction` for the
    full derivation.

    Args:
        rate_fraction: Overrides the real computed rate_fraction for a
            clearly labelled what-if. Leave as None for a baseline result.
        origin_carbon_price_gbp_per_tco2e: Carbon price effectively paid in the
            country of origin, GBP/tCO2e. Added 4 August 2026. It is zero for
            every case this study currently runs, because China's national ETS
            covers power, steel, cement and aluminium and has not yet been
            extended to chemicals, so neither hydrogen nor ammonia production
            is priced there. The parameter exists because the relief is real
            in law - carbon price relief is named in the title of the
            Regulations above - and because China's ETS expansion into
            chemicals is documented as planned. Without it the model could not
            represent that change at all.

            Note the unit: GBP, not EUR. The UK regime works in GBP throughout
            and the emissions table stores origin prices in EUR, so callers
            must convert. `total_cost.cbam_cost_per_tonne` does this via
            `rc.eur_to_gbp`. Passing a EUR figure here would silently overstate
            the relief by about 17%.

            Enters on the same basis as the liability it offsets, exactly as in
            `eu_cbam_cost`, and the result floors at zero.
    """
    if year < rc.UK_CBAM_START_YEAR:
        return 0.0  # zero-CBAM baseline year for Ningbo-Felixstowe in 2026

    fraction = rc.uk_cbam_rate_fraction(year) if rate_fraction is None else rate_fraction

    if is_unresolved(uk_carbon_price_gbp):
        uk_carbon_price_gbp._fail()

    net_price = uk_carbon_price_gbp - origin_carbon_price_gbp_per_tco2e
    return max(0.0, embedded_emissions_tco2e * fraction * net_price)


def cbam_cost_for_corridor(
    corridor: str,
    embedded_emissions_tco2e: float,
    year: int,
    eu_cert_price_eur: float,
    uk_carbon_price_gbp=None,
    origin_carbon_price_eur_per_tco2e: float = 0.0,
    using_default_values: bool = False,
    uk_rate_fraction=None,
    cbam_mechanism: str | None = None,
    benchmark_tco2e_per_tonne: float | None = None,
    product: str | None = None,
) -> float:
    """Dispatch to the right CBAM regime. Returns cost in the regime's currency.

    `cbam_mechanism` and `benchmark_tco2e_per_tonne` apply to the EU regime
    only. The UK scheme's rate fraction already nets off free allocation
    directly (see `uk_cbam_rate_fraction`), so it has no equivalent choice.
    """
    regime = rc.CORRIDOR_REGIME[corridor]
    if regime == "EU":
        return eu_cbam_cost(
            embedded_emissions_tco2e,
            year,
            eu_cert_price_eur,
            origin_carbon_price_eur_per_tco2e,
            using_default_values,
            cbam_mechanism,
            benchmark_tco2e_per_tonne,
            product,
        )
    return uk_cbam_cost(
        embedded_emissions_tco2e,
        year,
        uk_carbon_price_gbp,
        uk_rate_fraction,
        # The caller's origin price is in EUR; the UK regime works in GBP.
        rc.eur_to_gbp(origin_carbon_price_eur_per_tco2e),
    )
