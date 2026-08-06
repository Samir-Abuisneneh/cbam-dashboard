"""Tables and charts for the results chapter.

Two layers, reported separately because they cannot yet be joined. Currencies
are never mixed on a chart axis.
"""

from pathlib import Path

import pandas as pd

from ..config import regulatory_constants as rc
from ..config import scenarios

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


def _plt():
    """Lazy matplotlib import, so importing this module doesn't require it.

    matplotlib is a notebook/output-generation dependency, not in
    requirements.txt (the Streamlit Cloud deployment's dependency set) - the
    dashboard never plotted with it before it started importing this module
    for the pathway/corridor choice analyses added 5 August 2026, and a
    module-level `import matplotlib` broke the deployed app with a
    ModuleNotFoundError that had nothing to do with the code actually being
    used. Only the two plotting functions below need it; everything else in
    this module is pandas-only and must stay importable without it.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


BASE_CASE_BUNKERS = ["conventional", "n/a"]  # "n/a" is the UK corridor, which FuelEU does not price


def maritime_summary(maritime: pd.DataFrame, price_scenario: str = "medium") -> pd.DataFrame:
    """Base-case maritime carbon cost per voyage, both corridors.

    Held to conventional VLSFO bunkers. The green-bunker rows are a separate
    comparison (see `bunker_fuel_comparison`) and must not be mixed in here,
    since averaging the two would understate the base case.
    """
    return maritime[
        (maritime["price_scenario"] == price_scenario)
        & (maritime["speed_scenario"].isin(["base", "service"]))
        & (maritime["route_scenario"] == "suez")
        & (maritime["uk_ets_variant"].isin(["n/a", "current_scope"]))
        & (maritime["bunker_fuel"].isin(BASE_CASE_BUNKERS))
    ][
        [
            "corridor", "vessel_set", "year", "distance_nm", "voyage_days",
            "voyage_co2_t", "eu_ets_cost_eur", "fueleu_cost_eur",
            "uk_ets_cost_gbp", "total_eur", "total_gbp",
        ]
    ].sort_values(["year", "corridor", "vessel_set"])


def carbon_cost_per_tonne_co2(maritime: pd.DataFrame) -> pd.DataFrame:
    """Effective carbon cost per tonne of CO2 the voyage actually emits.

    This is the cleanest way to show the regulatory asymmetry without needing
    cargo tonnage. It divides what each corridor pays by what it emits, so the
    two are comparable even though one is priced in EUR and the other in GBP.

    `effective_cost_per_tonne_co2_gbp` additionally converts the EUR corridor's
    figure to GBP (23 July 2026 ECB reference rate), so the two corridors can
    be compared directly in one currency alongside the native-currency figure.
    """
    out = maritime.copy()
    out["cost_in_own_currency"] = out["total_eur"] + out["total_gbp"]
    out["currency"] = out["corridor"].map(
        lambda c: "EUR" if rc.CORRIDOR_REGIME[c] == "EU" else "GBP"
    )
    out["effective_cost_per_tonne_co2"] = (
        out["cost_in_own_currency"] / out["voyage_co2_t"]
    )
    out["effective_cost_per_tonne_co2_gbp"] = out.apply(
        lambda r: r["effective_cost_per_tonne_co2"]
        if r["currency"] == "GBP"
        else rc.eur_to_gbp(r["effective_cost_per_tonne_co2"]),
        axis=1,
    )
    return out[
        [
            "corridor", "vessel_set", "route_scenario", "speed_scenario", "year",
            "price_scenario", "uk_ets_variant", "uk_price_variant", "bunker_fuel",
            "voyage_co2_t", "currency", "cost_in_own_currency",
            "effective_cost_per_tonne_co2", "effective_cost_per_tonne_co2_gbp",
        ]
    ]


def cbam_summary(cbam_results: pd.DataFrame, price_scenario: str = "medium") -> pd.DataFrame:
    """CBAM cost summary, both corridors.

    `cbam_cost_gbp_equivalent` converts the EU corridor's EUR figure to GBP
    (23 July 2026 ECB reference rate) so both corridors are also comparable in
    one currency, alongside the native-currency `cbam_cost_in_own_currency`.
    """
    view = cbam_results[cbam_results["price_scenario"] == price_scenario].copy()
    view["cbam_cost_in_own_currency"] = (
        view["eu_cbam_cost_eur_per_tonne"] + view["uk_cbam_cost_gbp_per_tonne"]
    )
    view["currency"] = view["corridor"].map(
        lambda c: "EUR" if rc.CORRIDOR_REGIME[c] == "EU" else "GBP"
    )
    view["cbam_cost_gbp_equivalent"] = view.apply(
        lambda r: r["cbam_cost_in_own_currency"]
        if r["currency"] == "GBP"
        else rc.eur_to_gbp(r["cbam_cost_in_own_currency"]),
        axis=1,
    )
    return view.sort_values(["year", "corridor", "product", "pathway"])


def bunker_fuel_comparison(
    maritime: pd.DataFrame, price_scenario: str = "medium"
) -> pd.DataFrame:
    """What green bunker fuel saves against conventional VLSFO, per voyage.

    The supervisor's like-for-like fuel comparison. Only FuelEU prices bunker
    choice, so this is EU-corridor only and the saving is a pure FuelEU
    saving: EU ETS is unchanged because the model holds the vessel's actual
    CO2 output constant between the two cases (see `maritime_cost_per_voyage`),
    which isolates the compliance-cost effect rather than re-modelling the
    voyage's physics.
    """
    df = maritime[
        (maritime["price_scenario"] == price_scenario)
        & (maritime["speed_scenario"].isin(["base", "service"]))
        & (maritime["route_scenario"] == "suez")
        & (maritime["uk_ets_variant"].isin(["n/a", "current_scope"]))
        & (maritime["corridor"] == rc.HALIFAX_HAMBURG)
    ]
    if df.empty:
        return pd.DataFrame()

    keys = ["corridor", "vessel_set", "year"]
    wide = df.pivot_table(
        index=keys, columns="bunker_fuel", values="fueleu_cost_eur", aggfunc="first"
    ).reset_index()
    if "green_rfnbo" not in wide or "conventional" not in wide:
        return pd.DataFrame()

    wide = wide.rename(
        columns={
            "conventional": "fueleu_cost_conventional_eur",
            "green_rfnbo": "fueleu_cost_green_bunker_eur",
        }
    )
    wide["fueleu_saving_eur"] = (
        wide["fueleu_cost_conventional_eur"] - wide["fueleu_cost_green_bunker_eur"]
    )
    wide["price_scenario"] = price_scenario
    return wide.sort_values(["year", "vessel_set"])


MARGINAL_VERDICT_BAND_PCT = 10.0
"""How close to the carbon price counts as too close to call, in percent.

Set at 10%. The abatement costs this is applied to are ratios of two
literature-sourced figures, and for two of the four corridor-product
combinations the numerator is a subtraction between separate studies. A
result sitting inside 10% of the threshold is not distinguishable from the
other side of it given that input uncertainty, so it must not be reported as
a clean pass or fail.

This is not hypothetical. At 2030 medium prices, China ammonia green
electrolysis lands at EUR 57.3/tCO2 against a carbon price of EUR 57.9, a
margin of 1%, on a cost gap built from two unrelated papers. Reported as a
bare boolean that is a confident "yes"; reported honestly it is a coin flip.
"""


def _abatement_verdict(margin_pct: float) -> str:
    """Three-state reading of an abatement cost against the carbon price."""
    if abs(margin_pct) <= MARGINAL_VERDICT_BAND_PCT:
        return "marginal"
    return "justified" if margin_pct > 0 else "not justified"


def marginal_abatement_cost(
    emissions: pd.DataFrame,
    commercial: pd.DataFrame,
    year: int = 2030,
    price_scenario: str = "medium",
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """Cost of avoiding one tonne of CO2 by switching production pathway.

    MAC = (production cost of the cleaner route - production cost of the
    dirtiest route) / (emissions avoided). Compared against that corridor's
    carbon price: below it, the switch pays for itself on carbon grounds
    alone; above it, carbon pricing at that level does not justify it.

    This is the one delivered-cost-style question the model can answer
    exactly despite conversion and freight cost being unsourced. Both terms
    are invariant to production pathway (liquefying green hydrogen costs the
    same as liquefying grey), so they cancel from a within-corridor,
    within-product pathway difference. Absolute delivered cost stays out of
    reach; this difference does not.

    The reference route is the highest-emitting literature pathway for that
    corridor and product. `cbam_default` rows are excluded from both the
    reference choice and the comparison, since they are a regulatory default
    emissions figure rather than a real production route, and their
    production cost is only borrowed from the grey route.

    MAC is in EUR because production costs are. The UK corridor's carbon
    price is therefore converted from GBP so the comparison is like for like.
    """
    from ..model import cbam as cbam_model

    df = emissions.merge(commercial, on=["corridor", "product", "pathway"])
    df = df[~df["pathway"].map(cbam_model.is_cbam_default_pathway)]

    rows = []
    for (corridor, product), grp in df.groupby(["corridor", "product"]):
        if len(grp) < 2:
            continue
        ref = grp.loc[grp["embedded_emissions_tco2e_per_tonne"].idxmax()]
        if rc.CORRIDOR_REGIME[corridor] == "EU":
            carbon_price_eur = rc.eu_ets_price(year, price_scenario)
        else:
            carbon_price_eur = (
                rc.uk_ets_price(year, price_scenario, uk_price_variant)
                * rc.FX_EUR_PER_GBP
            )
        for _, alt in grp.iterrows():
            avoided = (
                ref["embedded_emissions_tco2e_per_tonne"]
                - alt["embedded_emissions_tco2e_per_tonne"]
            )
            if avoided <= 0:
                continue  # the reference route itself, or a dirtier one
            extra_cost = (
                alt["production_cost_eur_per_tonne"]
                - ref["production_cost_eur_per_tonne"]
            )
            mac = extra_cost / avoided
            margin_pct = (carbon_price_eur - mac) / carbon_price_eur * 100
            rows.append(
                {
                    "corridor": corridor,
                    "product": product,
                    "pathway": alt["pathway"],
                    "reference_pathway": ref["pathway"],
                    "year": year,
                    "price_scenario": price_scenario,
                    "extra_production_cost_eur_per_tonne": round(extra_cost, 2),
                    "emissions_avoided_tco2e_per_tonne": round(avoided, 3),
                    "abatement_cost_eur_per_tco2": round(mac, 2),
                    "carbon_price_eur_per_tco2": round(carbon_price_eur, 2),
                    "margin_vs_carbon_price_pct": round(margin_pct, 1),
                    "verdict": _abatement_verdict(margin_pct),
                    "justified_by_carbon_price": bool(mac < carbon_price_eur),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["corridor", "product", "abatement_cost_eur_per_tco2"]
    ) if rows else pd.DataFrame()


def abatement_source_robustness(
    emissions: pd.DataFrame,
    commercial: pd.DataFrame,
    year: int = 2030,
    price_scenario: str = "medium",
    green_route: str = "wind",
) -> pd.DataFrame:
    """Re-run the abatement result on IEA costs and put the two side by side.

    The primary production costs are peer-reviewed and country-specific, but
    two of the four corridor-product cost gaps are subtractions across separate
    studies: Canada hydrogen spans three papers, China ammonia spans two. Riya
    confirmed on 4 August 2026 that no single study covers the Canadian
    pathways, so the mixed sourcing cannot be fixed by swapping papers the way
    China hydrogen was.

    What can be done is to show whether the conclusion depends on it. The IEA
    sheet prices every pathway on both corridors under one methodology, so
    recomputing the abatement costs against it tests the finding rather than
    just disclaiming the weakness. A verdict that holds under both sourcings is
    reportable with the mixed-sourcing caveat attached; one that flips is not a
    finding at all.

    `verdict_stable` is the column that matters. `agree` is deliberately not
    reported as a headline: the two sourcings are not expected to produce the
    same number, only the same answer.
    """
    lit = marginal_abatement_cost(
        emissions, commercial, year=year, price_scenario=price_scenario
    )
    if lit.empty:
        return pd.DataFrame()

    iea = marginal_abatement_cost(
        emissions,
        _data_io().iea_production_costs(year=year, green_route=green_route),
        year=year,
        price_scenario=price_scenario,
    )
    if iea.empty:
        return pd.DataFrame()

    keys = ["corridor", "product", "pathway", "reference_pathway", "year", "price_scenario"]
    merged = lit.merge(iea, on=keys, suffixes=("_literature", "_iea"))
    merged["abatement_cost_delta_eur_per_tco2"] = (
        merged["abatement_cost_eur_per_tco2_iea"]
        - merged["abatement_cost_eur_per_tco2_literature"]
    ).round(2)
    merged["verdict_stable"] = (
        merged["verdict_literature"] == merged["verdict_iea"]
    )
    merged["sign_stable"] = (
        merged["justified_by_carbon_price_literature"]
        == merged["justified_by_carbon_price_iea"]
    )
    merged["iea_green_route"] = green_route
    return merged[
        keys
        + [
            "abatement_cost_eur_per_tco2_literature",
            "abatement_cost_eur_per_tco2_iea",
            "abatement_cost_delta_eur_per_tco2",
            "carbon_price_eur_per_tco2_literature",
            "margin_vs_carbon_price_pct_literature",
            "margin_vs_carbon_price_pct_iea",
            "verdict_literature",
            "verdict_iea",
            "verdict_stable",
            "sign_stable",
            "iea_green_route",
        ]
    ].sort_values(["corridor", "product", "abatement_cost_eur_per_tco2_literature"])


# ---------------------------------------------------------------------------
# Choice and timing. Added 5 August 2026.
# ---------------------------------------------------------------------------
# Everything above reports what something costs. The four functions below
# answer "which one should be picked, and when does the answer change" -
# pathway choice, corridor choice, the year a pathway switch starts paying for
# itself, and whether the pathway recommendation survives price uncertainty.
#
# None of this is an optimisation in the solver sense. There is no objective
# function and no search: the candidate set is the handful of pathways that
# exist in the literature and the two corridors the study is built on, so the
# "best" option is found by ranking an enumerated set, exactly as the rest of
# the model already enumerates its scenario matrix.


def pathway_cost_ranking(
    emissions: pd.DataFrame,
    commercial: pd.DataFrame,
    year: int = 2030,
    price_scenario: str = "medium",
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """Rank production pathways by the part of delivered cost that depends on them.

    `pathway_visible_cost_eur_per_tonne` is production cost plus CBAM
    liability. It is deliberately NOT a delivered cost, and must never be
    reported as one: conversion cost, shipping cost and the maritime ETS/FuelEU
    terms are all excluded.

    Excluding them is what makes this answerable at all while conversion and
    freight are still unsourced. Each of those three terms is invariant to
    production pathway as the model currently holds them - maritime cost
    depends on corridor, vessel, route, year and price but never on how the
    cargo was made; conversion cost is keyed by product alone and shipping cost
    by corridor and product. For a fixed corridor, product and year they are
    therefore one additive constant across every pathway, and a constant cannot
    change which pathway is cheapest. This is the same cancellation
    `marginal_abatement_cost` relies on, applied to a ranking instead of a
    pairwise difference.

    THE ASSUMPTION THAT CARRIES IT, and it should be stated in the methodology
    rather than left implicit: pathway-invariance of conversion and shipping
    cost is a property of how those two terms are currently populated, not an
    established fact about the world. Liquefying hydrogen made by electrolysis
    plausibly does not cost exactly what liquefying hydrogen made by coal
    gasification costs. If either term is ever sourced at pathway level, this
    cancellation breaks and the ranking becomes as blocked as full delivered
    cost already is.

    Costs are in EUR for both corridors, because production costs are. The UK
    corridor's CBAM liability is computed in GBP and converted, matching how
    `marginal_abatement_cost` already converts the UK carbon price so its
    comparison is like for like.

    `cbam_default` rows are excluded on the same grounds as in
    `marginal_abatement_cost`: it is a regulatory default emissions figure, not
    a production route a producer could actually choose, and its production
    cost is only borrowed from the corridor's grey pathway.
    """
    from ..model import cbam as cbam_model
    from ..model import total_cost

    df = emissions.merge(commercial, on=["corridor", "product", "pathway"])
    df = df[~df["pathway"].map(cbam_model.is_cbam_default_pathway)]
    if df.empty:
        return pd.DataFrame()

    rows = []
    for _, r in df.iterrows():
        corridor = r["corridor"]
        cbam_row = total_cost.cbam_cost_per_tonne(
            corridor=corridor,
            product=r["product"],
            pathway=r["pathway"],
            year=year,
            price_scenario=price_scenario,
            embedded_emissions_tco2e_per_tonne=r[
                "embedded_emissions_tco2e_per_tonne"
            ],
            # Year-varying, matching run_cbam_matrix rather than the emissions
            # table's flat 2026-baseline column.
            origin_carbon_price_eur_per_tco2e=rc.origin_carbon_price_eur(
                corridor, year
            ),
            uk_price_variant=uk_price_variant,
        )
        if rc.CORRIDOR_REGIME[corridor] == "EU":
            cbam_eur = cbam_row.eu_cbam_cost_eur_per_tonne
        else:
            cbam_eur = rc.gbp_to_eur(cbam_row.uk_cbam_cost_gbp_per_tonne)

        production_eur = float(r["production_cost_eur_per_tonne"])
        rows.append(
            {
                "corridor": corridor,
                "product": r["product"],
                "pathway": r["pathway"],
                "year": year,
                "price_scenario": price_scenario,
                "production_cost_eur_per_tonne": round(production_eur, 2),
                "cbam_cost_eur_per_tonne": round(cbam_eur, 2),
                "pathway_visible_cost_eur_per_tonne": round(
                    production_eur + cbam_eur, 2
                ),
                "embedded_emissions_tco2e_per_tonne": r[
                    "embedded_emissions_tco2e_per_tonne"
                ],
            }
        )

    out = pd.DataFrame(rows)
    out["rank"] = (
        out.groupby(["corridor", "product"])["pathway_visible_cost_eur_per_tonne"]
        .rank(method="dense")
        .astype(int)
    )
    out["is_cheapest"] = out["rank"] == 1
    return out.sort_values(["corridor", "product", "rank"]).reset_index(drop=True)


def cheapest_pathway(
    emissions: pd.DataFrame,
    commercial: pd.DataFrame,
    year: int = 2030,
    price_scenario: str = "medium",
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """The lowest pathway-visible-cost route per corridor and product.

    A thin filter over `pathway_cost_ranking`, whose docstring carries the
    caveats. Read that before quoting anything from this.
    """
    ranking = pathway_cost_ranking(
        emissions, commercial, year, price_scenario, uk_price_variant
    )
    if ranking.empty:
        return pd.DataFrame()
    return ranking[ranking["is_cheapest"]].reset_index(drop=True)


def pathway_choice_price_robustness(
    emissions: pd.DataFrame,
    commercial: pd.DataFrame,
    year: int = 2030,
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """Does the cheapest-pathway recommendation survive the price scenarios?

    Runs `cheapest_pathway` under the low, medium and high carbon price
    scenarios and reports whether the same pathway wins in all three.

    `choice_stable` is the column that matters, and it is deliberately the same
    shape of check as `abatement_source_robustness.verdict_stable`: a
    recommendation that flips with the carbon price assumption is not a
    recommendation, it is a restatement of the assumption. The three scenarios
    are not probability-weighted and no expected value is taken, because the
    scenario range is a sensitivity bracket rather than a distribution - the
    2026 figures are a near-term market range and the 2030 figures a consensus
    forecast, which are not the same kind of object.
    """
    picks = {}
    for scenario in rc.PRICE_SCENARIOS:
        ranking = pathway_cost_ranking(
            emissions, commercial, year, scenario, uk_price_variant
        )
        if ranking.empty:
            return pd.DataFrame()
        for _, r in ranking[ranking["is_cheapest"]].iterrows():
            picks.setdefault((r["corridor"], r["product"]), {})[scenario] = r[
                "pathway"
            ]

    rows = []
    for (corridor, product), by_scenario in sorted(picks.items()):
        distinct = set(by_scenario.values())
        row = {
            "corridor": corridor,
            "product": product,
            "year": year,
            "uk_price_variant": uk_price_variant,
        }
        for scenario in rc.PRICE_SCENARIOS:
            row[f"cheapest_pathway_{scenario}"] = by_scenario.get(scenario)
        row["choice_stable"] = len(distinct) == 1
        row["distinct_choices"] = len(distinct)
        rows.append(row)
    return pd.DataFrame(rows)


# Base-case filters for the corridor comparison. The compliance matrix splits
# the UK corridor on the proposed-expansion variant from 2028, and the EU
# corridor on bunker fuel, so without these the comparison would silently
# average a legislated result together with a policy-uncertain what-if.
BASE_CASE_UK_ETS_VARIANTS = ["n/a", "current_scope"]
BASE_CASE_UK_PRICE_VARIANTS = ["n/a", "frozen"]


def corridor_cost_comparison(
    compliance: pd.DataFrame,
    pathway: str = "cbam_default",
    price_scenario: str = "medium",
) -> pd.DataFrame:
    """Total compliance cost per tonne, both corridors side by side, by year.

    Converts the EU corridor's EUR figure to GBP so the two sit on one axis,
    following the `_gbp_equivalent` convention already used by `cbam_summary`
    and `carbon_cost_per_tonne_co2`. That conversion is the whole reason this
    function needs reading with care: it uses a single ECB reference-date rate
    (23 July 2026), so it holds the exchange rate fixed across a five-year
    horizon in which it would certainly move. The comparison is robust to that
    for large gaps and fragile for small ones, which matters most in whichever
    year the two corridors cross.

    Defaults to the `cbam_default` pathway because that is the study's primary
    scenario per Riya's 29 July 2026 proposal, and because it is one of only
    two pathway labels that exist on both corridors - the corridors otherwise
    carry different production routes (grey SMR on the Canadian side, coal
    gasification on the Chinese), so most pathway labels cannot be compared
    across them at all.
    """
    hh, nf = rc.HALIFAX_HAMBURG, rc.NINGBO_FELIXSTOWE

    def _base_case(column, allowed):
        # The EU corridor stores "n/a" in the UK-only columns, and pandas reads
        # that literal string back from CSV as NaN. Without the isna() arm this
        # filter silently drops every Halifax-Hamburg row whenever the frame
        # came from disk rather than straight from run_compliance_matrix, which
        # would leave the comparison with one corridor and no error.
        return compliance[column].isin(allowed) | compliance[column].isna()

    df = compliance[
        (compliance["pathway"] == pathway)
        & (compliance["price_scenario"] == price_scenario)
        & (compliance["route_scenario"] == "suez")
        & _base_case("uk_ets_variant", BASE_CASE_UK_ETS_VARIANTS)
        & _base_case("uk_price_variant", BASE_CASE_UK_PRICE_VARIANTS)
        & _base_case("bunker_fuel", BASE_CASE_BUNKERS)
    ].copy()
    if df.empty:
        return pd.DataFrame()

    df["total_gbp_equivalent"] = df.apply(
        lambda r: r["total_compliance_cost_per_tonne"]
        if r["currency"] == "GBP"
        else rc.eur_to_gbp(r["total_compliance_cost_per_tonne"]),
        axis=1,
    )

    wide = df.pivot_table(
        index=["product", "year"],
        columns="corridor",
        values="total_gbp_equivalent",
        aggfunc="first",
    ).reset_index()
    if hh not in wide.columns or nf not in wide.columns:
        return pd.DataFrame()

    wide = wide.rename(
        columns={
            hh: "halifax_hamburg_gbp_equivalent",
            nf: "ningbo_felixstowe_gbp_equivalent",
        }
    )
    wide["halifax_hamburg_gbp_equivalent"] = wide[
        "halifax_hamburg_gbp_equivalent"
    ].round(2)
    wide["ningbo_felixstowe_gbp_equivalent"] = wide[
        "ningbo_felixstowe_gbp_equivalent"
    ].round(2)
    wide["cost_gap_gbp"] = (
        wide["ningbo_felixstowe_gbp_equivalent"]
        - wide["halifax_hamburg_gbp_equivalent"]
    ).round(2)
    wide["cheaper_corridor"] = wide["cost_gap_gbp"].map(
        lambda gap: nf if gap < 0 else hh
    )
    wide["pathway"] = pathway
    wide["price_scenario"] = price_scenario
    wide.columns.name = None
    return wide.sort_values(["product", "year"]).reset_index(drop=True)


def corridor_crossover_year(
    compliance: pd.DataFrame,
    pathway: str = "cbam_default",
    price_scenario: str = "medium",
) -> pd.DataFrame:
    """The year the cheaper corridor changes, per product.

    Formalises what the README states narratively: the UK corridor's early
    advantage is a window that closes rather than a structural feature, because
    UK CBAM starts in 2027 and its rate fraction climbs to 2030 while the EU's
    CBAM factor is still ramping from a very low base.

    `crossover_year` is the first year whose cheaper corridor differs from the
    first modelled year's, or None if the ordering never changes across the
    horizon. Read it alongside the exchange-rate caveat in
    `corridor_cost_comparison`.
    """
    comparison = corridor_cost_comparison(compliance, pathway, price_scenario)
    if comparison.empty:
        return pd.DataFrame()

    rows = []
    for product, grp in comparison.groupby("product"):
        grp = grp.sort_values("year")
        first = grp.iloc[0]
        flipped = grp[grp["cheaper_corridor"] != first["cheaper_corridor"]]
        crossover = int(flipped.iloc[0]["year"]) if len(flipped) else None
        last = grp.iloc[-1]
        rows.append(
            {
                "product": product,
                "pathway": pathway,
                "price_scenario": price_scenario,
                "first_year": int(first["year"]),
                "last_year": int(last["year"]),
                "cheaper_corridor_first_year": first["cheaper_corridor"],
                "cheaper_corridor_last_year": last["cheaper_corridor"],
                "cost_gap_first_year_gbp": first["cost_gap_gbp"],
                "cost_gap_last_year_gbp": last["cost_gap_gbp"],
                "crossover_year": crossover,
                "ordering_changes": crossover is not None,
            }
        )
    return pd.DataFrame(rows)


def abatement_breakeven_year(
    emissions: pd.DataFrame,
    commercial: pd.DataFrame,
    years=tuple(scenarios.YEARS),
    price_scenario: str = "medium",
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """The year a pathway switch starts paying for itself on carbon grounds.

    Runs `marginal_abatement_cost` across the horizon and reports the first
    year each pathway's verdict reaches `justified`.

    READ `carbon_price_varies_by_year` BEFORE USING ANY UK-CORRIDOR ROW. The
    abatement cost itself does not move over the horizon at all: production
    costs are held flat (the model has no year-varying production cost
    mechanism) and embedded emissions are flat, so the numerator and
    denominator are both constant. Every bit of movement in the verdict comes
    from the carbon price.

    That makes this a real finding on the EU corridor, where the ETS price is a
    sourced forecast rising through 2030, and a degenerate one on the UK
    corridor under the default frozen price variant, where the price is held
    flat because only the 2026 figure was ever sourced. A frozen price cannot
    produce a crossing, so a UK row will report the same verdict in every year.
    That is an artefact of the price assumption and must not be written up as
    "switching never becomes worthwhile on the UK corridor". Running with
    `uk_price_variant="linked"` gives a rising UK path, but that variant is
    explicitly not law (see `UK_ETS_LINKAGE_IS_LAW`) and has to be labelled a
    scenario wherever it appears.

    A `marginal` verdict is not treated as a breakeven. The 10% band exists
    precisely because those rows are not distinguishable from the other side of
    the threshold, so `first_marginal_year` is reported separately rather than
    folded in.
    """
    frames = []
    for year in years:
        mac = marginal_abatement_cost(
            emissions,
            commercial,
            year=year,
            price_scenario=price_scenario,
            uk_price_variant=uk_price_variant,
        )
        if len(mac):
            frames.append(mac)
    if not frames:
        return pd.DataFrame()

    horizon = pd.concat(frames, ignore_index=True)

    rows = []
    for (corridor, product, pathway), grp in horizon.groupby(
        ["corridor", "product", "pathway"]
    ):
        grp = grp.sort_values("year")
        first, last = grp.iloc[0], grp.iloc[-1]
        varies = bool(grp["carbon_price_eur_per_tco2"].nunique() > 1)

        justified = grp[grp["verdict"] == "justified"]
        marginal = grp[grp["verdict"] == "marginal"]

        if varies:
            note = ""
        elif rc.CORRIDOR_REGIME[corridor] == "UK" and uk_price_variant == "frozen":
            note = (
                "Carbon price is flat across the horizon because the UK ETS price "
                "is frozen at the sourced 2026 determination. The verdict cannot "
                "change by construction. Not evidence about timing."
            )
        else:
            note = (
                "Carbon price is flat across the horizon, so the verdict cannot "
                "change by construction. Not evidence about timing."
            )

        rows.append(
            {
                "corridor": corridor,
                "product": product,
                "pathway": pathway,
                "reference_pathway": first["reference_pathway"],
                "price_scenario": price_scenario,
                "uk_price_variant": uk_price_variant,
                "abatement_cost_eur_per_tco2": first["abatement_cost_eur_per_tco2"],
                "carbon_price_first_year": first["carbon_price_eur_per_tco2"],
                "carbon_price_last_year": last["carbon_price_eur_per_tco2"],
                "carbon_price_varies_by_year": varies,
                "verdict_first_year": first["verdict"],
                "verdict_last_year": last["verdict"],
                "breakeven_year": (
                    int(justified.iloc[0]["year"]) if len(justified) else None
                ),
                "first_marginal_year": (
                    int(marginal.iloc[0]["year"]) if len(marginal) else None
                ),
                "note": note,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["corridor", "product", "abatement_cost_eur_per_tco2"]
    ).reset_index(drop=True)


def _data_io():
    """Imported lazily; data_io imports this package's siblings at module load."""
    from .. import data_io

    return data_io


def plot_effective_carbon_cost(maritime: pd.DataFrame, price_scenario: str = "medium"):
    """Effective carbon cost per tonne of voyage CO2, by corridor and year.

    The chart that makes the asymmetry visible. Axis label notes that the two
    corridors are in different currencies and are not converted.
    """
    df = carbon_cost_per_tonne_co2(maritime)
    df = df[
        (df["price_scenario"] == price_scenario)
        & (df["speed_scenario"].isin(["base", "service"]))
        & (df["route_scenario"] == "suez")
        & (df["uk_ets_variant"].isin(["n/a", "current_scope"]))
        & (df["vessel_set"] == "VLGC/VLAC")
        # Without this the pivot below would average the conventional and
        # green-bunker rows together and silently understate the EU corridor.
        & (df["bunker_fuel"].isin(BASE_CASE_BUNKERS))
    ]
    if df.empty:
        return None

    grouped = df.pivot_table(
        index="corridor", columns="year", values="effective_cost_per_tonne_co2"
    )
    fig, ax = _plt().subplots(figsize=(7, 5))
    grouped.plot(kind="bar", ax=ax)
    ax.set_ylabel("Carbon cost per tonne of voyage CO2\n(EUR for EU corridor, GBP for UK)")
    ax.set_xlabel("")
    ax.set_title(f"Effective maritime carbon cost, {price_scenario} price scenario")
    ax.legend(title="Year")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    return fig


def plot_maritime_cost_by_corridor(maritime: pd.DataFrame, year: int = 2026):
    """Per-voyage cost, one panel per currency so nothing is implicitly converted."""
    df = maritime[
        (maritime["year"] == year)
        & (maritime["speed_scenario"].isin(["base", "service"]))
        & (maritime["route_scenario"] == "suez")
        & (maritime["uk_ets_variant"].isin(["n/a", "current_scope"]))
        & (maritime["bunker_fuel"].isin(BASE_CASE_BUNKERS))
    ]
    if df.empty:
        return None

    fig, axes = _plt().subplots(1, 2, figsize=(12, 5))
    eu = df[df["corridor"] == rc.HALIFAX_HAMBURG]
    uk = df[df["corridor"] == rc.NINGBO_FELIXSTOWE]

    for ax, subset, cols, currency, title in (
        (axes[0], eu, ["eu_ets_cost_eur", "fueleu_cost_eur"], "EUR",
         "Halifax-Hamburg (EU regime)"),
        (axes[1], uk, ["uk_ets_cost_gbp"], "GBP",
         "Ningbo-Felixstowe (UK regime)"),
    ):
        if subset.empty:
            continue
        pivot = subset.pivot_table(
            index=["vessel_set", "price_scenario"], values=cols, aggfunc="first"
        )
        pivot.plot(kind="bar", stacked=True, ax=ax)
        ax.set_ylabel(f"Cost per voyage ({currency})")
        ax.set_title(title)
        ax.set_xlabel("")
        ax.tick_params(axis="x", labelsize=7, rotation=45)

    fig.suptitle(f"Maritime carbon cost per voyage, {year}. Currencies not converted.")
    fig.tight_layout()
    return fig


def write_all(
    maritime: pd.DataFrame,
    cbam_results: pd.DataFrame = None,
    sweep=None,
    ranked=None,
    compliance: pd.DataFrame = None,
    emissions: pd.DataFrame = None,
    commercial: pd.DataFrame = None,
):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []

    bunker = bunker_fuel_comparison(maritime)
    if len(bunker):
        bunker.to_csv(OUTPUT_DIR / "bunker_fuel_comparison.csv", index=False)
        written.append("bunker_fuel_comparison.csv")

    if emissions is not None and commercial is not None:
        mac = marginal_abatement_cost(emissions, commercial)
        if len(mac):
            mac.to_csv(OUTPUT_DIR / "marginal_abatement_cost.csv", index=False)
            written.append("marginal_abatement_cost.csv")

        # Both green routes, because the IEA solar PV and onshore wind figures
        # are far apart and the check is only meaningful if it covers both.
        robustness = pd.concat(
            [
                abatement_source_robustness(emissions, commercial, green_route=r)
                for r in ("wind", "solar")
            ],
            ignore_index=True,
        )
        if len(robustness):
            robustness.to_csv(
                OUTPUT_DIR / "abatement_source_robustness.csv", index=False
            )
            written.append("abatement_source_robustness.csv")

        ranking = pathway_cost_ranking(emissions, commercial)
        if len(ranking):
            ranking.to_csv(OUTPUT_DIR / "pathway_cost_ranking.csv", index=False)
            written.append("pathway_cost_ranking.csv")

        stability = pathway_choice_price_robustness(emissions, commercial)
        if len(stability):
            stability.to_csv(
                OUTPUT_DIR / "pathway_choice_price_robustness.csv", index=False
            )
            written.append("pathway_choice_price_robustness.csv")

        breakeven = abatement_breakeven_year(emissions, commercial)
        if len(breakeven):
            breakeven.to_csv(OUTPUT_DIR / "abatement_breakeven_year.csv", index=False)
            written.append("abatement_breakeven_year.csv")

    if compliance is not None and len(compliance):
        compliance.to_csv(OUTPUT_DIR / "compliance_cost_per_tonne.csv", index=False)
        written.append("compliance_cost_per_tonne.csv")

        comparison = corridor_cost_comparison(compliance)
        if len(comparison):
            comparison.to_csv(OUTPUT_DIR / "corridor_cost_comparison.csv", index=False)
            written.append("corridor_cost_comparison.csv")

        crossover = corridor_crossover_year(compliance)
        if len(crossover):
            crossover.to_csv(OUTPUT_DIR / "corridor_crossover_year.csv", index=False)
            written.append("corridor_crossover_year.csv")

    maritime.to_csv(OUTPUT_DIR / "maritime_cost_per_voyage.csv", index=False)
    written.append("maritime_cost_per_voyage.csv")

    maritime_summary(maritime).to_csv(OUTPUT_DIR / "maritime_summary.csv", index=False)
    written.append("maritime_summary.csv")

    carbon_cost_per_tonne_co2(maritime).to_csv(
        OUTPUT_DIR / "effective_carbon_cost.csv", index=False
    )
    written.append("effective_carbon_cost.csv")

    if cbam_results is not None and len(cbam_results):
        cbam_results.to_csv(OUTPUT_DIR / "cbam_cost_per_tonne.csv", index=False)
        written.append("cbam_cost_per_tonne.csv")

    if sweep is not None:
        sweep.to_csv(OUTPUT_DIR / "sensitivity_sweep.csv", index=False)
        written.append("sensitivity_sweep.csv")
    if ranked is not None:
        ranked.to_csv(OUTPUT_DIR / "sensitivity_ranked.csv", index=False)
        written.append("sensitivity_ranked.csv")

    # Whole-model sweep. The two files above cover voyage parameters against
    # per-voyage cost only, which ranks the wrong things now that CBAM
    # dominates by 2030. These rank against compliance cost per tonne.
    if emissions is not None:
        from . import sensitivity as _sens

        frames = []
        for _, row in emissions.iterrows():
            frames.append(
                _sens.sweep_compliance(
                    row["corridor"], row["product"], row["pathway"], emissions_row=row
                )
            )
        if frames:
            comp_sweep = pd.concat(frames, ignore_index=True)
            comp_sweep.to_csv(OUTPUT_DIR / "compliance_sensitivity_sweep.csv", index=False)
            written.append("compliance_sensitivity_sweep.csv")
            _sens.rank_compliance_drivers(comp_sweep).to_csv(
                OUTPUT_DIR / "compliance_sensitivity_ranked.csv", index=False
            )
            written.append("compliance_sensitivity_ranked.csv")

    fig = plot_effective_carbon_cost(maritime)
    if fig:
        fig.savefig(OUTPUT_DIR / "effective_carbon_cost.png", dpi=150)
        _plt().close(fig)
        written.append("effective_carbon_cost.png")

    for year in sorted(maritime["year"].unique()):
        fig = plot_maritime_cost_by_corridor(maritime, year)
        if fig:
            name = f"maritime_cost_{year}.png"
            fig.savefig(OUTPUT_DIR / name, dpi=150)
            _plt().close(fig)
            written.append(name)

    return written
