"""Generates CBAM_Model_Status_Report.pdf. Build tooling, not part of the model.

DATED BRIEFING, 27 JULY 2026. Do not read this as the current state of the
model and do not quote figures out of it. The prose is deliberately left close
to how it was written for that supervisor meeting, because a dated briefing
that gets quietly edited afterwards is worse than a stale one.

It is not a pure snapshot, and calling it "frozen" was overstating it: the
assumptions table carries some 4 August 2026 corrections that were folded in
after the meeting, while the surrounding prose was not revisited. So the two
disagree in places. Where they do, the table is the later text and this
docstring is the authority on what has since moved.

Several statements have since been superseded, and these are the ones most
likely to be quoted by mistake:

  - Canada's origin carbon price is given as CAD 110/tCO2e (EUR 68.63). That was
    an extrapolation from a December 2020 plan that had already been replaced.
    The sourced path is CAD 95 in 2026 rising to CAD 115 by 2030
    (`rc.ORIGIN_CARBON_PRICE_CANADA_CAD_PER_TCO2E_BY_YEAR`, corrected 5 Aug 2026).
  - Ammonia emissions are listed as pending and two Canadian hydrogen figures as
    provisional. All were delivered and taken as final on 4 August 2026.
  - The Ramsook et al. cross-check is described as not reconciling with the
    denominator hypothesis unconfirmed. The paper was read on 4 August 2026: the
    burden is measured against EU-bound revenue only, and it reconciles at 20.7%
    against the published 22% under the benchmark form of the obligation.
  - The assumptions table says China green hydrogen production cost takes "the
    lower figure" of Riya's two conflicting sheets (USD 4.63/kg). That was
    reversed by the source-consistency switch of 4 August 2026: the whole China
    hydrogen row now comes from one study (S0360319925010602), which puts green
    at USD 5.72-9.20/kg, and `data_io` uses that midpoint. The higher figure is
    in force, not the lower one. (The upper bound was reconciled against Riya's
    current sheet on 9 August 2026; the 4 August transcription read 6.62.)
  - The headline "roughly 37 times lower" for 2026 hydrogen is superseded twice
    over: by the input corrections above, and by the move to the
    `benchmark_shielded` CBAM mechanism on 7 August 2026. It also compared EUR
    against GBP without converting. See `README.md` for the current figures.
  - The whole document predates the CBAM free-allocation mechanism decision.
    Every CBAM figure in it is on the superseded `factor_scaled` form.
  - The test and reproduction-figure counts are from that date and have grown.

For the current position use `run_model.ipynb`, `README.md` and the test suite.
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "TitleCustom", parent=styles["Title"], fontSize=17, spaceAfter=4,
)
subtitle_style = ParagraphStyle(
    "Subtitle", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#444444"),
    spaceAfter=2,
)
h1 = ParagraphStyle(
    "H1Custom", parent=styles["Heading1"], fontSize=13, spaceBefore=16, spaceAfter=8,
    textColor=colors.HexColor("#1a1a1a"),
)
h2 = ParagraphStyle(
    "H2Custom", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=6,
    textColor=colors.HexColor("#2a2a2a"),
)
body = ParagraphStyle(
    "BodyCustom", parent=styles["Normal"], fontSize=10, leading=15, spaceAfter=8,
    alignment=TA_LEFT,
)
body_bold_lead = ParagraphStyle(
    "BodyBoldLead", parent=body,
)
cell = ParagraphStyle(
    "Cell", parent=styles["Normal"], fontSize=8.3, leading=11,
)
cell_header = ParagraphStyle(
    "CellHeader", parent=styles["Normal"], fontSize=8.5, leading=11,
    textColor=colors.white, fontName="Helvetica-Bold",
)

doc = SimpleDocTemplate(
    "CBAM_Model_Status_Report.pdf",
    pagesize=A4,
    topMargin=2.0 * cm, bottomMargin=2.0 * cm,
    leftMargin=2.0 * cm, rightMargin=2.0 * cm,
    title="CBAM Corridor Cost Model, Status Report",
    author="Samir Abuisneneh",
)

story = []

# --- Header -------------------------------------------------------------
story.append(Paragraph("CBAM Corridor Cost Model", title_style))
story.append(Paragraph("Status Report", subtitle_style))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "<b>Prepared by:</b> Samir Abuisneneh, Student 3 (Python Model and Scenario Analysis)",
    body,
))
story.append(Paragraph("<b>Date:</b> 27 July 2026", body))
story.append(Paragraph(
    "<b>Purpose:</b> Briefing for supervisor meeting. Summarises what has been built, "
    "what is assumed rather than confirmed, what remains outstanding, and recommended "
    "next steps.",
    body,
))

# --- 1. What the model does ---------------------------------------------
story.append(Paragraph("1. What the model does", h1))
story.append(Paragraph(
    "The model prices the carbon compliance cost of importing hydrogen and ammonia "
    "along two maritime corridors under two different regulatory regimes: Halifax to "
    "Hamburg, which falls under EU CBAM (Carbon Border Adjustment Mechanism, live since "
    "1 January 2026), EU ETS Maritime, and FuelEU Maritime; and Ningbo to Felixstowe, "
    "which falls under UK CBAM (not starting until 1 January 2027) and UK ETS Maritime. "
    "The two regimes running on different timelines is the central finding the "
    "dissertation is built around, not an inconvenience to model past.",
    body,
))
story.append(Paragraph(
    "It works in two layers. The maritime layer, built from Gayu's shipping data, "
    "prices carbon cost per voyage. The CBAM layer, built from Riya's emissions data, "
    "prices the border tax per tonne of product. A cargo capacity figure from Gayu "
    "converts between the two, so the model can report total carbon compliance cost "
    "per tonne of hydrogen or ammonia delivered, in the corridor's own currency.",
    body,
))
story.append(Paragraph(
    "The codebase is roughly 3,200 lines of Python, organised into a regulatory "
    "constants module, four cost calculation modules (CBAM, maritime ETS, FuelEU, and "
    "the layer that joins them), a data loading and validation layer, a scenario "
    "runner, and a sensitivity analysis module. It is tested by 81 automated tests and "
    "runs end to end from a single notebook, run_model.ipynb.",
    body,
))

# --- 2. Errors caught in the build spec ----------------------------------
story.append(Paragraph("2. Errors caught in the original build specification", h1))
story.append(Paragraph(
    "Three errors in the project's original technical build specification were found "
    "and corrected before they reached results.",
    body,
))
story.append(Paragraph(
    "<b>The FuelEU Maritime penalty formula was missing a divisor.</b> The "
    "specification calculated the penalty without dividing by the ship's actual fuel "
    "intensity, which Annex IV Part B of Regulation (EU) 2023/1805 requires. This "
    "would have overstated the penalty by roughly ninety times. Verified directly "
    "against the regulation, and independently confirmed by Gayu's separate "
    "implementation, which used the correct formula without prompting.",
    body,
))
story.append(Paragraph(
    "<b>The origin carbon price adjustment had a units error.</b> The specification "
    "subtracted a price per tonne of CO2 directly from a total cost figure, which "
    "could produce a negative CBAM liability from a positive one under realistic "
    "inputs. Corrected so the adjustment scales with the same emissions volume and "
    "CBAM factor as the liability it offsets, consistent with Article 9 of Regulation "
    "(EU) 2023/956.",
    body,
))
story.append(Paragraph(
    "<b>The FuelEU target schedule stopped at 2029</b>, while the scenario matrix runs "
    "through 2030, where Article 4(2) of the regulation tightens the reduction "
    "requirement from 2% to 6%. The full step schedule through 2050 has been added.",
    body,
))
story.append(Paragraph(
    "Gayu's maritime notebooks also corrected the build specification on several "
    "points, most significantly the Halifax to Hamburg distance, which the "
    "specification listed as approximately 6,300 nautical miles against the correct "
    "SeaRoute derived figure of 2,962 nautical miles. This had been overstating that "
    "corridor's voyage emissions by more than a factor of two.",
    body,
))

# --- 3. What was assumed -------------------------------------------------
story.append(Paragraph("3. What was assumed, and what has since been resolved", h1))
story.append(Paragraph(
    "This is the section that matters most. Every input the model depends on is "
    "listed below with its current status.",
    body,
))

table_data = [
    [Paragraph("Input", cell_header), Paragraph("Status", cell_header),
     Paragraph("Detail", cell_header)],
    [Paragraph("Maritime costs (distance, fuel, vessel specs)", cell),
     Paragraph("<b>Resolved</b>", cell),
     Paragraph("From Gayu's three notebooks. All 31 published figures reproduce "
               "exactly in the model's test suite.", cell)],
    [Paragraph("Cargo tonnage per voyage", cell),
     Paragraph("<b>Resolved</b>", cell),
     Paragraph("From Gayu's cargo capacity notebook: 84,000 m3 vessel (Seo et al., "
               "2024), 98% IMO filling limit, giving 56,142 t ammonia or 5,828 t "
               "hydrogen. See caveat below.", cell)],
    [Paragraph("Hydrogen embedded emissions", cell),
     Paragraph("<b>Resolved</b>", cell),
     Paragraph("From Riya, delivered 26 July 2026 and revised 4 August 2026, both "
               "corridors, four pathways each, all cited to named sources. The "
               "4 August revision moved Canada blue from 4.89 to 2.02. All three "
               "China hydrogen pathways were then consolidated onto a single "
               "study (S0360319925010602), agreed with Riya, replacing figures "
               "that had been drawn from four different papers: grey 29.02 to "
               "20.09 and blue 7.91 to 6.28.", cell)],
    [Paragraph("Ammonia embedded emissions", cell),
     Paragraph("<b>Delivered</b>", cell),
     Paragraph("Delivered 29 July 2026 and revised 4 August 2026. Both corridors, "
               "with CBAM regulatory defaults (1.98 Canada, 4.36 China). The 4 August "
               "revision corrected China coal gasification from 4.60 to 6.15: the old "
               "value was the same paper's natural-gas row, mislabelled.", cell)],
    [Paragraph("UK ETS maritime price", cell),
     Paragraph("<b>Resolved</b>", cell),
     Paragraph("GBP 49.41/tCO2e, the UK ETS Authority's official determination for "
               "the 2026 scheme year, published 28 November 2025. Calculated from "
               "twelve months of UKA December futures settlement prices, so market "
               "derived rather than an administrative figure.", cell)],
    [Paragraph("EU ETS price", cell),
     Paragraph("<b>Resolved</b>", cell),
     Paragraph("Two anchor years used: 2026 from ESMA's near term market range (via "
               "Gayu), 2030 from a multi institution consensus forecast. The model "
               "interpolates between them by year.", cell)],
    [Paragraph("Canada origin carbon price", cell),
     Paragraph("<b>Resolved, with a caveat</b>", cell),
     Paragraph("CAD 110/tCO2e, the federal Output Based Pricing System rate for "
               "2026 (Nova Scotia, where EverWind is based, follows the federal rate "
               "directly). Converted to EUR 68.63 at the ECB reference rate for 23 "
               "July 2026. Caveat: this system only charges on emissions above a "
               "facility specific benchmark, so the true figure paid could be lower. "
               "Treat as an upper bound, not a confirmed effective price.", cell)],
    [Paragraph("China origin carbon price", cell),
     Paragraph("<b>Resolved</b>", cell),
     Paragraph("Set to EUR 0. This is a finding, not a gap: hydrogen production is "
               "not currently within the scope of China's national Emissions "
               "Trading Scheme, which as of 2026 covers only power generation, "
               "steel, cement, and aluminium. Chemicals and petrochemicals, which "
               "would include hydrogen, are described in official and industry "
               "sources as planned for a future expansion phase.", cell)],
    [Paragraph("UK CBAM phase in mechanism", cell),
     Paragraph("<b>Resolved</b>", cell),
     Paragraph("Traced through primary UK legislation: the draft CBAM (Calculation "
               "of CBAM Rate and Determination of Carbon Price Relief) Regulations "
               "2026 and the Greenhouse Gas Emissions Trading Scheme (Amendment) "
               "Order 2026. The UK CBAM rate is not a flat percentage of embedded "
               "emissions like the EU's; it is UK ETS price times one minus a "
               "baseline free allocation percentage times an Article 16(14) factor "
               "that runs 0.975 in 2027 down to 0.775 by 2030. The baseline (Finance "
               "Act 2026 s.149(4)) blends 2019 EU ETS data with 2022 and 2023 UK "
               "ETS data for the UK's one in scope hydrogen installation, Teesside "
               "Hydrogen Plant. All three years are now sourced, giving a baseline "
               "of 86.49% and an implied rate rising from 15.7% of the UK ETS price "
               "in 2027 to 33.0% by 2030.",
               cell)],
    [Paragraph("GBP to EUR exchange rate", cell),
     Paragraph("<b>Resolved</b>", cell),
     Paragraph("ECB reference rate for 23 July 2026, 1 GBP = 1.17209 EUR, the same "
               "reference date used for the Canadian dollar and US dollar "
               "conversions. Headline tables still report each corridor in its own "
               "currency, as Gayu's notebooks do; the rate is applied only where a "
               "single-currency comparison is explicitly labelled as such.", cell)],
    [Paragraph("Production cost", cell),
     Paragraph("<b>Resolved</b>", cell),
     Paragraph("From Riya, 4 August 2026, covering every modelled pathway on both "
               "corridors, reconciled against her current sheet on 9 August 2026. "
               "Converted from USD at the 23 July 2026 ECB rate. Her two sheets "
               "disagreed on China green hydrogen (4.63 vs 5.72-9.20 USD/kg); the "
               "source-consistency switch takes the latter, so the whole China "
               "hydrogen row sits on one study, and that choice needs stating in "
               "the methodology.", cell)],
    [Paragraph("Conversion and shipping cost", cell),
     Paragraph("<b>Not sourced, no owner</b>", cell),
     Paragraph("See Section 4. Both are invariant to production pathway, so they "
               "cancel out of within-corridor pathway comparisons and do not block "
               "the marginal abatement cost results.", cell)],
]

col_widths = [3.9 * cm, 2.6 * cm, 10.5 * cm]
assumptions_table = Table(table_data, colWidths=col_widths, repeatRows=1)
assumptions_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f4858")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f7")]),
]))
story.append(assumptions_table)
story.append(Spacer(1, 10))

# --- 4. What is still missing --------------------------------------------
story.append(Paragraph("4. What is still missing", h1))
story.append(Paragraph(
    "<b>Production, conversion, and freight cost per tonne of product.</b> This is "
    "the most significant open gap. The model currently produces total carbon "
    "compliance cost, meaning CBAM plus maritime ETS plus FuelEU. It does not yet "
    "produce a total delivered cost, because three of the six cost components that "
    "would make up a delivered cost figure have never been assigned to a member of "
    "the group. Production cost in particular is understood from the literature to "
    "be the largest single component of delivered cost, larger than any of the "
    "regulatory charges the model already covers. Until this is resolved, the "
    "dissertation's aim should be described as pricing regulatory compliance cost "
    "rather than total delivered cost, unless the wording of the aims section "
    "already reflects this distinction.",
    body,
))
story.append(Paragraph(
    "<b>Ammonia embedded emissions</b>, pending Riya.",
    body,
))
story.append(Paragraph(
    "<b>Two provisional emissions figures</b> from Riya, Canada green and blue "
    "hydrogen, pending her confirmation.",
    body,
))
story.append(Paragraph(
    "<b>China blue hydrogen production method.</b> Riya's data gives an emissions "
    "figure for this pathway but does not state the production method. It has been "
    "labelled generically pending confirmation, since China's blue hydrogen route "
    "is more likely coal based with carbon capture than the gas based route used "
    "for Canada.",
    body,
))

# --- 5. Quality control ---------------------------------------------------
story.append(Paragraph("5. Quality control performed", h1))
story.append(Paragraph(
    "Three layers of checking are built into the model, rather than trust being "
    "placed in a single run.",
    body,
))
story.append(Paragraph(
    "Eighty one automated tests check the regulatory logic against hand calculated "
    "expected values, including specific tests for the two facts previously "
    "confirmed wrong earlier in this project: the CBAM factor being confused with "
    "the free allocation share, and UK ETS maritime scope being assumed equivalent "
    "to the EU's when it is not.",
    body,
))
story.append(Paragraph(
    "A reproduction test suite checks the model against all 31 figures published in "
    "Gayu's maritime notebooks. All 31 currently reproduce exactly.",
    body,
))
story.append(Paragraph(
    "An external cross check was attempted against Ramsook, Boodlal and Maharaj "
    "(2025), a published study of Trinidad and Tobago's ammonia exports under EU "
    "CBAM. This check does not currently reconcile: the model produces a "
    "substantially higher CBAM burden as a share of export value than the 22% "
    "reported in that paper. The most likely explanation, not yet confirmed, is "
    "that the published figure is measured against total global export revenue "
    "while this model's CBAM cost applies only to the EU bound share. This is "
    "reported honestly in the model's output rather than adjusted until it agrees, "
    "and is flagged as an open item requiring the source paper to be read in full.",
    body,
))

# --- 6. Headline results ---------------------------------------------------
story.append(Paragraph("6. Headline results so far", h1))
story.append(Paragraph(
    "Using currently available data, 2026 shows a pronounced asymmetry: Chinese "
    "hydrogen, despite having roughly twice the embedded emissions of Canadian "
    "hydrogen, faces a carbon compliance cost roughly 37 times lower, because UK "
    "CBAM has not yet started and UK ETS does not price the ocean voyage. By 2030, "
    "this narrows substantially and can invert, as the EU CBAM factor rises "
    "sharply and UK CBAM (modelled here as an upper bound scenario, given the "
    "unresolved phase in question) begins to apply. The asymmetry therefore "
    "appears to be a temporary feature of the current regulatory timeline rather "
    "than a structural one, which is a stronger and more defensible framing for "
    "the discussion chapter than a simple statement of which corridor is cheaper.",
    body,
))

# --- 7. Next steps -----------------------------------------------------
story.append(Paragraph("7. Recommended next steps", h1))
next_steps = [
    "Decide ownership of production, conversion, and shipping cost this week. "
    "Either assign it or formally narrow the dissertation's stated aim to "
    "compliance cost rather than delivered cost.",
    "Follow up with Riya on the ammonia table and the two provisional Canadian "
    "hydrogen figures.",
    "Continue monitoring UK CBAM policy publications for the free allowance "
    "adjustment mechanism referenced in paragraph 3.76 of the government's "
    "consultation response, and update the model once it is published.",
    "Resolve the Ramsook et al. reference check by reading the source paper in "
    "full to confirm or rule out the denominator hypothesis.",
    "Await MCG's HyPACT validation data, requested from Clinton and Jiaqi, "
    "subject to ethics approval sign off.",
]
story.append(ListFlowable(
    [ListItem(Paragraph(step, body), leftIndent=0) for step in next_steps],
    bulletType="1", start="1", leftIndent=18,
))

doc.build(story)
print("wrote CBAM_Model_Status_Report.pdf")
