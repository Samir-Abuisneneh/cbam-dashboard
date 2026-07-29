"""Generates CBAM_Model_Status_Report.pdf. Build tooling, not part of the model."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem,
)
from reportlab.lib.enums import TA_LEFT

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
     Paragraph("From Riya, delivered 26 July 2026, both corridors, four pathways "
               "each, all cited to named sources. Two Canadian figures (green and "
               "blue) are provisional; Riya has flagged she may still revise them.",
               cell)],
    [Paragraph("Ammonia embedded emissions", cell),
     Paragraph("<b>Not yet delivered</b>", cell),
     Paragraph("Riya has confirmed the China figures are not yet added. Currently "
               "running on placeholder literature ranges.", cell)],
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
     Paragraph("<b>Unresolved</b>", cell),
     Paragraph("Confirmed unresolved by the UK government itself. The EU CBAM "
               "factor phases in liability from 2.5% in 2026 to 100% by 2034. "
               "Checked directly against the UK government's response to its CBAM "
               "policy design consultation. Paragraph 3.76 states the UK CBAM rate "
               "will be adjusted for free allowances but that government is "
               "continuing to consider options as to how to do this. The mechanism "
               "also appears structurally different from the EU's. Not a research "
               "gap on our side; a live and openly acknowledged gap in UK policy.",
               cell)],
    [Paragraph("GBP to EUR exchange rate", cell),
     Paragraph("<b>Not applied</b>", cell),
     Paragraph("No conversion is performed anywhere in the model. Gayu's notebooks "
               "deliberately report the two corridors in their own currencies "
               "rather than combining them with an assumed rate, and the model "
               "follows the same approach.", cell)],
    [Paragraph("Production, conversion, and shipping cost", cell),
     Paragraph("<b>Not sourced, no owner</b>", cell),
     Paragraph("See Section 4.", cell)],
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
    "<b>The UK CBAM phase in mechanism</b>, pending UK government policy. This "
    "blocks a full, non hypothetical 2027 onward result for the Ningbo to "
    "Felixstowe corridor. The model currently runs this case as a clearly labelled "
    "upper bound scenario rather than reporting it as fact.",
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
