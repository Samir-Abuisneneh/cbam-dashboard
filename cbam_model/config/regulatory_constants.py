"""Law-derived constants for the corridor cost model.

Every value carries its source. Values that are still genuinely unsourced use
the `Unresolved` sentinel from `unresolved.py` and raise if used; none currently
do, as of 1 August 2026.

Corridors:
    halifax_hamburg    Canada to Germany. EU CBAM, EU ETS Maritime, FuelEU.
    ningbo_felixstowe  China to UK. UK CBAM (from 2027), UK ETS Maritime. No FuelEU.
"""

HALIFAX_HAMBURG = "halifax_hamburg"
NINGBO_FELIXSTOWE = "ningbo_felixstowe"
CORRIDORS = (HALIFAX_HAMBURG, NINGBO_FELIXSTOWE)

PRODUCTS = ("hydrogen", "ammonia")

# Corridor to regulatory regime. Drives which cost terms apply.
CORRIDOR_REGIME = {
    HALIFAX_HAMBURG: "EU",
    NINGBO_FELIXSTOWE: "UK",
}


# ---------------------------------------------------------------------------
# EU CBAM
# ---------------------------------------------------------------------------

# Share of embedded emissions that generates a certificate obligation.
#
# WARNING: this is NOT the free allocation share. Free allocation is the
# inverse (97.5% protected in 2026, falling to 0% in 2034). Confusing the two
# inverts the entire result and has been caught twice in this project.
# Source: Regulation (EU) 2023/956, free-allocation phase-out schedule.
CBAM_FACTOR = {
    2026: 0.025,
    2027: 0.05,
    2028: 0.10,
    2029: 0.225,
    2030: 0.485,
    2031: 0.61,
    2032: 0.735,
    2033: 0.86,
    2034: 1.00,
}

# Mark-up applied to default embedded emissions values, to incentivise use of
# verified actual data over defaults.
# Source: Implementing Regulation (EU) 2025/2621, which also sets the
# country-specific and production-route-specific default values for hydrogen
# (CN 2804 10 00) and ammonia.
DEFAULT_VALUE_MARKUP = {2026: 0.10, 2027: 0.20, 2028: 0.30}  # 0.30 applies 2028 onward

# Certificate price mechanism.
# Source: Implementing Regulation (EU) 2025/2548. NOTE: this is a different
# regulation from 2025/2621 above. 2621 sets default values, 2548 sets price.
# Miscited once earlier in this project.
#
# The model does not feed this Q1 print into eu_cbam_cost() directly. Article
# 21 pegs the CBAM certificate price to the EU ETS average over the averaging
# window above, so it should track the EU_ETS_PRICE_SCENARIOS_BY_YEAR figures
# rather than needing its own separate cost path - eu_cbam_cost() is called
# with the EU ETS price precisely because the two are meant to move together.
# This constant instead exists as a real-world anchor: see
# cbam_cert_price_within_ets_scenario_bounds() below, which checks the 2026
# scenario range still brackets it. If that check ever fails, the scenario
# bounds have drifted from the actual market and need revisiting.
CBAM_CERT_PRICE_AVERAGING = {2026: "quarterly", 2027: "weekly"}  # weekly from 2027 onward
CBAM_CERT_PRICE_Q1_2026_ACTUAL = 75.36  # EUR/tCO2e, confirmed published figure (EEX)

# EU ETS product benchmarks, tCO2e per tonne of product.
#
# SOURCED 4 August 2026 from Commission Implementing Regulation (EU) 2021/447,
# Annex, section 2 (product benchmarks accounting for fuel and electricity
# exchangeability). Note the regulation prints these with a decimal comma, so
# "1,570" is 1.570 and "6,84" is 6.84.
#
# These are NOT the CBAM default embedded emissions values. Those are a
# different thing in a different regulation (IR 2025/2621) and are already held
# per country in the emissions table as the `cbam_default` pathway. A benchmark
# is what an EU installation's free allocation is calculated against; a default
# value is what an importer must use absent verified actual emissions data.
# Conflating them is easy and would be a material error.
#
# Independent confirmation that these are the right figures: Ramsook et al.
# (2025) quote the EU ammonia benchmark as 1.57 tCO2/tNH3, matching 1.570 here
# exactly. See validation/reference_case.py.
#
# CAVEAT: these are the 2021-2025 values. The Commission adopted revised
# benchmarks for 2026-2030 on 29 June 2026, cutting free allocation by more
# than 16% on average, with ammonia and hydrogen explicitly among the sectors
# revised. The 2026-2030 figures have NOT been read out yet. Use these to size
# the effect, not to produce a final result.
EU_ETS_PRODUCT_BENCHMARK_TCO2E_PER_TONNE = {"hydrogen": 6.84, "ammonia": 1.570}
EU_ETS_PRODUCT_BENCHMARK_PERIOD = "2021-2025"
EU_ETS_PRODUCT_BENCHMARK_SOURCE = "Commission Implementing Regulation (EU) 2021/447, Annex"

# Hydrogen has no de minimis mass exemption. Every shipment is in scope.
EU_CBAM_HYDROGEN_DE_MINIMIS_EXEMPTION = False

# First annual declaration and certificate surrender for 2026 imports.
EU_CBAM_FIRST_SURRENDER_DEADLINE = "2027-09-30"


# ---------------------------------------------------------------------------
# UK CBAM
# ---------------------------------------------------------------------------
# Source: UK Government CBAM policy summary (HMRC).

UK_CBAM_START_YEAR = 2027  # Ningbo-Felixstowe carries zero CBAM liability in 2026
UK_CBAM_COUNTRY_DIFFERENTIATED_DEFAULTS = False  # single flat default per CN code, year 1
UK_CBAM_VALUE_THRESHOLD_GBP = 50_000  # value threshold, not the EU's 50-tonne mass threshold
UK_CBAM_INDIRECT_EMISSIONS_INCLUDED_FROM = 2029  # at the earliest
UK_CBAM_IS_TAX_NOT_CERTIFICATES = True  # structural difference from the EU scheme
UK_CBAM_FIRST_PAYMENT_DEADLINE = "2028-05-31"  # for the 2027 accounting period

# RESOLVED 31 July 2026. There is no flat "UK CBAM rate" - it is a formula,
# from the draft Carbon Border Adjustment Mechanism (Calculation of CBAM Rate
# and Determination of Carbon Price Relief) Regulations 2026:
#
#   UK CBAM rate = UK ETS price x (1 - baseline free allocation % x
#                                       Article 16(14) factor)
#
# The design intent (Analytical Annex: Free Allocation for CBAM Sectors): the
# import charge is pegged to what a UK domestic producer in the same CBAM
# sector effectively pays after their own free allowances, not the full UK
# ETS price. As UK domestic free allocation shrinks over 2027-2030, the
# import rate rises correspondingly.
#
# The baseline free allocation percentage is legally defined (Finance Act
# 2026, s.149(4)) as the average across three scheme years: 2019 under the EU
# ETS (pre-Brexit), plus 2022 and 2023 under the UK ETS. Hydrogen is one of
# five UK CBAM sectors, with the UK's only in-scope installation being
# Teesside Hydrogen Plant (BOC Limited).
#
#   2019 (EU ETS): Union Registry Public Website bulk export ("Operators
#   Yearly Activity Daily", union-registry-data.ec.europa.eu), installation
#   ID 201961, retrieved 31 July 2026. This is the Commission's own
#   installation-level data, not the EEA's aggregated country+sector+year
#   "data viewer" product, which cannot isolate a single installation.
#
#   2022 and 2023 (UK ETS): Analytical Annex Table 4, sourced to the UK ETS
#   Registry Compliance Report.
UK_CBAM_BASELINE_YEARS = {
    2019: {"emissions_tco2e": 221_554, "free_allocation": 200_228},
    2022: {"emissions_tco2e": 170_000, "free_allocation": 160_000},
    2023: {"emissions_tco2e": 160_000, "free_allocation": 120_000},
}
UK_CBAM_BASELINE_FREE_ALLOCATION_PCT = sum(
    v["free_allocation"] / v["emissions_tco2e"] for v in UK_CBAM_BASELINE_YEARS.values()
) / len(UK_CBAM_BASELINE_YEARS)  # 0.8649

# Article 16(14) factor, inserted into the UK's retained version of
# Commission Delegated Regulation (EU) 2019/331 by The Greenhouse Gas
# Emissions Trading Scheme (Amendment) Order 2026. Multiplies the CBAM
# sector's free allocation (new Article 16(2a)), not the CBAM rate directly.
# Current-law defaults - the UK ETS Authority can change these via secondary
# legislation for any given scheme year.
UK_CBAM_ARTICLE_16_14_FACTOR = {2027: 0.975, 2028: 0.95, 2029: 0.9, 2030: 0.775}


def uk_cbam_rate_fraction(year: int) -> float:
    """Fraction of the UK ETS price charged as the UK CBAM rate.

    rate_fraction = 1 - (baseline free allocation % x Article 16(14) factor).
    Raises for years with no confirmed Article 16(14) factor rather than
    extrapolating - these are current-law defaults, not a smooth curve.
    """
    if year not in UK_CBAM_ARTICLE_16_14_FACTOR:
        raise ValueError(
            f"No confirmed Article 16(14) factor for {year}. Defined for "
            f"{sorted(UK_CBAM_ARTICLE_16_14_FACTOR)} only."
        )
    factor = UK_CBAM_ARTICLE_16_14_FACTOR[year]
    return 1 - (UK_CBAM_BASELINE_FREE_ALLOCATION_PCT * factor)


# ---------------------------------------------------------------------------
# EU ETS Maritime
# ---------------------------------------------------------------------------
# Source: EMSA EU ETS Maritime Extension Overview; European Commission FAQ on
# maritime transport in the EU ETS. Confirmed against two independent EU sources.

EU_ETS_MARITIME_PHASE_IN = {2024: 0.40, 2025: 0.70, 2026: 1.00}  # 1.00 from 2026 onward
EU_ETS_INTRA_EEA_COVERAGE = 1.00  # voyages between two EU/EEA ports
EU_ETS_EXTRA_EEA_COVERAGE = 0.50  # voyages to or from a port outside the EEA

# Halifax-Hamburg's EU leg is extra-EEA, so 50% coverage applies.
EU_ETS_CORRIDOR_COVERAGE = {HALIFAX_HAMBURG: EU_ETS_EXTRA_EEA_COVERAGE}


# ---------------------------------------------------------------------------
# UK ETS Maritime
# ---------------------------------------------------------------------------
# HIGHEST ERROR RISK IN THE MODEL. This was wrong in two earlier drafts, which
# assumed EU-equivalent 50% coverage of the international voyage. It is not.
# Re-verified against the Environment Agency guidance plus ICCT, DNV, Lloyd's
# Register and ICAP commentary (7 sources total).
#
# Source: UK Government / Environment Agency, "UK Emissions Trading Scheme for
# Maritime: How to Comply", published 22 June 2026.

UK_ETS_START_DATE = "2026-07-01"  # first compliance period is 6 months, Jul-Dec 2026
UK_ETS_DOMESTIC_VOYAGE_COVERAGE = 1.00  # UK port to UK port only
UK_ETS_INTL_VOYAGE_COVERAGE = 0.00  # the international ocean leg is NOT covered
UK_ETS_IN_PORT_COVERAGE = 1.00  # 100% of berth, hotelling and in-port movement
# emissions, regardless of whether the ship
# arrived from a UK or a non-UK port

# PROPOSED extension to 50% of international voyages from 2028. The consultation
# closed January 2026 with no legislative decision. This is not law. It may only
# ever appear in the model as an explicitly labelled scenario.
UK_ETS_INTL_EXPANSION_PROPOSED = 0.50
UK_ETS_INTL_EXPANSION_IS_LAW = False
UK_ETS_INTL_EXPANSION_EARLIEST_YEAR = 2028


# ---------------------------------------------------------------------------
# FuelEU Maritime
# ---------------------------------------------------------------------------
# Source: Regulation (EU) 2023/1805, Annex II, Annex IV and Article 5.
# Applies to the Halifax-Hamburg corridor only. Felixstowe sits outside EU
# jurisdiction, so Ningbo-Felixstowe carries no FuelEU cost. That asymmetry is a
# real cost difference between the corridors, not a gap in the model.

FUELEU_BASELINE_2020 = 91.16  # gCO2e/MJ, well-to-wake

# Article 4(2) reduction steps applied to the 2020 baseline. The build spec only
# carried the 2025-2029 step, but the scenario matrix runs 2030, so the later
# steps are added here. Targets are computed from the baseline rather than typed
# in, which is why the 2025 figure reads 89.3368 rather than the rounded 89.34
# quoted in most secondary sources.
FUELEU_REDUCTION_BY_PERIOD = {
    (2025, 2029): 0.02,
    (2030, 2034): 0.06,
    (2035, 2039): 0.145,
    (2040, 2044): 0.31,
    (2045, 2049): 0.62,
    (2050, 2099): 0.80,
}
# The 2025-2029 ceiling is quoted as 89.34 gCO2e/MJ in the regulation's own
# supporting material and in Gayu's model. Computing it from the baseline gives
# 89.3368, a 0.004% difference that would nonetheless make results diverge from
# hers. The published figure is used for those years so the two models agree
# exactly; later years are computed from the Article 4(2) reduction steps.
FUELEU_TARGET_PUBLISHED = {year: 89.34 for year in range(2025, 2030)}

FUELEU_PENALTY_EUR_PER_TONNE_VLSFO = 2400
VLSFO_MJ_PER_TONNE = 41_000

# Well-to-wake intensity of conventional marine fuel, from the European
# Commission's own worked example for marine diesel oil: 14.4 gCO2e/MJ
# well-to-tank plus 76.4 gCO2e/MJ tank-to-wake.
# Source: European Commission Q&A on Regulation (EU) 2023/1805, via Gayu.
FUELEU_CONVENTIONAL_WTW_INTENSITY = 90.8

# Green bunker fuel scenario: the ship burns its own cargo product (green
# hydrogen or e-ammonia) as bunker fuel instead of conventional VLSFO. Gayu's
# own gas-carrier notebook runs this as a worked example ("Green ammonia
# (RFNBO, 2x multiplier)"). Updated 1 Aug 2026 per Gayu to the real green
# ammonia well-to-wake intensity rather than the earlier near-zero placeholder.
FUELEU_GREEN_BUNKER_WTW_INTENSITY = 1.28  # gCO2e/MJ, Gayu's notebook

FUELEU_RFNBO_MULTIPLIER = 2.0  # green H2 / e-ammonia bunker fuel, to end of 2033 (Art. 5)
FUELEU_RFNBO_MULTIPLIER_EXPIRES = 2033
FUELEU_APPLIES_TO = (HALIFAX_HAMBURG,)

# Annex II tank-to-wake default values for ammonia combustion in internal
# combustion engines are marked "TBM" (to be measured) and are not yet set.
# Declared as a data gap; fuel-cell pathway factors and literature values are
# used instead.
FUELEU_AMMONIA_ICE_TTW_IS_TBM = True


# ---------------------------------------------------------------------------
# Carbon price scenarios
# ---------------------------------------------------------------------------
# Source: GMK Center consensus forecast aggregating Bloomberg, ABN Amro,
# Refinitiv, ICIS, S&P Global, Aurora and the Potsdam Institute. 2030 range
# EUR 80-147 across institutions, consensus approximately EUR 126.

# Prices are year-specific because the two sources answer different questions.
# The 2026 figures are a near-term market range; the 2030 figures are a forecast.
# Using an 80 EUR near-term price for 2030, or a 126 EUR 2030 forecast for 2026,
# would both be wrong.
#
# 2026: ESMA, Market Report on EU Carbon Markets 2026 (9 July 2026), via Gayu's
#       maritime cost model.
# 2030: GMK Center consensus forecast aggregating Bloomberg, ABN Amro, Refinitiv,
#       ICIS, S&P Global, Aurora and the Potsdam Institute. Range EUR 80-147
#       across institutions, consensus approximately EUR 126.
EU_ETS_PRICE_SCENARIOS_BY_YEAR = {
    2026: {"low": 70.0, "medium": 80.0, "high": 90.0},
    2030: {"low": 80.0, "medium": 126.0, "high": 147.0},
}

# UK ETS. RESOLVED, previously an open item.
#
# The medium figure is the UK ETS Authority's determination of GBP 49.41/tCO2e
# for the scheme year beginning 1 January 2026, published 28 November 2025. It is
# formally the price used for civil penalties, but it is calculated as the average
# end-of-day settlement price of 2026 UKA December futures over the 12 months to
# 11 November 2025, so it is a market-derived figure rather than an administrative
# rate. That makes it a defensible central anchor. For comparison, the equivalent
# 2025 determination was GBP 41.84.
#
# The low and high figures are Gayu's bracketing scenarios around that anchor.
# They are not themselves sourced forecasts, and should be described as a
# sensitivity range rather than as projections.
#
# Note this sits well below the EU ETS figures above, which is the expected
# relationship and was the reason the spec warned against reusing the EU series.
UK_ETS_PRICE_SCENARIOS = {"low": 40.0, "medium": 49.41, "high": 60.0}  # GBP/tCO2e
UK_ETS_PRICE_2026_OFFICIAL = 49.41

PRICE_SCENARIOS = ("low", "medium", "high")


# ---------------------------------------------------------------------------
# EU-UK ETS linkage
# ---------------------------------------------------------------------------
# The figures above hold the UK price flat across every model year, which is
# not a finding but an artefact: only the 2026 figure was ever sourced. The
# defensible forward path is not an invented growth rate, it is convergence,
# because the UK and EU are linking their trading schemes and linked schemes
# mutually recognise allowances, which arbitrages the price difference away.
#
# Timeline, all documented:
#   19 May 2025   UK and EU jointly commit to linking their ETSs.
#   12 Nov 2025   EU member states unanimously back a negotiating mandate.
#   w/c 19 Jan 2026  Formal negotiations open.
#
# Market expectation (Energy Aspects): the EUA-UKA spread falls below EUR 10/t
# by end-2026, narrows through 2027-28, and reaches full price alignment from
# 2029. The market has already repriced hard on the announcement alone: the
# spread fell from over GBP 35/t in January 2025 to roughly GBP 6.50 by August
# 2025. The Switzerland-EU linkage of 2020 is the precedent, where the discount
# closed within weeks of signature.
#
# NOT LAW. A summit was scheduled for 13 July 2026 at which a formal agreement
# was expected; that outcome is not confirmed in the sources consulted on
# 4 August 2026. So this may only ever appear as an explicitly labelled
# scenario, exactly like UK_ETS_INTL_EXPANSION_PROPOSED above. The frozen path
# stays the baseline.
#
# Note also that linkage contemplates mutual EU/UK CBAM exemptions. That does
# NOT touch either corridor in this study: Halifax-Hamburg is Canada-to-EU and
# Ningbo-Felixstowe is China-to-UK, and neither Canada nor China is party to
# the linkage. Do not let that provision leak into the corridor results.
UK_ETS_LINKAGE_IS_LAW = False
UK_ETS_LINKAGE_ANCHOR_YEAR = 2026  # last year on the sourced official figure
UK_ETS_LINKAGE_FULL_ALIGNMENT_YEAR = 2029
UK_ETS_PRICE_VARIANTS = ("frozen", "linked")


def eu_ets_price(year: int, scenario: str) -> float:
    """EU ETS price in EUR/tCO2e for a given year and scenario.

    Years between the two anchor points are linearly interpolated. Years beyond
    2030 hold flat at the 2030 figure rather than extrapolating, since the
    underlying forecasts do not extend further.
    """
    anchors = sorted(EU_ETS_PRICE_SCENARIOS_BY_YEAR)
    if year in EU_ETS_PRICE_SCENARIOS_BY_YEAR:
        return EU_ETS_PRICE_SCENARIOS_BY_YEAR[year][scenario]
    if year <= anchors[0]:
        return EU_ETS_PRICE_SCENARIOS_BY_YEAR[anchors[0]][scenario]
    if year >= anchors[-1]:
        return EU_ETS_PRICE_SCENARIOS_BY_YEAR[anchors[-1]][scenario]
    lo = max(a for a in anchors if a < year)
    hi = min(a for a in anchors if a > year)
    lo_p = EU_ETS_PRICE_SCENARIOS_BY_YEAR[lo][scenario]
    hi_p = EU_ETS_PRICE_SCENARIOS_BY_YEAR[hi][scenario]
    return lo_p + (hi_p - lo_p) * (year - lo) / (hi - lo)


def cbam_cert_price_within_ets_scenario_bounds(year: int = 2026) -> bool:
    """Sanity check: does the real published CBAM certificate price fall
    within that year's EU ETS low/high scenario bounds?

    The model prices EU CBAM using the EU ETS scenario range rather than
    CBAM_CERT_PRICE_Q1_2026_ACTUAL directly (see the comment above that
    constant). This is only a reasonable substitution while the two stay
    close, so this check exists to catch the day they drift apart - if the
    EU ETS scenario bounds are ever revised without checking against the
    actual CBAM print, this returning False is the signal to look again.
    """
    low = eu_ets_price(year, "low")
    high = eu_ets_price(year, "high")
    return low <= CBAM_CERT_PRICE_Q1_2026_ACTUAL <= high


# ---------------------------------------------------------------------------
# Modelling assumptions (not law)
# ---------------------------------------------------------------------------
# These are analyst choices rather than regulatory values, so they are separated
# from everything above. Each must be stated in the methodology chapter and
# carried through the sensitivity analysis.

# ---------------------------------------------------------------------------
# Origin carbon prices
# ---------------------------------------------------------------------------
# Article 9 of Regulation (EU) 2023/956 lets an importer deduct any carbon
# price already effectively paid in the country of origin from EU CBAM
# liability. These two figures replace the invented EUR 50 / GBP 10 placeholders
# that were in the model until this was looked up on 26-27 July 2026.

# CANADA. Federal Output-Based Pricing System (OBPS) rate, the industrial half
# of the Greenhouse Gas Pollution Pricing Act. Nova Scotia, where EverWind is
# based, does not run its own industrial carbon price and follows the federal
# one directly, confirmed via the Nova Scotia government's own climate change
# pages.
#
# CORRECTED 5 August 2026 (Alex, Student 4). The figure below through 4 August
# was CAD 110/tCO2e flat, taken from the December 2020 plan (CAD 95 in 2025,
# +15/year to CAD 170 by 2030, published in "A Healthy Environment and a
# Healthy Economy"). That plan was superseded before this figure was ever
# checked against a primary source. On 12 March 2026, Bill C-4 permanently
# repealed the *consumer* fuel charge (backdated to April 2025) but left the
# industrial system in place; the federal government published a revised
# industrial price path on 15 May 2026 that is materially lower and flatter
# than the abandoned 2020 plan:
# https://www.canada.ca/en/environment-climate-change/services/climate-change/pricing-pollution-how-it-will-work/carbon-pollution-pricing-federal-benchmark-information.html
#
#   2026: CAD 95   2027-2029: CAD 100 (flat)   2030: CAD 115
#   (2035: CAD 130, 2040: CAD 140 - outside this model's 2026-2030 run range)
#
# The old CAD 110 was never the real 2026 rate; it was an extrapolation from a
# plan that no longer applies. This model runs 2026-2030 on a flat production
# cost already (see `_placeholder_commercial`), but the origin carbon price
# now has a genuinely sourced year-varying schedule, so it is treated as
# year-varying via `origin_carbon_price_canada_eur(year)`, unlike production
# cost.
#
# CAVEAT, and it is a real one: OBPS is not a flat charge on every tonne. Each
# facility gets free allowances up to a sector-average performance benchmark
# and only pays this rate on emissions above that benchmark. A facility
# performing at or better than the benchmark could owe close to nothing despite
# this headline rate existing. EverWind's actual performance against its
# benchmark is not known, so this schedule is the ceiling on what could be
# deducted, not a confirmed effective price. Same shape of problem as the EU
# CBAM factor vs free allocation distinction elsewhere in this project.
#
# SECOND CAVEAT, also from Alex's 5 Aug 2026 delivery: the federal benchmark
# price is not what a facility actually pays either, because OBPS compliance
# units trade provincially and prices vary widely - around CAD 65/t in British
# Columbia, CAD 72/t in Ontario, and as low as roughly CAD 37.50/t where cheap
# Alberta-linked credits are available (mid-2026 figures, carboncredits.com).
# The federal benchmark is used here anyway because it is what Nova Scotia,
# EverWind's own jurisdiction, actually applies, not a shopping exercise
# across provinces. Still worth stating as a limitation: the true effective
# price could plausibly be lower than the federal benchmark used here.
#
# Converted at the ECB reference rate for 23 July 2026, 1 CAD = 0.62393 EUR.
FX_EUR_PER_CAD_2026_07_23 = 0.62393

ORIGIN_CARBON_PRICE_CANADA_CAD_PER_TCO2E_BY_YEAR = {
    2026: 95.0,
    2027: 100.0,
    2028: 100.0,
    2029: 100.0,
    2030: 115.0,
}


def origin_carbon_price_canada_cad(year: int) -> float:
    """Canada's federal industrial (OBPS) carbon price in CAD/tCO2e for `year`.

    Holds at the nearest published figure outside 2026-2030 rather than
    extrapolating, since the model does not run beyond that range anyway.
    """
    years = sorted(ORIGIN_CARBON_PRICE_CANADA_CAD_PER_TCO2E_BY_YEAR)
    if year in ORIGIN_CARBON_PRICE_CANADA_CAD_PER_TCO2E_BY_YEAR:
        return ORIGIN_CARBON_PRICE_CANADA_CAD_PER_TCO2E_BY_YEAR[year]
    if year < years[0]:
        return ORIGIN_CARBON_PRICE_CANADA_CAD_PER_TCO2E_BY_YEAR[years[0]]
    return ORIGIN_CARBON_PRICE_CANADA_CAD_PER_TCO2E_BY_YEAR[years[-1]]


def origin_carbon_price_canada_eur(year: int) -> float:
    """Canada's origin carbon price in EUR/tCO2e for `year`, for the Article 9
    CBAM deduction."""
    return round(origin_carbon_price_canada_cad(year) * FX_EUR_PER_CAD_2026_07_23, 2)


# Backward-compatible flat figure, now the 2026 baseline rather than the old
# (wrong) constant. Used only where a table genuinely cannot vary by year, for
# example the static emissions table column consumed by the dashboard and the
# sensitivity sweep's base case. `run_cbam_matrix` and `run_compliance_matrix`
# do NOT use this - they call `origin_carbon_price_eur(corridor, year)` below,
# so their outputs correctly vary year to year even though this constant does
# not.
ORIGIN_CARBON_PRICE_CANADA_EUR_PER_TCO2E = origin_carbon_price_canada_eur(2026)  # EUR 59.27

# CHINA. Set to zero, and this is a finding rather than a missing figure.
# China's national ETS as of 2026 covers only power generation, steel, cement
# and aluminium smelting. Hydrogen production falls under chemicals and
# petrochemicals, which multiple sources (ICAP, IEEFA, China-Briefing) describe
# as planned for a future expansion phase, not yet included. If hydrogen
# production is not in scope of any domestic carbon price, there is genuinely
# nothing to deduct under Article 9, which is different from simply not having
# looked the number up.
ORIGIN_CARBON_PRICE_CHINA_EUR_PER_TCO2E = 0.0


def origin_carbon_price_eur(corridor: str, year: int) -> float:
    """Origin carbon price in EUR/tCO2e for `corridor` in `year`.

    The single entry point `run_cbam_matrix` and `run_compliance_matrix` use,
    so the Article 9 deduction actually varies by year for Canada rather than
    applying one flat figure across 2026-2030. China stays at zero regardless
    of year - not because no figure was sourced, but because hydrogen and
    ammonia production are confirmed out of scope of China's national ETS
    (see the constant above), which is itself year-independent.
    """
    if corridor == HALIFAX_HAMBURG:
        return origin_carbon_price_canada_eur(year)
    if corridor == NINGBO_FELIXSTOWE:
        return ORIGIN_CARBON_PRICE_CHINA_EUR_PER_TCO2E
    raise ValueError(f"No origin carbon price sourced for corridor {corridor!r}")

# RESOLVED 1 August 2026. Same reference date as the Canada FX rate above, for
# consistency across every cross-currency conversion in the model. ECB euro
# foreign exchange reference rate for 23 July 2026: 1 EUR = 0.85318 GBP, so
# 1 GBP = 1 / 0.85318 EUR.
FX_EUR_PER_GBP_2026_07_23 = 1.17209
FX_EUR_PER_GBP = FX_EUR_PER_GBP_2026_07_23


def eur_to_gbp(amount_eur: float) -> float:
    """Convert a EUR amount to GBP at the 23 July 2026 ECB reference rate."""
    return amount_eur / FX_EUR_PER_GBP


def gbp_to_eur(amount_gbp: float) -> float:
    """Convert a GBP amount to EUR at the 23 July 2026 ECB reference rate.

    The inverse of `eur_to_gbp`, added 5 August 2026 for the pathway-choice
    analysis in `analysis/outputs.py`. That comparison has to run in EUR
    because production costs are denominated in EUR for both corridors, while
    UK CBAM liability comes back in GBP - the same direction of conversion
    `marginal_abatement_cost` already performs inline on the UK carbon price.

    Conversion here is for a within-corridor pathway comparison, never for
    presenting one corridor's headline cost in the other's currency. The
    project's rule that EUR and GBP are not mixed in a reported cost still
    holds; see `cbam_summary` for the labelled `_gbp_equivalent` convention
    used when the two corridors genuinely have to sit side by side.
    """
    return amount_gbp * FX_EUR_PER_GBP


# RESOLVED 4 August 2026. Needed to convert Riya's USD-denominated production
# cost literature review (Assumptions Table, "Production Costs - Literature")
# into EUR for commercial_inputs.csv. Same 23 July 2026 reference date as the
# Canada and GBP rates above, for consistency across every cross-currency
# conversion in the model.
# ECB euro foreign exchange reference rate for 23 July 2026 (ECB Statistical
# Data Warehouse, series EXR.D.USD.EUR.SP00.A): 1 EUR = 1.1392 USD.
FX_USD_PER_EUR_2026_07_23 = 1.1392
FX_EUR_PER_USD = round(1 / FX_USD_PER_EUR_2026_07_23, 6)


def usd_to_eur(amount_usd: float) -> float:
    """Convert a USD amount to EUR at the 23 July 2026 ECB reference rate."""
    return amount_usd * FX_EUR_PER_USD


def uk_ets_price(year: int, scenario: str = "medium", variant: str = "frozen") -> float:
    """UK ETS price in GBP/tCO2e.

    Args:
        variant: "frozen" holds the sourced 2026 official determination across
            every year. That is the baseline, and it is conservative rather
            than correct: nobody decided UK prices stay flat, only one year was
            ever sourced. "linked" runs the EU-UK ETS linkage scenario, which
            is NOT law (see UK_ETS_LINKAGE_IS_LAW) and must be labelled as a
            scenario wherever it appears.

    The linked path narrows the discount to the EU price to zero by
    UK_ETS_LINKAGE_FULL_ALIGNMENT_YEAR, rather than interpolating the price
    level directly. Modelling it as a shrinking spread is what the market
    commentary actually describes, and it keeps the UK price tracking EU
    movements during the transition instead of drifting on its own line.
    """
    if variant not in UK_ETS_PRICE_VARIANTS:
        raise ValueError(
            f"Unknown UK ETS price variant {variant!r}. "
            f"Expected one of {UK_ETS_PRICE_VARIANTS}."
        )

    frozen = UK_ETS_PRICE_SCENARIOS[scenario]
    if variant == "frozen":
        return frozen

    anchor = UK_ETS_LINKAGE_ANCHOR_YEAR
    align = UK_ETS_LINKAGE_FULL_ALIGNMENT_YEAR
    if year <= anchor:
        return frozen

    aligned_now = eu_ets_price(year, scenario) / FX_EUR_PER_GBP
    if year >= align:
        return aligned_now

    # Spread at the anchor year, shrinking linearly to zero at alignment.
    anchor_spread = (eu_ets_price(anchor, scenario) / FX_EUR_PER_GBP) - frozen
    remaining = (align - year) / (align - anchor)
    return aligned_now - anchor_spread * remaining


def cbam_factor(year: int) -> float:
    """EU CBAM factor for a given year. 100% from 2034 onward."""
    if year < 2026:
        return 0.0
    return CBAM_FACTOR.get(year, 1.00)


def default_value_markup(year: int) -> float:
    """Mark-up on EU CBAM default embedded emissions values. 30% from 2028 onward."""
    if year < 2026:
        return 0.0
    return DEFAULT_VALUE_MARKUP.get(year, 0.30)


def eu_ets_maritime_phase_in(year: int) -> float:
    """EU ETS maritime phase-in fraction. 100% from 2026 onward."""
    if year < 2024:
        return 0.0
    return EU_ETS_MARITIME_PHASE_IN.get(year, 1.00)


def fueleu_target(year: int) -> float:
    """FuelEU GHG intensity target in gCO2e/MJ for a given year.

    Source: Regulation (EU) 2023/1805 Article 4(2), applied to the 91.16 gCO2e/MJ
    2020 fleet-average baseline.
    """
    if year in FUELEU_TARGET_PUBLISHED:
        return FUELEU_TARGET_PUBLISHED[year]
    for (start, end), reduction in FUELEU_REDUCTION_BY_PERIOD.items():
        if start <= year <= end:
            return FUELEU_BASELINE_2020 * (1 - reduction)
    raise ValueError(
        f"No FuelEU target defined for {year}. Article 4(2) covers 2025 onward."
    )
