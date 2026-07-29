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


def maritime_summary(maritime: pd.DataFrame, price_scenario: str = "medium") -> pd.DataFrame:
    """Base-case maritime carbon cost per voyage, both corridors."""
    return maritime[
        (maritime["price_scenario"] == price_scenario)
        & (maritime["speed_scenario"].isin(["base", "service"]))
        & (maritime["route_scenario"] == "suez")
        & (maritime["uk_ets_variant"].isin(["n/a", "current_scope"]))
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
    """
    out = maritime.copy()
    out["cost_in_own_currency"] = out["total_eur"] + out["total_gbp"]
    out["currency"] = out["corridor"].map(
        lambda c: "EUR" if rc.CORRIDOR_REGIME[c] == "EU" else "GBP"
    )
    out["effective_cost_per_tonne_co2"] = (
        out["cost_in_own_currency"] / out["voyage_co2_t"]
    )
    return out[
        [
            "corridor", "vessel_set", "route_scenario", "speed_scenario", "year",
            "price_scenario", "uk_ets_variant", "voyage_co2_t", "currency",
            "cost_in_own_currency", "effective_cost_per_tonne_co2",
        ]
    ]


def cbam_summary(cbam_results: pd.DataFrame, price_scenario: str = "medium") -> pd.DataFrame:
    view = cbam_results[cbam_results["price_scenario"] == price_scenario].copy()
    view["cbam_cost_in_own_currency"] = (
        view["eu_cbam_cost_eur_per_tonne"] + view["uk_cbam_cost_gbp_per_tonne"]
    )
    view["currency"] = view["corridor"].map(
        lambda c: "EUR" if rc.CORRIDOR_REGIME[c] == "EU" else "GBP"
    )
    return view.sort_values(["year", "corridor", "product", "pathway"])


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
):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []

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
