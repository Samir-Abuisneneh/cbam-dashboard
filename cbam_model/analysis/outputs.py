"""Tables and charts for the results chapter.

Two layers, reported separately because they cannot yet be joined. Currencies
are never mixed on a chart axis.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from ..config import regulatory_constants as rc  # noqa: E402

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


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
    fig, ax = plt.subplots(figsize=(7, 5))
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

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
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

    if compliance is not None and len(compliance):
        compliance.to_csv(OUTPUT_DIR / "compliance_cost_per_tonne.csv", index=False)
        written.append("compliance_cost_per_tonne.csv")

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
        plt.close(fig)
        written.append("effective_carbon_cost.png")

    for year in sorted(maritime["year"].unique()):
        fig = plot_maritime_cost_by_corridor(maritime, year)
        if fig:
            name = f"maritime_cost_{year}.png"
            fig.savefig(OUTPUT_DIR / name, dpi=150)
            plt.close(fig)
            written.append(name)

    return written
