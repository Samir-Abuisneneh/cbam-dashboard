"""Capture the dashboard's four tabs to `docs/figures/` for the write-up.

The dashboard is the only part of this project that is not reproducible from a
script, so its figures would otherwise be hand-captured and impossible to
regenerate after an input change. This makes them a build step.

Usage, with the dashboard already running:

    .venv/bin/streamlit run dashboard.py --server.port 8511 &
    .venv/bin/python capture_figures.py [--port 8511]

The scenario captured is the study's primary one: the CBAM regulatory default
pathway on the gas carrier, base speed, Suez routing, medium prices. Change
SCENARIO below rather than clicking through the UI, so the captured figures and
the reported numbers cannot drift apart.
"""

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

FIGURES_DIR = Path(__file__).parent / "docs" / "figures"

# Tab labels as they appear in dashboard.py's `st.tabs` call, paired with the
# filename each becomes. Order matters only for readability.
TABS = [
    ("Compliance cost", "dashboard_1_compliance_cost.png"),
    ("Maritime layer only", "dashboard_2_maritime.png"),
    ("Sensitivity", "dashboard_3_sensitivity.png"),
    ("Which pathway / corridor", "dashboard_4_pathway_corridor.png"),
    ("Price forecast", "dashboard_5_price_forecast.png"),
    ("Sourcing optimiser", "dashboard_6_sourcing_optimiser.png"),
]

# The sidebar selections to make before capturing. Left at the dashboard's own
# defaults except where the primary scenario differs.
SCENARIO = {
    "Corridor": "Halifax → Hamburg",
    "Product": "Hydrogen",
    "Production pathway": "CBAM regulatory default",
    "Year": "2030",
    "Carbon price scenario": "Medium",
}

VIEWPORT = {"width": 1600, "height": 1200}


def _settle(page, ms: int = 2500) -> None:
    """Wait for Streamlit to finish its rerun.

    Streamlit streams DOM updates over a websocket, so `networkidle` alone
    returns while the page is still filling in. The explicit wait is crude but
    it is what stops a capture landing mid-render.
    """
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


def capture(port: int) -> list[Path]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    written = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
        page.goto(f"http://localhost:{port}", wait_until="networkidle")
        _settle(page)

        for label, value in SCENARIO.items():
            box = page.get_by_label(label, exact=True)
            if box.count() == 0:
                print(f"  ! no control labelled {label!r}, leaving at default")
                continue
            box.first.click()
            # Scoped to the open listbox rather than get_by_text against the
            # whole page: with six tabs now built, several of them render a
            # plotly chart with an axis tick reading the same text as a
            # scenario value ("2030" on a price-history x-axis, for one),
            # and an unscoped text match can resolve to that instead of the
            # dropdown option, hanging on an element that is never visible.
            page.get_by_role("option", name=value, exact=True).click()
            _settle(page, 1200)

        for label, filename in TABS:
            tab = page.get_by_role("tab", name=label)
            if tab.count() == 0:
                print(f"  ! no tab named {label!r}, skipping")
                continue
            tab.first.click()
            _settle(page)
            path = FIGURES_DIR / filename
            page.screenshot(path=str(path), full_page=True)
            written.append(path)
            print(f"  {path.relative_to(Path(__file__).parent)}")

        browser.close()

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8511)
    args = parser.parse_args()

    print(f"capturing from http://localhost:{args.port}")
    written = capture(args.port)
    if not written:
        print("nothing captured; is the dashboard running on that port?")
        return 1
    print(f"wrote {len(written)} figures to docs/figures/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
