"""MCG scenario explorer over the CBAM corridor cost model.

Streamlit dashboard, tooling rather than part of the model itself. Calls
`cbam_model` live for every selection rather than reading pre-baked CSVs, so
it can never drift from the tested regulatory logic in `cbam_model/model/`.

Scope is deliberately the fixed scenario matrix already built and covered by
the test suite in `tests/test_model.py`: the two named corridors, their
existing pathway/year/price/vessel/route/speed dimensions. It does not accept
arbitrary routes or ports, which would need the routing package wired in as a
genuine model feature first, not something a UI can add on its own.

Run with:
    .venv/bin/streamlit run dashboard.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cbam_model import data_io, runner
from cbam_model.analysis import outputs, sensitivity
from cbam_model.config import regulatory_constants as rc
from cbam_model.config import scenarios
from cbam_model.config import vessel_logistics as vl
from cbam_model.config.unresolved import UnresolvedConstantError
from cbam_model.forecasting import price_model
from cbam_model.market_data import eua_prices
from cbam_model.model import total_cost
from cbam_model.optimisation import allocation

st.set_page_config(
    page_title="CBAM Corridor Cost Explorer", layout="wide", page_icon="⚓"
)

# ---------------------------------------------------------------------------
# Design tokens - fixed categorical identity per cost component, held constant
# across every chart in the app. Light/dark pair from the validated palette
# (dataviz skill reference instance): slot 1 blue = CBAM, slot 2 orange = ETS
# (EU or UK - mutually exclusive per corridor, so no clash), slot 3 aqua =
# FuelEU. Chart chrome (ink/surface/gridline) is the same reference instance.
# ---------------------------------------------------------------------------
_IS_DARK = st.get_option("theme.base") == "dark"

TOKENS = {
    "cbam": "#3987e5" if _IS_DARK else "#2a78d6",
    "ets": "#d95926" if _IS_DARK else "#eb6834",
    "fueleu": "#199e70" if _IS_DARK else "#1baf7a",
    "sequential": "#3987e5" if _IS_DARK else "#2a78d6",
    "ink": "#ffffff" if _IS_DARK else "#0b0b0b",
    "ink_secondary": "#c3c2b7" if _IS_DARK else "#52514e",
    "ink_muted": "#898781",
    "surface": "#1a1a19" if _IS_DARK else "#fcfcfb",
    "gridline": "#2c2c2a" if _IS_DARK else "#e1e0d9",
    "border": "rgba(255,255,255,0.10)" if _IS_DARK else "rgba(11,11,11,0.10)",
    "warning": "#fab219",
}

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap');

    #MainMenu {{ visibility: hidden; }}
    [data-testid="stAppDeployButton"] {{ display: none; }}
    footer {{ visibility: hidden; }}

    .block-container {{ padding-top: 2.75rem; max-width: 1180px; }}
    html, body, [class*="css"] {{ font-feature-settings: "tnum"; }}

    h1, h2, h3, .hero .value {{
        font-family: 'Inter', system-ui, sans-serif !important;
        letter-spacing: -0.01em;
    }}
    [data-testid="stMetricValue"], .mono, .badge, .eyebrow {{
        font-family: 'IBM Plex Mono', ui-monospace, monospace !important;
    }}

    .app-eyebrow {{
        font-family: 'IBM Plex Mono', ui-monospace, monospace;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        font-size: 0.72rem;
        font-weight: 600;
        color: {TOKENS['ink_muted']};
        display: flex; align-items: center; gap: 0.5rem;
        margin-bottom: 0.35rem;
    }}
    .app-eyebrow .line {{
        flex: 0 0 28px; height: 1px; background: {TOKENS['gridline']};
    }}

    [data-testid="stMetricValue"] {{
        font-variant-numeric: tabular-nums;
        font-weight: 600;
    }}
    [data-testid="stMetric"] {{
        background: color-mix(in srgb, {TOKENS['ink']} 3%, transparent);
        border: 1px solid {TOKENS['border']};
        border-radius: 8px;
        padding: 0.85rem 1rem 0.6rem;
    }}

    .eyebrow {{
        text-transform: uppercase;
        letter-spacing: 0.09em;
        font-size: 0.72rem;
        font-weight: 600;
        color: {TOKENS['ink_muted']};
        margin-bottom: 0.15rem;
    }}

    .badge-row {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.4rem 0 1rem; }}
    .badge {{
        display: inline-flex; align-items: center; gap: 0.35rem;
        padding: 0.22rem 0.65rem;
        border-radius: 4px;
        border: 1px solid {TOKENS['border']};
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: {TOKENS['ink_secondary']};
        background: color-mix(in srgb, {TOKENS['ink']} 3%, transparent);
    }}
    .badge.warn {{
        color: #9a6a00;
        border-color: color-mix(in srgb, {TOKENS['warning']} 55%, transparent);
        background: color-mix(in srgb, {TOKENS['warning']} 16%, transparent);
    }}
    .badge .dot {{
        width: 7px; height: 7px; border-radius: 50%; display: inline-block;
    }}

    .hero {{
        border: 1px solid {TOKENS['border']};
        border-radius: 10px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        background: linear-gradient(135deg,
            color-mix(in srgb, {TOKENS['cbam']} 7%, transparent),
            color-mix(in srgb, {TOKENS['ink']} 2%, transparent) 70%);
    }}
    .hero .value {{
        font-size: 2.7rem;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        line-height: 1.1;
        color: {TOKENS['ink']};
    }}
    .hero .unit {{
        font-family: 'IBM Plex Mono', ui-monospace, monospace;
        font-size: 0.95rem;
        font-weight: 500;
        color: {TOKENS['ink_secondary']};
        margin-left: 0.4rem;
    }}

    /* --- voyage strip: the ship makes the run between the two ports --- */
    .voyage {{
        border: 1px solid {TOKENS['border']};
        border-radius: 10px;
        padding: 1rem 1.4rem 0.85rem;
        margin-bottom: 1rem;
        display: flex; flex-direction: column; gap: 0.35rem;
    }}
    .voyage-row {{ display: flex; align-items: center; gap: 0.85rem; }}
    .voyage-port {{
        font-family: 'IBM Plex Mono', ui-monospace, monospace;
        font-size: 0.82rem;
        font-weight: 600;
        color: {TOKENS['ink']};
        white-space: nowrap;
    }}
    .voyage-track {{
        position: relative;
        flex: 1;
        height: 22px;
        display: flex; align-items: center;
    }}
    .voyage-track::before {{
        content: "";
        position: absolute; left: 0; right: 0; top: 50%;
        border-top: 1.5px dashed {TOKENS['gridline']};
    }}
    .voyage-track .ship {{ position: relative; margin-left: 46%; width: 34px; }}
    .voyage-meta {{
        font-family: 'IBM Plex Mono', ui-monospace, monospace;
        font-size: 0.74rem;
        color: {TOKENS['ink_muted']};
        letter-spacing: 0.03em;
        padding-left: calc(0.85rem);
    }}

    div[data-baseweb="tab-list"] {{ gap: 4px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

CORRIDOR_NAMES = {
    rc.HALIFAX_HAMBURG: "Halifax → Hamburg (EU CBAM / EU ETS / FuelEU)",
    rc.NINGBO_FELIXSTOWE: "Ningbo → Felixstowe (UK CBAM / UK ETS)",
}


def _corridor_short(c: str) -> str:
    return CORRIDOR_NAMES[c].split(" (")[0]


# Pathway keys are internal scenario identifiers, not intended for display.
# Humanised labels for the fixed, known set; anything new falls back to a
# generic title-cased rendering so the UI never breaks on a new pathway.
PATHWAY_LABELS = {
    "cbam_default": "CBAM default",
    "blue_smr_ccs": "Blue SMR + CCS",
    "blue_ccs": "Blue + CCS",
    "green_electrolysis": "Green electrolysis",
    "grey_smr": "Grey SMR",
    "coal_gasification": "Coal gasification",
}


def _pathway_display(p: str) -> str:
    return PATHWAY_LABELS.get(p, p.replace("_", " ").capitalize())


def _route_display(route: str) -> str:
    """Humanise an optimisation route key, "corridor / pathway".

    The optimisation package emits internal identifiers because it must not
    know how this app names things. Everywhere those keys reach a reader they
    go through here, so the new tabs read the same as the old ones rather than
    showing "ningbo_felixstowe / coal_gasification" next to "Ningbo → Felixstowe".
    """
    corridor, _, pathway = route.partition(" / ")
    origin = _corridor_short(corridor) if corridor in CORRIDOR_NAMES else corridor
    return f"{origin.split(' → ')[0]} · {_pathway_display(pathway)}"


# Forecasting model keys are algorithm names, not display copy. Each label says
# what the model assumes, because "ar1_log" tells a reader nothing about why it
# is in the comparison.
MODEL_LABELS = {
    "random_walk": "No change (baseline)",
    "drift": "Continues past growth",
    "ar1_log": "Reverts to a long-run level",
    "linear_trend": "Straight line through history",
    "ses": "Weighted recent average",
    "damped_trend": "Trend that flattens out",
    "theta": "Theta method",
}


def _model_display(m: str) -> str:
    return MODEL_LABELS.get(m, m.replace("_", " ").capitalize())


# Sensitivity sweep parameter names (cbam_model/analysis/sensitivity.py) are
# internal model identifiers, not display copy - humanised for the same
# reason as PATHWAY_LABELS above.
PARAMETER_LABELS = {
    "main_engine_power_kw": "Main engine power (kW)",
    "service_speed_knots": "Service speed (knots)",
    "engine_load_fraction": "Engine load fraction",
    "sfoc_g_per_kwh": "Fuel consumption rate (SFOC, g/kWh)",
    "vlsfo_carbon_factor": "VLSFO carbon factor",
    "carbon_price": "Carbon price",
    "port_days": "Port days",
    "fueleu_actual_intensity_gco2e_mj": "FuelEU actual GHG intensity (gCO2e/MJ)",
}


def _param_display(p: str) -> str:
    return PARAMETER_LABELS.get(p, p.replace("_", " ").capitalize())


CORRIDOR_PORTS = {
    rc.HALIFAX_HAMBURG: ("HALIFAX", "HAMBURG"),
    rc.NINGBO_FELIXSTOWE: ("NINGBO", "FELIXSTOWE"),
}

SHIP_ICON = f"""
<svg viewBox="0 0 64 32" width="34" height="17" xmlns="http://www.w3.org/2000/svg">
  <path d="M4 22 L8 27 L54 27 L58 22 L50 19 L10 19 Z" fill="{TOKENS['ink']}" />
  <rect x="13" y="10" width="9" height="9" rx="1" fill="{TOKENS['cbam']}" />
  <rect x="24" y="7" width="9" height="12" rx="1" fill="{TOKENS['ets']}" />
  <rect x="35" y="10" width="9" height="9" rx="1" fill="{TOKENS['fueleu']}" />
  <rect x="45" y="12" width="6" height="7" rx="1" fill="{TOKENS['ink']}" />
  <line x1="48" y1="12" x2="48" y2="5" stroke="{TOKENS['ink']}" stroke-width="1.6" stroke-linecap="round" />
</svg>
"""


def _badge(label: str, warn: bool = False, dot: str | None = None) -> str:
    cls = "badge warn" if warn else "badge"
    dot_html = f'<span class="dot" style="background:{dot}"></span>' if dot else ""
    return f'<span class="{cls}">{dot_html}{label}</span>'


def _voyage_strip(origin: str, dest: str, distance_nm: float, voyage_days: float, route: str) -> str:
    route_label = "via Suez" if route == "suez" else "via Cape of Good Hope"
    return f"""
    <div class="voyage">
        <div class="voyage-row">
            <span class="voyage-port">⛴ {origin}</span>
            <span class="voyage-track"><span class="ship">{SHIP_ICON}</span></span>
            <span class="voyage-port">{dest} ⚓</span>
        </div>
        <div class="voyage-meta">{distance_nm:,.0f} NM &nbsp;·&nbsp; {voyage_days:.1f} DAYS AT SEA &nbsp;·&nbsp; {route_label.upper()}</div>
    </div>
    """


def _chart_layout(fig: go.Figure, height: int) -> go.Figure:
    """Shared chrome so every chart in the app reads as one system."""
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 70, "t": 8, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": TOKENS["ink_secondary"], "size": 13},
        showlegend=False,
        hoverlabel={
            "bgcolor": TOKENS["surface"],
            "bordercolor": TOKENS["border"],
            "font": {"color": TOKENS["ink"]},
        },
    )
    fig.update_xaxes(
        gridcolor=TOKENS["gridline"], zerolinecolor=TOKENS["gridline"], color=TOKENS["ink_muted"]
    )
    fig.update_yaxes(showgrid=False, color=TOKENS["ink"])
    return fig


def _headroom(values: list[float]) -> dict:
    """Extra x-range so outside data labels never clip against the plot edge."""
    top = max(values) if values else 0
    return {"range": [0, top * 1.22]} if top else {}


st.markdown(
    '<div class="app-eyebrow"><span class="line"></span>MCG · MSc DATA SCIENCE FOR BUSINESS · UNIVERSITY OF BRISTOL</div>',
    unsafe_allow_html=True,
)
st.title("CBAM Corridor Cost Explorer")
st.caption(
    "Carbon compliance cost only: CBAM plus maritime ETS plus FuelEU. "
    "Conversion and freight cost are not yet included (no owner assigned in "
    "the data contracts), so this is not a full delivered cost. "
    "EUR (Halifax–Hamburg) and GBP (Ningbo–Felixstowe) are never "
    "converted or combined."
)

@st.cache_data(show_spinner=False)
def _load_inputs():
    """Input tables, read once per session rather than on every widget change.

    Streamlit re-executes this whole script on each interaction. Without the
    cache the three CSVs are re-read and re-validated every time, and
    `using_placeholder_data()` reads them a second time on top of that.
    """
    emissions, _, commercial = data_io.load_inputs()
    return emissions, commercial, data_io.using_placeholder_data()


@st.cache_data(show_spinner=False)
def _compliance_matrix(uk_price_variant: str):
    """Full compliance matrix for the corridor comparison, cached per price path.

    This is the most expensive call in the app (both corridors x every year x
    every price scenario x every emissions row) and its result does not depend
    on any sidebar control except the UK price path, so recomputing it when the
    user changes vessel or speed is pure waste.
    """
    emissions, _, _ = _load_inputs()
    return runner.run_compliance_matrix(emissions, uk_price_variant=uk_price_variant)


@st.cache_data(show_spinner=False)
def _eua_monthly():
    """Monthly EUA price series. Read and validated once per session.

    Returns None rather than raising if the file is absent, because the raw
    download is not fetched by the code and will not exist on a fresh clone.
    The tab then explains itself instead of the whole app failing.
    """
    try:
        return eua_prices.to_monthly(eua_prices.load_eua_daily())["price_mean"]
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def _forecast_scores():
    """Walk-forward validation of every model at every horizon.

    The most expensive call in the app after the compliance matrix, and it
    depends on nothing the user can change, so it is computed once.
    """
    series = _eua_monthly()
    if series is None:
        return None, None
    base = price_model.walk_forward(series, price_model.random_walk)
    rows = []
    for name in price_model.PRESPECIFIED:
        results = price_model.walk_forward(series, price_model.MODELS[name])
        score = price_model.evaluate(
            results, name, baseline=None if name == price_model.BASELINE else base
        )
        forecast = price_model.forecast_with_interval(series, price_model.MODELS[name], name)
        rows.append(
            {
                "model": name,
                "MAPE %": round(score.mape_pct, 1),
                "typical miss": round(float(np.exp(score.median_abs_log_error)), 1),
                "skill vs random walk": round(score.skill_vs_baseline, 3),
                "2030 point (EUR)": round(forecast.point_eur, 1),
                "2030 low (EUR)": round(forecast.lower_eur, 1),
                "2030 high (EUR)": round(forecast.upper_eur, 1),
            }
        )
    return pd.DataFrame(rows), price_model.horizon_sweep(series)


@st.cache_data(show_spinner=False)
def _allocation_options(product: str, year: int, price_scenario: str, uk_variant: str):
    compliance = _compliance_matrix(uk_variant)
    return allocation.build_options(
        product, year, price_scenario, compliance=compliance, uk_price_variant=uk_variant
    )


emissions, commercial, placeholder_inputs = _load_inputs()
if placeholder_inputs:
    st.warning(
        "Some inputs are still placeholders, not final figures. The "
        "commercial cost table's conversion and shipping costs have no "
        "owner yet; production cost is real (Riya's literature review). "
        "Emissions and all maritime figures are real, sourced data. "
        "See data/README.md."
    )

# ---------------------------------------------------------------------------
# Sidebar: scenario controls
# ---------------------------------------------------------------------------
st.sidebar.header("Scenario")

corridor = st.sidebar.selectbox(
    "Corridor", list(rc.CORRIDORS), format_func=_corridor_short
)
st.sidebar.caption(CORRIDOR_NAMES[corridor].split("(", 1)[1].rstrip(")"))
product = st.sidebar.selectbox(
    "Product", list(rc.PRODUCTS), format_func=lambda p: p.capitalize()
)

# Riya flagged the blue hydrogen figures (blue_smr_ccs, blue_ccs) as a data
# quality issue and asked for them to be dropped from the dashboard. The
# underlying rows stay in emissions_table.csv; this is a display-only filter.
#
# It has to be applied to every surface, not just the selector. Until
# 7 August 2026 it was subtracted from `pathway_options` alone, so the two
# charts in the "Which pathway / corridor" tab still ranked and tabulated blue
# hydrogen: on Halifax-Hamburg it sat at rank 2 of 3 in the cheapest-pathway
# chart. `emissions_shown` is the frame every display reads, so a pathway
# excluded here is excluded everywhere.
EXCLUDED_PATHWAYS = {"blue_smr_ccs", "blue_ccs"}

emissions_shown = emissions[~emissions["pathway"].isin(EXCLUDED_PATHWAYS)]

pathway_options = sorted(
    emissions_shown[
        (emissions_shown["corridor"] == corridor)
        & (emissions_shown["product"] == product)
    ]["pathway"].unique()
)
if not pathway_options:
    st.sidebar.error("No emissions pathway data for this corridor/product combination.")
    st.stop()

# Per Riya's 29 July 2026 proposal: anchor on the CBAM regulatory default
# value as the primary scenario, with literature pathways (green/grey/blue/
# coal) as bracketing sensitivity scenarios around it. Defaults the selector
# to cbam_default when one exists for this corridor/product.
has_cbam_default = "cbam_default" in pathway_options
default_pathway_index = (
    pathway_options.index("cbam_default") if has_cbam_default else 0
)


def _pathway_label(p: str) -> str:
    if p == "cbam_default":
        return "CBAM regulatory default"
    return f"{_pathway_display(p)} (literature)"


pathway = st.sidebar.selectbox(
    "Production pathway",
    pathway_options,
    index=default_pathway_index,
    format_func=_pathway_label,
)
if pathway == "cbam_default":
    st.sidebar.caption("Recommended primary scenario, per Riya's 29 July 2026 proposal.")
elif not has_cbam_default:
    st.sidebar.caption(
        f"No CBAM regulatory default value exists yet for {product} on this "
        "corridor, pending sourcing from IR 2025/2621 Annex I. Every pathway "
        "shown here is literature-only, not yet anchored to a regulatory "
        "default."
    )
else:
    st.sidebar.caption("Literature pathway, a sensitivity scenario around the CBAM default.")

year = st.sidebar.selectbox("Year", list(scenarios.YEARS))
price_scenario = st.sidebar.selectbox(
    "Carbon price scenario",
    list(rc.PRICE_SCENARIOS),
    index=1,
    format_func=lambda v: v.capitalize(),
)

vessel_set = st.sidebar.selectbox(
    "Vessel",
    list(vl.VESSEL_SETS),
    format_func=lambda v: "Gas carrier (VLGC/VLAC)" if v == "gas_carrier" else "Container ship (MCG-named)",
)
speed_scenario = (
    st.sidebar.selectbox(
        "Speed scenario",
        ("lower", "base", "upper"),
        index=1,
        format_func=lambda v: v.capitalize(),
    )
    if vessel_set == "gas_carrier"
    else "base"
)

route_options = ["suez"] + (["cape"] if corridor in vl.DISTANCE_NM_CAPE else [])
route = st.sidebar.selectbox(
    "Route",
    route_options,
    format_func=lambda r: "Suez Canal" if r == "suez" else "Cape of Good Hope diversion",
)

is_uk = rc.CORRIDOR_REGIME[corridor] == "UK"

uk_ets_variant = "current_scope"
if is_uk and year >= rc.UK_ETS_INTL_EXPANSION_EARLIEST_YEAR:
    uk_ets_variant = st.sidebar.selectbox(
        "UK ETS international voyage scope",
        scenarios.UK_ETS_VARIANTS,
        format_func=lambda v: (
            "Currently legislated (in-port emissions only)"
            if v == "current_scope"
            else "Proposed 50% international expansion (NOT law)"
        ),
    )
    st.sidebar.caption(scenarios.VARIANT_LABELS[uk_ets_variant])

# One label per entry in rc.UK_ETS_PRICE_VARIANTS, keyed by variant rather than
# branched on, so adding a fourth path fails visibly here (KeyError on the
# selector) instead of silently inheriting another path's caption. Defined in
# `config.scenarios` beside the variants themselves and covered by
# `test_every_uk_price_variant_has_its_own_label`; see that module for the
# mislabelling bug this shape prevents.
UK_PRICE_VARIANT_LABELS = scenarios.UK_PRICE_VARIANT_LABELS

uk_price_variant = "frozen"
if is_uk:
    uk_price_variant = st.sidebar.selectbox(
        "UK carbon price path",
        rc.UK_ETS_PRICE_VARIANTS,
        format_func=UK_PRICE_VARIANT_LABELS.__getitem__,
    )
    if uk_price_variant == "linked":
        st.sidebar.caption(
            f"EU-UK ETS linkage scenario, NOT law. The UK and EU committed to "
            f"link their schemes in May 2025; EU member states backed a "
            f"negotiating mandate in November 2025 and talks opened in January "
            f"2026. Linked schemes mutually recognise allowances, so prices "
            f"converge: market expectation is full alignment from "
            f"{rc.UK_ETS_LINKAGE_FULL_ALIGNMENT_YEAR}. "
            f"{year} price: GBP {rc.uk_ets_price(year, price_scenario, 'linked'):.2f} "
            f"against GBP {rc.uk_ets_price(year, price_scenario, 'frozen'):.2f} frozen. "
            f"Note the linkage also contemplates mutual EU/UK CBAM exemptions, "
            f"which do not apply here: this corridor is China to UK, and China "
            f"is not party to the linkage."
        )
    elif uk_price_variant == "desnz":
        st.sidebar.caption(
            f"{rc.UK_ETS_PRICE_DESNZ_SOURCE}. The only forward UK path here "
            f"with an official source, but read its caveats: these are real "
            f"{rc.UK_ETS_PRICE_DESNZ_PRICE_BASE_YEAR} prices while every other "
            f"price in the model is nominal, DESNZ states they are scenario "
            f"projections rather than forecasts, and they model a standalone "
            f"UK ETS that does not account for EU linking, so this and the "
            f"linked path are alternative views of the same uncertainty and "
            f"must never be combined. "
            f"{year} price: GBP {rc.uk_ets_price(year, price_scenario, 'desnz'):.2f} "
            f"against GBP {rc.uk_ets_price(year, price_scenario, 'frozen'):.2f} frozen."
        )
    else:
        st.sidebar.caption(
            "Holds the sourced 2026 official determination flat across every "
            "year. Conservative rather than correct: nobody decided UK prices "
            "stay flat, only one year was ever sourced."
        )

uk_cbam_override = None
if is_uk and year >= rc.UK_CBAM_START_YEAR:
    real_rate_fraction = rc.uk_cbam_rate_fraction(year)
    st.sidebar.markdown("**UK CBAM rate**")
    st.sidebar.caption(
        f"{real_rate_fraction:.1%} of the UK ETS price, from the confirmed "
        f"86.49% three-year baseline free allocation (Finance Act 2026 "
        f"s.149(4): 2019 EU ETS + 2022/2023 UK ETS, Teesside Hydrogen Plant) "
        f"and the {year} Article 16(14) factor. This is the real mechanism, "
        f"not a placeholder."
    )
    if st.sidebar.checkbox("Override with a what-if rate"):
        uk_cbam_override = st.sidebar.slider(
            "Share of UK ETS price charged", 0.0, 1.0, real_rate_fraction, 0.05
        )

bunker_fuel = "conventional"
if not is_uk:
    bunker_fuel = st.sidebar.selectbox(
        "Bunker fuel (FuelEU)",
        ("conventional", "green_rfnbo"),
        format_func=lambda v: (
            "Conventional (VLSFO)" if v == "conventional" else "Green RFNBO (own cargo as fuel)"
        ),
    )
    if bunker_fuel == "green_rfnbo":
        st.sidebar.caption(
            "Ship bunkers green hydrogen/ammonia instead of VLSFO at 1.28 "
            "gCO2e/MJ well-to-wake (Gayu), comfortably inside the target "
            "before the Article 5 2x multiplier is even applied. Only "
            "changes FuelEU: EU ETS still "
            "charges the voyage's actual CO2 either way, since propulsion "
            "fuel burn itself isn't re-modelled here."
        )

# ---------------------------------------------------------------------------
# Compute: maritime layer, CBAM layer, compliance join
# ---------------------------------------------------------------------------
profile = vl.corridor_profile(corridor, vessel_set, speed_scenario, route)
maritime = total_cost.maritime_cost_per_voyage(
    profile, year, price_scenario, uk_ets_variant,
    bunker_fuel=bunker_fuel, uk_price_variant=uk_price_variant,
)

row = emissions[
    (emissions["corridor"] == corridor)
    & (emissions["product"] == product)
    & (emissions["pathway"] == pathway)
].iloc[0]

is_placeholder_row = str(row.get("source", "")).startswith("PLACEHOLDER")

compliance = None
blocked_message = None
# UK CBAM's rate mechanism and the GBP/EUR rate are both resolved (see the
# caption above), so this except branch no longer fires for either reason.
# Kept as a safety net for any not-yet-sourced regulatory constant added later.
try:
    cbam_row = total_cost.cbam_cost_per_tonne(
        corridor=corridor,
        product=product,
        pathway=pathway,
        year=year,
        price_scenario=price_scenario,
        embedded_emissions_tco2e_per_tonne=row["embedded_emissions_tco2e_per_tonne"],
        # Year-varying (rc.origin_carbon_price_eur), not the emissions
        # table's flat 2026-baseline column - the dashboard lets the user
        # pick any year, and the origin price genuinely differs by year for
        # Canada since the 5 Aug 2026 correction.
        origin_carbon_price_eur_per_tco2e=rc.origin_carbon_price_eur(corridor, year),
        uk_cbam_rate_override=uk_cbam_override,
        uk_price_variant=uk_price_variant,
    )
    compliance = total_cost.compliance_cost_per_tonne(maritime, cbam_row)
except UnresolvedConstantError as exc:
    blocked_message = str(exc)

currency = "EUR" if not is_uk else "GBP"


def _fmt_money(value: float) -> str:
    """2dp normally; more precision only when 2dp would hide a nonzero value."""
    if value != 0 and abs(value) < 0.01:
        return f"{value:.4f}"
    return f"{value:.2f}"


st.markdown(
    '<div class="badge-row">'
    + _badge(_corridor_short(corridor), dot=TOKENS["cbam"])
    + _badge(f"Settles in {currency}")
    + _badge("UK CBAM/ETS regime" if is_uk else "EU CBAM/ETS/FuelEU regime")
    + (_badge("Contains placeholder inputs", warn=True) if placeholder_inputs else _badge("All inputs sourced", dot=TOKENS["fueleu"]))
    + "</div>",
    unsafe_allow_html=True,
)

origin_port, dest_port = CORRIDOR_PORTS[corridor]
st.markdown(
    _voyage_strip(origin_port, dest_port, maritime.distance_nm, maritime.voyage_days, route),
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
(
    tab_compliance,
    tab_maritime,
    tab_sensitivity,
    tab_choice,
    tab_forecast,
    tab_optimiser,
) = st.tabs(
    [
        "Compliance cost",
        "Maritime layer only",
        "Sensitivity",
        "Which pathway / corridor",
        "Price forecast",
        "Sourcing optimiser",
    ]
)

with tab_compliance:
    st.subheader(CORRIDOR_NAMES[corridor])
    if is_placeholder_row:
        st.info(
            f"'{_pathway_display(pathway)}' emissions for {product} on this "
            "corridor are a placeholder value, not final data."
        )

    if blocked_message:
        st.error(
            "This case cannot be priced yet:\n\n" + blocked_message.strip()
        )
    else:
        st.markdown(
            f"""
            <div class="hero">
                <div class="eyebrow">Total compliance cost, this scenario</div>
                <span class="value">{_fmt_money(compliance['total_compliance_cost_per_tonne'])}</span>
                <span class="unit">{currency} / tonne · {product.capitalize()}, {_pathway_display(pathway)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns(3)
        c1.metric(
            f"CBAM ({currency}/t)",
            _fmt_money(compliance["cbam_cost_per_tonne"]),
        )
        c2.metric(
            f"Maritime ETS + FuelEU ({currency}/t)",
            _fmt_money(compliance["maritime_cost_per_tonne"]),
        )
        c3.metric("Cargo tonnes this voyage", f"{compliance['cargo_tonnes']:,}")

        st.caption(
            "Total compliance cost = CBAM cost per tonne + this tonne's share "
            "of the voyage's EU/UK ETS and FuelEU cost. Not a delivered cost: "
            "production, conversion and freight are excluded."
        )

        breakdown = {
            "CBAM": (compliance["cbam_cost_per_tonne"], TOKENS["cbam"]),
            "EU ETS": (compliance["eu_ets_cost_per_tonne"], TOKENS["ets"]),
            "UK ETS": (compliance["uk_ets_cost_per_tonne"], TOKENS["ets"]),
            "FuelEU": (compliance["fueleu_cost_per_tonne"], TOKENS["fueleu"]),
        }
        breakdown = {k: v for k, v in breakdown.items() if v[0]}
        if breakdown:
            st.markdown('<div class="eyebrow">Cost breakdown, this scenario</div>', unsafe_allow_html=True)
            labels = list(breakdown.keys())
            values = [v[0] for v in breakdown.values()]
            colors = [v[1] for v in breakdown.values()]
            fig = go.Figure(
                go.Bar(
                    x=values,
                    y=labels,
                    orientation="h",
                    marker={"color": colors, "cornerradius": 4},
                    text=[f"{v:,.2f}" for v in values],
                    textposition="outside",
                    cliponaxis=False,
                    textfont={"color": TOKENS["ink"]},
                    hovertemplate="%{y}: %{x:,.2f} " + currency + "/t<extra></extra>",
                )
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_xaxes(title=f"Cost per tonne ({currency})", **_headroom(values))
            st.plotly_chart(
                _chart_layout(fig, height=90 + 46 * len(labels)),
                use_container_width=True,
                config={"displayModeBar": False},
            )

with tab_maritime:
    st.subheader("Per-voyage maritime carbon cost")
    st.caption(
        "Entirely Gayu's maritime data: distance, fuel burn, voyage CO2, and "
        "the resulting ETS/FuelEU cost for one voyage. Independent of cargo "
        "type or embedded emissions."
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Distance (nm)", f"{maritime.distance_nm:,.0f}")
    m2.metric("Voyage days", f"{maritime.voyage_days:.1f}")
    m3.metric("Voyage CO2 (t)", f"{maritime.voyage_co2_t:,.1f}")

    if not is_uk:
        voyage_parts = {
            "EU ETS": (maritime.eu_ets_cost_eur, TOKENS["ets"]),
            "FuelEU": (maritime.fueleu_cost_eur, TOKENS["fueleu"]),
        }
        voyage_parts = {k: v for k, v in voyage_parts.items() if v[0]}
        if voyage_parts:
            st.markdown('<div class="eyebrow">Voyage cost composition (EUR)</div>', unsafe_allow_html=True)
            labels = list(voyage_parts.keys())
            values = [v[0] for v in voyage_parts.values()]
            colors = [v[1] for v in voyage_parts.values()]
            fig = go.Figure(
                go.Bar(
                    x=values,
                    y=labels,
                    orientation="h",
                    marker={"color": colors, "cornerradius": 4},
                    text=[f"EUR {v:,.0f}" for v in values],
                    textposition="outside",
                    cliponaxis=False,
                    textfont={"color": TOKENS["ink"]},
                    hovertemplate="%{y}: EUR %{x:,.2f}<extra></extra>",
                )
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_xaxes(title="Cost per voyage (EUR)", **_headroom(values))
            st.plotly_chart(
                _chart_layout(fig, height=90 + 46 * len(labels)),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        st.write(f"**Total: EUR {maritime.total_eur:,.2f} per voyage**")
    else:
        st.write(f"UK ETS cost: GBP {maritime.uk_ets_cost_gbp:,.2f}")
        st.write(f"**Total: GBP {maritime.total_gbp:,.2f} per voyage**")
        st.caption(
            "The international ocean leg carries zero UK ETS liability under "
            "current law. Only time spent in a UK port is charged, unless the "
            "proposed international expansion variant is selected above."
        )

with tab_sensitivity:
    st.subheader("What drives the maritime cost")
    st.caption(
        "One-at-a-time sweep (±20%) on the maritime layer only, since "
        "that is the layer built entirely from sourced data. Does not capture "
        "parameter interactions."
    )
    sweep = sensitivity.sweep_corridor(
        corridor, year=year, vessel=vessel_set, route=route,
        price_scenario=price_scenario,
        # Must match the path selected in the sidebar. The ranking is
        # unaffected either way, since the price cancels out of a percentage
        # change, but the underlying cost levels in the table below are not.
        uk_price_variant=uk_price_variant,
    )
    ranked = sensitivity.rank_drivers(sweep)
    ranked_this = ranked[
        (ranked["corridor"] == corridor)
        & (ranked["vessel_set"] == vessel_set)
        & (ranked["year"] == year)
    ].sort_values("rank")
    if not ranked_this.empty:
        ranked_this = ranked_this.assign(
            parameter_label=ranked_this["parameter"].map(_param_display)
        )

    if not ranked_this.empty:
        st.markdown('<div class="eyebrow">Ranked by mean absolute % change in voyage cost</div>', unsafe_allow_html=True)
        fig = go.Figure(
            go.Bar(
                x=ranked_this["mean_abs_pct_change"],
                y=ranked_this["parameter_label"],
                orientation="h",
                marker={"color": TOKENS["sequential"], "cornerradius": 4},
                text=[f"{v:.1f}%" for v in ranked_this["mean_abs_pct_change"]],
                textposition="outside",
                textfont={"color": TOKENS["ink"]},
                hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
            )
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(
            title="Mean abs % change in voyage cost",
            **_headroom(list(ranked_this["mean_abs_pct_change"])),
        )
        st.plotly_chart(
            _chart_layout(fig, height=90 + 40 * len(ranked_this)),
            use_container_width=True,
            config={"displayModeBar": False},
        )

        with st.expander("Show as table"):
            st.dataframe(
                ranked_this[["rank", "parameter_label", "parameter", "mean_abs_pct_change"]].rename(
                    columns={
                        "parameter_label": "parameter",
                        "parameter": "model key",
                        "mean_abs_pct_change": "mean abs % change in voyage cost",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )

with tab_choice:
    st.caption(
        "Not an optimisation, but a ranking over the small set of pathways and "
        "corridors the literature actually supports. Answers \"which one, and "
        "when\", not \"what does it cost\" (that's the Compliance cost tab)."
    )
    st.subheader("Which pathway is cheapest?")
    st.caption(
        "Production cost + CBAM only, not a delivered cost: conversion, "
        "shipping and maritime cost are held pathway-invariant in the current "
        "data, so they cancel out of *which pathway wins* even though they'd "
        "be needed for an absolute delivered-cost figure. Same reasoning "
        "`marginal_abatement_cost` already relies on."
    )

    ranking = outputs.pathway_cost_ranking(
        emissions_shown, commercial, year=year, price_scenario=price_scenario,
        uk_price_variant=uk_price_variant,
    )
    ranking_here = ranking[
        (ranking["corridor"] == corridor) & (ranking["product"] == product)
    ].sort_values("rank")

    if ranking_here.empty:
        st.info("No commercial (production cost) data for this corridor/product.")
    else:
        cheapest_row = ranking_here.iloc[0]
        colors = [
            TOKENS["fueleu"] if p == cheapest_row["pathway"] else TOKENS["ink_muted"]
            for p in ranking_here["pathway"]
        ]
        fig = go.Figure(
            go.Bar(
                x=ranking_here["pathway_visible_cost_eur_per_tonne"],
                y=[_pathway_display(p) for p in ranking_here["pathway"]],
                orientation="h",
                marker={"color": colors, "cornerradius": 4},
                text=[f"EUR {v:,.0f}" for v in ranking_here["pathway_visible_cost_eur_per_tonne"]],
                textposition="outside",
                cliponaxis=False,
                textfont={"color": TOKENS["ink"]},
                hovertemplate="%{y}: EUR %{x:,.2f}/t<extra></extra>",
            )
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(
            title="Production + CBAM cost (EUR/tonne)",
            **_headroom(list(ranking_here["pathway_visible_cost_eur_per_tonne"])),
        )
        st.plotly_chart(
            _chart_layout(fig, height=90 + 46 * len(ranking_here)),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st.write(
            f"**Cheapest: {_pathway_display(cheapest_row['pathway'])}** "
            f"at EUR {cheapest_row['pathway_visible_cost_eur_per_tonne']:,.2f}/t "
            f"({year}, {price_scenario} price)."
        )

        robustness = outputs.pathway_choice_price_robustness(
            emissions_shown, commercial, year=year,
            uk_price_variant=uk_price_variant,
        )
        r_here = robustness[
            (robustness["corridor"] == corridor) & (robustness["product"] == product)
        ]
        if not r_here.empty:
            stable = bool(r_here.iloc[0]["choice_stable"])
            if stable:
                st.markdown(
                    _badge("Stable across low/medium/high price scenarios", dot=TOKENS["fueleu"]),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    _badge("Recommendation changes with the price scenario", warn=True),
                    unsafe_allow_html=True,
                )
                st.caption(
                    "Low: " + _pathway_display(r_here.iloc[0]["cheapest_pathway_low"])
                    + " · Medium: " + _pathway_display(r_here.iloc[0]["cheapest_pathway_medium"])
                    + " · High: " + _pathway_display(r_here.iloc[0]["cheapest_pathway_high"])
                )

    st.divider()
    st.subheader("Corridor comparison")
    st.caption(
        "Both corridors on one axis (GBP-equivalent, 23 July 2026 ECB rate), "
        "for the CBAM regulatory-default pathway, the only pathway label that "
        "exists on both corridors, since Halifax-Hamburg and Ningbo-Felixstowe "
        "otherwise run different production routes. UK price path: "
        f"{UK_PRICE_VARIANT_LABELS[uk_price_variant]}."
    )
    compliance_matrix = _compliance_matrix(uk_price_variant)
    comparison = outputs.corridor_cost_comparison(
        compliance_matrix,
        pathway="cbam_default",
        price_scenario=price_scenario,
        # Must match the variant the matrix was built with, or the base-case
        # filter drops every row and the chart reads as "no data".
        uk_price_variant=uk_price_variant,
    )
    comp_here = comparison[comparison["product"] == product].sort_values("year")

    if comp_here.empty:
        st.info("No corridor comparison available for this product/price scenario.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=comp_here["year"], y=comp_here["halifax_hamburg_gbp_equivalent"],
            name="Halifax-Hamburg", mode="lines+markers",
            line={"color": TOKENS["cbam"], "width": 3},
            hovertemplate="Halifax-Hamburg %{x}: GBP %{y:,.2f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=comp_here["year"], y=comp_here["ningbo_felixstowe_gbp_equivalent"],
            name="Ningbo-Felixstowe", mode="lines+markers",
            line={"color": TOKENS["ets"], "width": 3},
            hovertemplate="Ningbo-Felixstowe %{x}: GBP %{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(showlegend=True, legend={"orientation": "h", "y": 1.15})
        fig.update_xaxes(title="Year", dtick=1)
        fig.update_yaxes(title="Total compliance cost (GBP-equivalent/t)")
        st.plotly_chart(
            _chart_layout(fig, height=320), use_container_width=True,
            config={"displayModeBar": False},
        )

        crossover = outputs.corridor_crossover_year(
            compliance_matrix,
            pathway="cbam_default",
            price_scenario=price_scenario,
            uk_price_variant=uk_price_variant,
        )
        c_here = crossover[crossover["product"] == product]
        if not c_here.empty and c_here.iloc[0]["ordering_changes"]:
            cy = int(c_here.iloc[0]["crossover_year"])
            st.write(
                f"**Cheaper corridor flips in {cy}** "
                f"({_corridor_short(c_here.iloc[0]['cheaper_corridor_first_year'])} "
                f"→ {_corridor_short(c_here.iloc[0]['cheaper_corridor_last_year'])}), "
                f"the year UK CBAM starts, not a gradual overtake."
            )

    st.divider()
    st.subheader("When does switching pathway start paying for itself?")
    st.caption(
        "First year each pathway's marginal abatement cost drops below the "
        "corridor's carbon price. Check `carbon_price_varies_by_year` before "
        "reading a UK row: the UK ETS price is frozen (only 2026 was ever "
        "sourced), so \"no breakeven year\" there is an artefact of that "
        "assumption, not evidence switching never pays."
    )
    breakeven = outputs.abatement_breakeven_year(
        emissions_shown, commercial, price_scenario=price_scenario,
        uk_price_variant=uk_price_variant,
    )
    b_here = breakeven[
        (breakeven["corridor"] == corridor) & (breakeven["product"] == product)
    ]
    if b_here.empty:
        st.info("No abatement pathways to compare for this corridor/product.")
    else:
        display = b_here.copy()
        display["pathway"] = display["pathway"].map(_pathway_display)
        display["reference_pathway"] = display["reference_pathway"].map(_pathway_display)
        st.dataframe(
            display[[
                "pathway", "reference_pathway", "abatement_cost_eur_per_tco2",
                "verdict_first_year", "verdict_last_year", "breakeven_year",
                "first_marginal_year", "carbon_price_varies_by_year", "note",
            ]].rename(columns={
                "reference_pathway": "vs. reference pathway",
                "abatement_cost_eur_per_tco2": "MAC (EUR/tCO2)",
                "verdict_first_year": f"verdict {scenarios.YEARS[0]}",
                "verdict_last_year": f"verdict {scenarios.YEARS[-1]}",
            }),
            hide_index=True,
            use_container_width=True,
        )


with tab_forecast:
    st.caption(
        "Statistical forecasting of the EU allowance price, shown to establish "
        "what the price history on its own supports. Nothing on this tab feeds "
        "any cost figure elsewhere in the app. The three sourced carbon price "
        "scenarios remain the basis of every result on the other tabs."
    )

    series = _eua_monthly()
    if series is None:
        st.warning(
            "The EUA price file is not present. It is downloaded by hand rather "
            "than fetched, so it does not appear on a fresh clone. See "
            "cbam_model/market_data/eua_prices.py for where it comes from."
        )
    else:
        scores, sweep = _forecast_scores()
        consensus = price_model.consensus_2030()

        # Lead with the claim, not the evidence. Every number in it is read off
        # the results below rather than written here, so the verdict cannot
        # drift from the tables that support it.
        best = scores.loc[scores["skill vs random walk"].idxmax()]
        rw_row = scores[scores["model"] == price_model.BASELINE].iloc[0]
        rw_fc = price_model.forecast_with_interval(series, price_model.random_walk, "rw")
        wider = rw_fc.width_ratio() / consensus["width_ratio"]
        st.info(
            f"**A fitted forecast cannot pin down the 2030 carbon price, and that "
            f"is the finding.**\n\n"
            f"- Seven models were tried. The best of them, "
            f"*{_model_display(best['model'])}*, is barely better than simply "
            f"assuming the price never changes, and on this much data that margin "
            f"cannot be told apart from luck.\n"
            f"- Even the best model is typically out by a factor of "
            f"{best['typical miss']} four years ahead.\n"
            f"- Past prices alone put 2030 somewhere between EUR "
            f"{rw_fc.lower_eur:.0f} and EUR {rw_fc.upper_eur:.0f}. The forecasters "
            f"this study cites say EUR {consensus['low']:.0f} to "
            f"{consensus['high']:.0f}, a range {wider:.1f} times narrower.\n\n"
            f"Those forecasters are not contradicted by the data. They are simply "
            f"far more confident than past prices alone can justify, because they "
            f"are pricing where policy is heading and the price history does not "
            f"contain that. **This is the evidence for keeping the three sourced "
            f"scenarios as the base case.**"
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Daily observations", f"{len(eua_prices.load_eua_daily()):,}")
        c2.metric("Span", f"{series.index[0].year}-{series.index[-1].year}")
        c3.metric("Last monthly mean (EUR)", f"{series.iloc[-1]:.2f}")

        st.markdown('<div class="eyebrow">EUA price history, monthly mean</div>', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.to_numpy(),
                mode="lines",
                line={"color": TOKENS["ets"], "width": 2},
                hovertemplate="%{x|%b %Y}: EUR %{y:.2f}<extra></extra>",
            )
        )
        fig.add_hrect(
            y0=consensus["low"],
            y1=consensus["high"],
            fillcolor=TOKENS["cbam"],
            opacity=0.12,
            line_width=0,
            annotation_text="2030 sourced scenario range",
            annotation_position="top left",
            annotation_font={"color": TOKENS["ink_muted"], "size": 11},
        )
        st.plotly_chart(_chart_layout(fig, 300), use_container_width=True)

        st.markdown('<div class="eyebrow">How well each model did when tested against the past</div>', unsafe_allow_html=True)
        scores_display = scores.copy()
        scores_display["model"] = scores_display["model"].map(_model_display)
        scores_display = scores_display.rename(
            columns={
                "model": "Model",
                "MAPE %": "Average error %",
                "typical miss": "Typical miss (x)",
                "skill vs random walk": "Better than assuming no change?",
            }
        )
        st.dataframe(scores_display, hide_index=True, use_container_width=True)
        st.caption(
            "Skill is measured against the random walk, so zero means no better "
            "than assuming the price never changes. Negative is worse. Only "
            "damped_trend beats the baseline, and by a margin this sample cannot "
            "distinguish from luck: the 115 validation folds overlap so heavily "
            "that they amount to roughly 2.4 independent windows. Every model "
            "under-predicted, because the price rose sixfold between 2017 and "
            "2022 and nothing fitted before that saw it coming, which is why an "
            "interval can sit above its own point forecast."
        )

        st.divider()
        st.markdown('<div class="eyebrow">Where predictability dies</div>', unsafe_allow_html=True)
        skill = sweep.pivot(index="model", columns="horizon_months", values="skill_vs_baseline")
        skill = skill.reindex(list(price_model.PRESPECIFIED)).round(3)
        skill.index = [_model_display(m) for m in skill.index]
        skill.index.name = "Model"
        skill.columns = [f"{h} months ahead" for h in skill.columns]
        # Green where a model beats the baseline, red where it loses. A grid of
        # bare negative numbers hides the single positive row that matters.
        st.dataframe(
            skill.style.background_gradient(cmap="RdYlGn", vmin=-1.0, vmax=0.2, axis=None),
            use_container_width=True,
        )
        mape = sweep.pivot(index="model", columns="horizon_months", values="mape_pct")
        st.caption(
            "Skill by forecast horizon in months. Every model that extrapolates "
            "an undamped trend degrades monotonically as the horizon grows, "
            "which is a mechanism rather than noise. The random walk's own error "
            f"rises from {mape.loc['random_walk', 6]:.0f}% at six months to "
            f"{mape.loc['random_walk', 48]:.0f}% at four years. The price is "
            "forecastable over months and not over years, and this study needs "
            "years."
        )

        st.divider()
        st.markdown('<div class="eyebrow">Fitted forecast against the institutional consensus</div>', unsafe_allow_html=True)
        rw = price_model.forecast_with_interval(series, price_model.random_walk, "random_walk")
        comparison = price_model.compare_with_consensus(rw)
        d1, d2, d3 = st.columns(3)
        d1.metric("Consensus central (EUR)", f"{consensus['central']:.0f}")
        d2.metric(
            "Consensus range (EUR)",
            f"{consensus['low']:.0f}-{consensus['high']:.0f}",
            f"x{consensus['width_ratio']:.1f} wide",
        )
        d3.metric(
            "Random walk 80% (EUR)",
            f"{rw.lower_eur:.0f}-{rw.upper_eur:.0f}",
            f"x{rw.width_ratio():.1f} wide",
        )
        st.caption(
            f"The statistical interval is {comparison['model_interval_is_wider_by']}x "
            "wider than the published consensus. The consensus is not "
            "contradicted by the data, it sits comfortably inside what the "
            "history admits. It is far more precise than price history alone can "
            "justify, because the institutions are pricing the policy trajectory "
            "and the price series does not contain it. That is the argument for "
            "keeping sourced anchors as the base case, reached from the opposite "
            "direction. Note that 2030 has not happened, so this is not a test of "
            "which is more accurate and no such test is available."
        )


with tab_optimiser:
    st.caption(
        "Least-cost sourcing across both corridors and every pathway, subject "
        "to supply limits and an emissions ceiling. This is the only tab that "
        "optimises rather than enumerates. The capacity limits are analyst "
        "assumptions with no source, so read the answer as conditional on them."
    )

    o1, o2, o3 = st.columns(3)
    opt_product = o1.selectbox("Product", scenarios.PRODUCTS, key="opt_product")
    opt_year = o2.selectbox(
        "Year", list(scenarios.YEARS), index=len(scenarios.YEARS) - 1, key="opt_year"
    )
    demand_kt = o3.number_input(
        "Annual demand (kt)", min_value=100, max_value=10_000, value=1_000, step=100
    )
    demand = float(demand_kt) * 1_000

    o4, o5 = st.columns(2)
    route_share = o4.slider(
        "Max share any one route may supply", 0.2, 1.0, 0.6, 0.05,
        help="No source exists for this. It is the assumption the answer is most sensitive to.",
    )
    cut_pct = o5.slider(
        "Emissions cut below the unconstrained optimum", 0, 60, 30, 5,
        help="Zero means no ceiling, and the problem degenerates to a merit-order fill.",
    )

    options = _allocation_options(opt_product, opt_year, price_scenario, uk_price_variant)
    caps = allocation.CapacityAssumptions(per_route_share_of_demand=route_share)

    try:
        unconstrained = allocation.solve_allocation(options, demand, caps)
        ceiling = None if cut_pct == 0 else unconstrained.total_emissions_tco2e * (1 - cut_pct / 100)
        result = allocation.solve_allocation(
            options, demand, caps, emissions_cap_tco2e=ceiling,
            product=opt_product, year=opt_year, price_scenario=price_scenario,
        )
    except ValueError as exc:
        try:
            deepest = allocation.max_feasible_cut(options, demand, caps)
            st.error(
                f"A {cut_pct}% cut is not achievable here. The deepest possible "
                f"cut is {deepest:.0%}, and that is a limit of the supply base "
                "rather than of the budget: the cleaner routes cannot carry the "
                "volume within their capacity limits. Raise the capacity slider "
                "or ask for a shallower cut."
            )
        except ValueError:
            st.error(str(exc))
        result = None

    if result is not None:
        # Units live in the labels rather than the values. The metric tiles are
        # a quarter of the panel wide and truncate anything longer than about
        # ten characters, which silently hides the digits that matter.
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Cost (EUR/t)", f"{result.cost_per_tonne_eur:,.2f}")
        k2.metric("Emissions (MtCO2e)", f"{result.total_emissions_tco2e / 1e6:,.2f}")
        k3.metric("Routes used", f"{result.routes_used}")
        k4.metric(
            "Shadow price (EUR/tCO2e)",
            "n/a" if result.emissions_shadow_price_eur_per_tco2e is None
            else f"{result.emissions_shadow_price_eur_per_tco2e:,.2f}",
            help="What one more tonne of CO2e allowance would be worth at the optimum.",
        )

        st.markdown('<div class="eyebrow">What this says</div>', unsafe_allow_html=True)
        for line in allocation.read_result(result, options, label=_route_display):
            st.markdown(f"- {line}")

        shares = result.shares()
        shares = shares[shares > 0].sort_values()
        st.markdown('<div class="eyebrow">Optimal sourcing mix</div>', unsafe_allow_html=True)
        fig = go.Figure(
            go.Bar(
                x=(shares * 100).to_numpy(),
                y=[_route_display(r) for r in shares.index],
                orientation="h",
                marker={"color": TOKENS["cbam"], "cornerradius": 4},
                text=[f"{v:.1%}" for v in shares],
                textposition="outside",
                cliponaxis=False,
                textfont={"color": TOKENS["ink"]},
                hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            )
        )
        st.plotly_chart(_chart_layout(fig, 60 + 34 * len(shares)), use_container_width=True)

        st.markdown('<div class="eyebrow">The menu it chose from (EUR per tonne)</div>', unsafe_allow_html=True)
        menu = options[[
            "production_eur_per_tonne", "compliance_eur_per_tonne",
            "cost_eur_per_tonne", "emissions_tco2e_per_tonne",
        ]].round(2)
        menu.columns = ["Cost to make", "Carbon cost", "Total", "Carbon (tCO2e/t)"]
        menu.index = [_route_display(r) for r in menu.index]
        menu.index.name = "Route"
        st.dataframe(menu, use_container_width=True)
        st.caption(
            "Production cost plus carbon compliance cost only. Conversion and "
            "freight are excluded deliberately: they are placeholder values with "
            "no owner, and letting unsourced numbers into an objective function "
            "would let them decide the answer. UK corridor figures are converted "
            "from GBP at the same fixed ECB reference rate used elsewhere."
        )

        if cut_pct > 0:
            st.divider()
            st.markdown('<div class="eyebrow">Does the answer survive the carbon price uncertainty</div>', unsafe_allow_html=True)
            across = allocation.price_scenario_comparison(
                opt_product, opt_year, demand, caps,
                cap_fraction=1 - cut_pct / 100,
                compliance=_compliance_matrix(uk_price_variant),
            )
            if across.attrs["mix_is_invariant"]:
                st.success(
                    "**The optimal mix does not change across the low, medium and "
                    "high carbon price paths.** Only the cost and the shadow price "
                    "move. The sourcing decision is therefore robust to the single "
                    "largest uncertainty in the model, which is worth more than any "
                    "point estimate of that uncertainty."
                )
            else:
                st.warning(
                    "**The optimal mix changes with the carbon price path.** The "
                    "sourcing decision is not robust to the one input the model is "
                    "least certain about, so it should be reported as conditional "
                    "on the price scenario rather than as a recommendation."
                )
            across_display = across.drop(
                columns=[c for c in across.columns if c.startswith("share::")]
            ).rename(columns={
                "price_scenario": "Price path",
                "carbon_price_eur": "Carbon price (EUR)",
                "cost_per_tonne_eur": "Cost (EUR/t)",
                "routes_used": "Routes used",
                "shadow_price_eur_per_tco2e": "Shadow price (EUR/tCO2e)",
            })
            st.dataframe(across_display, hide_index=True, use_container_width=True)
            st.caption(
                "The emissions ceiling is held fixed in absolute terms across the "
                "three price paths. Setting it relative to each path's own optimum "
                "would move two things at once and produced a total cost that fell "
                "as carbon got more expensive, which is impossible."
            )

        st.divider()
        st.markdown('<div class="eyebrow">Marginal abatement cost curve</div>', unsafe_allow_html=True)
        sweep = allocation.cap_sweep(options, demand, caps)
        feasible = sweep[sweep["feasible"]]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=((1 - feasible["cap_fraction"]) * 100).to_numpy(),
                y=feasible["shadow_price_eur_per_tco2e"].to_numpy(),
                mode="lines+markers",
                line={"color": TOKENS["ets"], "width": 2, "shape": "hv"},
                marker={"size": 7},
                hovertemplate="%{x:.0f}% cut: EUR %{y:.2f}/tCO2e<extra></extra>",
            )
        )
        st.plotly_chart(_chart_layout(fig, 260), use_container_width=True)
        st.caption(
            "Shadow price against how deep the emissions cut is. It steps rather "
            "than curves because a linear program switches between discrete "
            "routes: each step is the point where one substitution is exhausted "
            "and a more expensive one starts. Cheap abatement is used first, so "
            "the average cost of a cut is always below the marginal cost of "
            "extending it."
        )

        if cut_pct > 0:
            st.divider()
            st.markdown('<div class="eyebrow">How much of this is the capacity assumption</div>', unsafe_allow_html=True)
            cap_sens = allocation.capacity_sensitivity(
                options, demand, cap_fraction=1 - cut_pct / 100
            )
            cap_sens = cap_sens.rename(
                columns={
                    **{
                        c: f"{_route_display(c.removeprefix('share::'))} share"
                        for c in cap_sens.columns
                        if c.startswith("share::")
                    },
                    "per_route_share": "Max share per route",
                    "cost_per_tonne_eur": "Cost (EUR/t)",
                    "routes_used": "Routes used",
                    "shadow_price_eur_per_tco2e": "Shadow price (EUR/tCO2e)",
                }
            )
            st.dataframe(cap_sens, hide_index=True, use_container_width=True)
            st.caption(
                "The same problem solved across a range of capacity assumptions. "
                "This sweep is the honest result rather than any single solve "
                "above, because the capacity numbers are the one input here with "
                "no provenance at all."
            )
