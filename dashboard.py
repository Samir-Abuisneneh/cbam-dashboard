"""MCG scenario explorer over the CBAM corridor cost model.

Streamlit dashboard, tooling rather than part of the model itself. Calls
`cbam_model` live for every selection rather than reading pre-baked CSVs, so
it can never drift from the tested regulatory logic in `cbam_model/model/`.

Scope is deliberately the fixed scenario matrix already built and covered by
the 81-test suite: the two named corridors, their existing pathway/year/price/
vessel/route/speed dimensions. It does not accept arbitrary routes or ports -
that would need the routing package wired in as a genuine model feature first
(see memory: cbam-model-enhancement-ideas), not something a UI can add on its
own.

Run with:
    .venv/bin/streamlit run dashboard.py
"""

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from cbam_model import data_io  # noqa: E402
from cbam_model.config import regulatory_constants as rc  # noqa: E402
from cbam_model.config import scenarios  # noqa: E402
from cbam_model.config import vessel_logistics as vl  # noqa: E402
from cbam_model.config.unresolved import UnresolvedConstantError  # noqa: E402
from cbam_model.model import total_cost  # noqa: E402

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
        margin=dict(l=8, r=70, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TOKENS["ink_secondary"], size=13),
        showlegend=False,
        hoverlabel=dict(
            bgcolor=TOKENS["surface"],
            bordercolor=TOKENS["border"],
            font=dict(color=TOKENS["ink"]),
        ),
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
    "Carbon compliance cost only — CBAM plus maritime ETS plus FuelEU. "
    "Conversion and freight cost are not yet included (no owner assigned in "
    "the data contracts), so this is not a full delivered cost. "
    "EUR (Halifax–Hamburg) and GBP (Ningbo–Felixstowe) are never "
    "converted or combined."
)

emissions, _, _ = data_io.load_inputs()
placeholder_inputs = data_io.using_placeholder_data()
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
EXCLUDED_PATHWAYS = {"blue_smr_ccs", "blue_ccs"}

pathway_options = sorted(
    set(
        emissions[
            (emissions["corridor"] == corridor) & (emissions["product"] == product)
        ]["pathway"].unique()
    )
    - EXCLUDED_PATHWAYS
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
        "corridor — pending sourcing from IR 2025/2621 Annex I. Every pathway "
        "shown here is literature-only, not yet anchored to a regulatory "
        "default."
    )
else:
    st.sidebar.caption("Literature pathway — a sensitivity scenario around the CBAM default.")

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

uk_price_variant = "frozen"
if is_uk:
    uk_price_variant = st.sidebar.selectbox(
        "UK carbon price path",
        rc.UK_ETS_PRICE_VARIANTS,
        format_func=lambda v: (
            "Frozen at the 2026 determination (baseline)"
            if v == "frozen"
            else "EU-UK ETS linkage: converges to EU price (NOT law)"
        ),
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
        f"{real_rate_fraction:.1%} of the UK ETS price — from the confirmed "
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
tab_compliance, tab_maritime, tab_sensitivity = st.tabs(
    ["Compliance cost", "Maritime layer only", "Sensitivity"]
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
                    marker=dict(color=colors, cornerradius=4),
                    text=[f"{v:,.2f}" for v in values],
                    textposition="outside",
                    cliponaxis=False,
                    textfont=dict(color=TOKENS["ink"]),
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
                    marker=dict(color=colors, cornerradius=4),
                    text=[f"EUR {v:,.0f}" for v in values],
                    textposition="outside",
                    cliponaxis=False,
                    textfont=dict(color=TOKENS["ink"]),
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
    from cbam_model.analysis import sensitivity

    sweep = sensitivity.sweep_corridor(
        corridor, year=year, vessel=vessel_set, route=route,
        price_scenario=price_scenario,
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
                marker=dict(color=TOKENS["sequential"], cornerradius=4),
                text=[f"{v:.1f}%" for v in ranked_this["mean_abs_pct_change"]],
                textposition="outside",
                textfont=dict(color=TOKENS["ink"]),
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
