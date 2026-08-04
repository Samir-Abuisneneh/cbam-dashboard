"""Generates run_model.ipynb. Run once, then work in the notebook.

Build tooling, not part of the model.
"""

import nbformat as nbf
from pathlib import Path

ROOT = Path(__file__).parent


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md("""
# CBAM Corridor Cost Model
### Halifax–Hamburg and Ningbo–Felixstowe, hydrogen and ammonia

Two corridors sit under different carbon regimes in the same calendar year, and that asymmetry is what
the study is about:

- **Halifax → Hamburg** falls under EU CBAM (live since 1 January 2026), EU ETS Maritime, and FuelEU Maritime.
- **Ningbo → Felixstowe** falls under UK CBAM, which does not begin until 1 January 2027, and UK ETS Maritime,
  which covers only time spent physically in a UK port. The ocean crossing carries no UK carbon liability at all.

Every maritime figure here comes from Gayu's notebooks. Nothing has been substituted, rounded differently,
or filled in. Section 1 checks that by reproducing her published outputs before anything is built on top.

The model works in two layers. Gayu's maritime costs are per voyage; CBAM liability is per tonne of
product, because embedded emissions are expressed per tonne. Her cargo capacity notebook supplies the
tonnage that joins them, so **total carbon compliance cost per tonne is now computable**.

Full delivered cost is not, because production, conversion and freight cost still have no owner.
"""),
    code("""
import warnings
import pandas as pd

from cbam_model import data_io, runner
from cbam_model.analysis import outputs, sensitivity
from cbam_model.config import regulatory_constants as rc
from cbam_model.config import vessel_logistics as vl
from cbam_model.validation import gayu_reproduction, reference_case

pd.set_option('display.max_colwidth', None)
pd.set_option('display.width', 200)
"""),
    md("""
## 1. Reproducing Gayu's notebooks

Distances, voyage time, fuel burn, CO2, and the EU ETS, UK ETS and FuelEU costs that follow. If any of
these stop matching, a shared assumption has moved and nothing downstream should be trusted until it is
understood.
"""),
    code("""
print(gayu_reproduction.format_report())
"""),
    md("""
## 2. What comes from where

Gayu's figures supersede the original build spec wherever the two disagree, and in one place the spec was
badly wrong.

| quantity | build spec | Gayu | effect |
|---|---|---|---|
| Halifax–Hamburg distance | ~6,300 nm | **2,962 nm** | spec overstated Atlantic voyage emissions by >2x |
| Ningbo–Felixstowe (Suez) | ~11,200 nm | 10,403 nm | minor |
| Cape of Good Hope diversion | +3,500 nm | +4,412 nm | minor |
| VLSFO carbon factor | 3.114 tCO2/t | 3.151 tCO2/t | IMO MEPC 82/6/38 |
| EU ETS 2026 price | 65 / 82 / 126 | **70 / 80 / 90** | the spec's figures were a 2030 forecast |

Her FuelEU calculation divides the compliance deficit by the actual GHG intensity, which is what Annex IV
Part B requires. The build spec omitted that divisor and would have overstated the penalty by roughly
ninety times.
"""),
    code("""
emissions, logistics, commercial = data_io.load_inputs()
logistics[['corridor', 'vessel_class', 'route_scenario', 'distance_nm', 'voyage_days',
           'voyage_co2_t', 'port_in_port_emissions_t']]
"""),
    md("""
## 3. Carbon prices

The two regimes are priced from different sources and on different bases, so they are never combined.

**EU ETS.** Two anchor years. 2026 is ESMA's near-term market range, from Gayu. 2030 is the consensus
forecast aggregating Bloomberg, ABN Amro, Refinitiv, ICIS, S&P Global, Aurora and the Potsdam Institute.
Applying a near-term price to 2030, or a 2030 forecast to 2026, would both be wrong, so the model
interpolates between them.

**UK ETS.** £49.41/tCO2e, the UK ETS Authority determination for the scheme year beginning 1 January 2026.
It is formally the civil-penalty price, but it is calculated from twelve months of 2026 UKA December
futures settlement prices, so it is market-derived rather than administrative. The £40 and £60 figures
bracket it as a sensitivity range and are not forecasts.

Headline tables keep the two currencies apart, as Gayu's notebooks do. A GBP/EUR rate is now sourced
(ECB, 23 July 2026) and is applied only where a single-currency comparison is explicitly labelled.

The UK price has two variants. `frozen` holds the sourced 2026 official determination flat across
every year, which is the baseline and is conservative rather than correct: only one year was ever
sourced. `linked` runs the EU-UK ETS linkage scenario, under which the UK price converges on the EU
price by 2029. Linkage is NOT law, so it may only ever appear as a labelled scenario.
"""),
    code("""
pd.DataFrame([
    {'year': y, 'scenario': s,
     'eu_ets_eur_per_tco2e': rc.eu_ets_price(y, s),
     'uk_ets_gbp_frozen': rc.uk_ets_price(y, s, 'frozen'),
     'uk_ets_gbp_linked': rc.uk_ets_price(y, s, 'linked')}
    for y in rc.CBAM_FACTOR if y <= 2030 for s in rc.PRICE_SCENARIOS
])
"""),
    md("""
## 4. Maritime carbon cost per voyage

Run across Gayu's own scenario dimensions rather than collapsed to a single base case: three speed
scenarios for the gas carrier, both routings for the UK corridor, and both vessel sets.
"""),
    code("""
maritime = runner.run_maritime_matrix()
print(f"{len(maritime)} voyage scenarios.")
outputs.maritime_summary(maritime)
"""),
    md("""
### The asymmetry, without needing cargo tonnage

Dividing what each corridor pays by what it actually emits gives a like-for-like comparison that does not
depend on any missing input. The corridors remain in their own currencies.

This is the central finding stated as a number. Halifax–Hamburg is the shorter route and emits roughly a
third as much CO2, yet it pays around seventy times more per tonne emitted, because it sits inside a live
regulatory regime and the other does not.
"""),
    code("""
eff = outputs.carbon_cost_per_tonne_co2(maritime)
eff[(eff['year'] == 2026) & (eff['price_scenario'] == 'medium')
    & (eff['speed_scenario'].isin(['base', 'service']))
    & (eff['route_scenario'] == 'suez')
    & (eff['uk_ets_variant'].isin(['n/a', 'current_scope']))][
    ['corridor', 'vessel_set', 'voyage_co2_t', 'currency',
     'cost_in_own_currency', 'effective_cost_per_tonne_co2']]
"""),
    md("""
### The Red Sea diversion costs nothing under current UK rules

Rerouting Ningbo–Felixstowe via the Cape of Good Hope adds 4,412 nm and raises voyage emissions by about
42%, and changes the UK carbon bill by exactly zero, because UK ETS does not price the ocean leg. That is
a concrete illustration of how narrow the current UK scope is.
"""),
    code("""
uk = maritime[(maritime['corridor'] == rc.NINGBO_FELIXSTOWE)
              & (maritime['year'] == 2026) & (maritime['price_scenario'] == 'medium')
              & (maritime['speed_scenario'] == 'base')
              & (maritime['vessel_set'] == 'VLGC/VLAC')]
uk[['route_scenario', 'distance_nm', 'voyage_co2_t', 'port_co2_t', 'uk_ets_cost_gbp']]
"""),
    md("""
## 5. CBAM liability per tonne of product

Separate layer, separate unit. Still running on placeholder embedded emissions pending Riya's table.

One regulatory item remains unresolved: whether UK CBAM applies its own phase-in factor from 2027,
analogous to the EU schedule that starts at 2.5% in 2026, or charges the full amount from day one. The gap
between those two readings is wide, so the affected cases are skipped rather than guessed.
"""),
    code("""
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    cbam_results = runner.run_cbam_matrix(emissions)
    for w in caught:
        print(w.message)

outputs.cbam_summary(cbam_results)[
    ['year', 'corridor', 'product', 'pathway', 'embedded_emissions_tco2e_per_tonne',
     'currency', 'cbam_cost_in_own_currency']]
"""),
    md("""
## 6. Joining the layers: compliance cost per tonne

Gayu's cargo capacity notebook closes the gap between the two units. An 84,000 m³ carrier at the IGC Code
98% filling limit gives 82,320 m³ usable, which is **56,142 tonnes of ammonia or 5,828 tonnes of liquid
hydrogen**, a ratio of 9.6 to 1.

Every input is sourced: capacity from the same peer-reviewed vessel study already used for speed and port
time, the filling limit from IMO regulation, ammonia density from the NIH chemistry database, and hydrogen
density corroborated by a second peer-reviewed paper.

One caveat to carry into the write-up. An 84,000 m³ ammonia carrier runs at about -33°C and cannot
physically hold liquid hydrogen, which needs -253°C. The largest liquid hydrogen vessel built is 1,250 m³
and designs under development are around 40,000 m³. Applying the ammonia carrier's geometry to hydrogen
is a deliberate counterfactual that isolates the effect of cargo density by holding the vessel constant.
It should be labelled as such rather than presented as a shipping option available today.
"""),
    code("""
print(f"Usable volume:  {vl.USABLE_VOLUME_M3:,.0f} m3 "
      f"({vl.VESSEL_CUBIC_CAPACITY_M3:,} x {vl.FILLING_LIMIT_FRACTION:.0%} IGC filling limit)")
for product, tonnes in vl.CARGO_TONNES.items():
    print(f"{product:<9} {tonnes:>7,} t per voyage  "
          f"(at {vl.DENSITY_KG_PER_M3[product]} kg/m3)")

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    compliance = runner.run_compliance_matrix(emissions)
    for w in caught:
        print(w.message)
"""),
    md("""
### Total compliance cost per tonne, 2026

This is the dissertation's central question answered in its proper unit. Currencies stay separate.
"""),
    code("""
v = compliance[(compliance['year'] == 2026) & (compliance['price_scenario'] == 'medium')]
v[['corridor', 'product', 'pathway', 'currency', 'cbam_cost_per_tonne',
   'eu_ets_cost_per_tonne', 'fueleu_cost_per_tonne', 'uk_ets_cost_per_tonne',
   'total_compliance_cost_per_tonne']]
"""),
    md("""
### What 2026 shows

Halifax–Hamburg grey hydrogen pays about €18.35 per tonne in total carbon compliance. Ningbo–Felixstowe
hydrogen from coal gasification, at nearly twice the embedded emissions, pays about £0.50.

The dirtier product on the longer route pays roughly thirty-seven times less, purely because UK CBAM has
not started and UK ETS does not price the ocean leg. That is the regulatory asymmetry stated per tonne.

### And what 2030 shows

Run with UK CBAM assumed at 100%, which is a labelled what-if since the phase-in factor is unresolved, the
picture inverts. CBAM grows to dominate everything and the maritime terms become close to irrelevant.
Chinese coal-gasification hydrogen becomes the most exposed product in the study.

The asymmetry is therefore a window, not a permanent feature. Worth saying plainly in the discussion.
"""),
    code("""
whatif = runner.run_compliance_matrix(
    emissions, uk_cbam_rate_override=1.0, skip_unresolved=False)
w2030 = whatif[(whatif['year'] == 2030) & (whatif['price_scenario'] == 'medium')
               & (whatif['uk_ets_variant'].isin(['n/a', 'current_scope']))]
w2030[['corridor', 'product', 'pathway', 'currency',
       'embedded_emissions_tco2e_per_tonne', 'cbam_cost_per_tonne',
       'maritime_cost_per_tonne', 'total_compliance_cost_per_tonne']]
"""),
    md("""
### Delivered cost is still blocked

The blocker has moved, though. Cargo tonnage has landed. What is missing now is the commercial side.
"""),
    code("""
try:
    runner.run_delivered_cost()
except Exception as exc:
    print(exc)
"""),
    md("""
## 7. Which assumption actually drives the maritime result

Each input varied by plus and minus 20% with everything else held constant. Run on the maritime layer only,
since that is the layer built entirely from sourced data.

Two results worth carrying into the write-up:

**FuelEU intensity dominates the EU corridor**, and by a lot more than 20%. The penalty is zero below the
threshold and rises steeply above it, so the response is strongly non-linear and a modest change in assumed
fuel quality swings the cost far more than a modest change in carbon price does.

**Port time is the only lever that matters on the UK corridor.** Speed and fuel intensity move it by
nothing at all, because neither affects time at berth, which is the only thing UK ETS prices.
"""),
    code("""
sweep = pd.concat([sensitivity.sweep_corridor(c) for c in rc.CORRIDORS], ignore_index=True)
ranked = sensitivity.rank_drivers(sweep)

(ranked.groupby(['corridor', 'parameter'])['mean_abs_pct_change']
       .mean().unstack(0).round(2)
       .sort_values('halifax_hamburg', ascending=False))
"""),
    md("""
## 8. External cross-check

Ramsook, Boodlal and Maharaj (2025) put Trinidad and Tobago's ammonia CBAM burden at roughly 22% of export
revenue by 2034. The paper has since been read directly, which settled two questions that were open when
this check was first written. The burden is measured against EU-bound revenue only, not total export
revenue. And reproducing their figure needs the benchmark form of the CBAM obligation,
`max(0, embedded - benchmark x (1 - CBAM_factor))`, which lands at 20.7% against their published 22%.

The form this model currently uses, `embedded x CBAM_factor`, gives 14.5% on the same inputs. Both sit side
by side in `validation/reference_case.py` with a test that fails if the main one is switched without anyone
noticing. Switching is an open decision, waiting on the revised 2026-2030 EU ETS benchmarks adopted on
29 June 2026.
"""),
    code("""
print(reference_case.format_reference_check(reference_case.run_reference_check()))
"""),
    md("""
## 9. Outputs
"""),
    code("""
written = outputs.write_all(maritime, cbam_results, sweep, ranked, compliance,
                            emissions=emissions, commercial=commercial)
for name in written:
    print(f"cbam_model/outputs/{name}")
"""),
    md("""
## Where this stands

**Solid.** The maritime layer is complete and carries no invented inputs. All 25 of Gayu's published
figures reproduce exactly. The UK ETS price anchor is resolved from an official determination. The
regulatory logic is pinned by 72 tests, including the three facts this project has previously got wrong.

**Resolved since the first build.** UK ETS price anchors, from the official 2026 determination. Cargo
tonnage, from Gayu's capacity notebook. Compliance cost per tonne now runs end to end.

**Blocked on other people.**

1. **Embedded emissions**, from Riya. The CBAM layer runs on placeholders, and by 2030 CBAM dominates every
   other term, so this is now the largest source of uncertainty in the study. The origin carbon price
   column matters most: Canada prices industrial carbon and China prices it lower, and a large enough
   Canadian price would cut Halifax-Hamburg's CBAM liability sharply.
2. **Production, conversion and freight cost per tonne.** No owner assigned. The only thing standing
   between compliance cost and full delivered cost.
3. **The UK CBAM phase-in factor.** Blocks the 2027-onward UK cases and drives the entire 2030 comparison.
4. **The Ramsook cross-check**, which does not reconcile and needs the paper read.
"""),
]

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}
nbf.write(nb, ROOT / "run_model.ipynb")
print("wrote run_model.ipynb")
