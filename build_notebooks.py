"""Generates run_model.ipynb. Run once, then work in the notebook.

Build tooling, not part of the model.
"""

from pathlib import Path

import nbformat as nbf

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

The UK price has three variants and they are not interchangeable. `frozen` holds the sourced 2026
official determination flat across every year; it is the baseline and is conservative rather than
correct, since only one year was ever sourced. `linked` runs the EU-UK ETS linkage scenario, under
which the UK price converges on the EU price by 2029. `desnz` runs the UK government's own published
traded carbon values, the only forward UK path here with an official source behind it.

Two things must travel with the last two. Linkage is NOT law, so it may only ever appear as a
labelled scenario. And the DESNZ series is in **real 2025 prices** while every other price in the
model is nominal, DESNZ states plainly that these are scenario projections rather than forecasts,
and they model a standalone UK ETS that explicitly does not account for EU linking. `desnz` and
`linked` are therefore alternative views of the same uncertainty and must never be combined.
"""),
    code("""
pd.DataFrame([
    {'year': y, 'scenario': s,
     'eu_ets_eur_per_tco2e': rc.eu_ets_price(y, s),
     **{f'uk_ets_gbp_{v}': rc.uk_ets_price(y, s, v) for v in rc.UK_ETS_PRICE_VARIANTS}}
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
    ['corridor', 'vessel_class', 'voyage_co2_t', 'currency',
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
              & (maritime['vessel_set'] == 'gas_carrier')]
uk[['route_scenario', 'distance_nm', 'voyage_co2_t', 'port_co2_t', 'uk_ets_cost_gbp']]
"""),
    md("""
## 5. CBAM liability per tonne of product

Separate layer, separate unit. Embedded emissions are Riya's real sourced figures for both products
and both corridors, not placeholders, as of her 4 August 2026 delivery.

The UK CBAM phase-in was the last open regulatory item here and it is now resolved from primary
legislation. There is no flat "UK CBAM rate": it is `UK ETS price x (1 - baseline free allocation %
x Article 16(14) factor)`, from the draft CBAM (Calculation of CBAM Rate and Determination of Carbon
Price Relief) Regulations 2026 and Finance Act 2026 s.149(4). That works out at 15.7% of the UK ETS
price in 2027 rising to 33.0% by 2030. Nothing is skipped any more; the skip warning below only fires
if a not-yet-sourced constant is added later.
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

Halifax–Hamburg grey hydrogen pays about €57.26 per tonne in total carbon compliance, which is £48.85 at
the 23 July 2026 ECB reference rate. Ningbo–Felixstowe hydrogen from coal gasification, at twice the
embedded emissions, pays about £0.50.

The dirtier product on the longer route pays roughly ninety-seven times less, purely because UK CBAM has
not started and UK ETS does not price the ocean leg. That is the regulatory asymmetry stated per tonne.

Both figures are converted to one currency before the ratio is taken. Comparing the €57.26 against the
£0.50 directly would quote a ratio across two currencies, which is the one thing the rest of this model
is careful never to do.

### And what 2030 shows

The cell below runs UK CBAM at 100% of the UK ETS price. That is deliberately **not** the model's
baseline: the real rate fraction is now sourced and reaches only 33.0% by 2030 (see section 5). It is
an upper-bound what-if, and it is kept because it brackets the corridor comparison from the direction
that is least favourable to the UK corridor. Read `run_compliance_matrix()` without the override for
the legislated figures.

Either way the picture inverts. CBAM grows to dominate everything and the maritime terms become close
to irrelevant, and Chinese coal-gasification hydrogen becomes the most exposed product in the study.

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

The alternative form, `embedded x CBAM_factor`, gives 14.5% on the same inputs. Both stay implemented and
sit side by side in `validation/reference_case.py`, with a test that fails if the default moves without
anyone noticing.

**The model was switched to the benchmark form on 7 August 2026**, and the benchmark it uses was
corrected on 8 August 2026. The correction is the more important of the two.

Until 8 August the model netted off the **EU ETS product benchmark** (ammonia 1.522, hydrogen 7.98,
IR 2026/1412). That is the wrong instrument. Commission Implementing Regulation (EU) 2025/2620 of
16 December 2025, adopted under Article 31(2), sets out the calculation directly and defines its own
**CBAM benchmark**: ammonia 1.522, the same figure, but hydrogen **5.089**. The model had been shielding
hydrogen by 56.8% more than the law allows, understating EU hydrogen liability in every year. The same
regulation supplies a cross-sectoral correction factor term that was missing entirely; it is now
represented and held at 1.0 as a stated assumption rather than a sourced value.

That regulation also settles the functional form. Its `CBAM_y` is the share of free allocation still
remaining, which is `1 - cbam_factor(year)` in this model's terms, so the factor-scaled reading is
confirmed wrong rather than merely disfavoured, whatever practitioner guidance describes.

What remains for the write-up is presentation, not correctness. The switch changes headline findings
rather than rescaling them, as section 6 shows, and it has not been confirmed by the supervisor. The
methodology chapter has to state which form was used and why, and report both.
`outputs.cbam_mechanism_comparison` below sizes exactly what changes.
"""),
    code("""
outputs.cbam_mechanism_comparison(emissions).query("price_scenario == 'medium'")[
    ['product', 'pathway', 'year', 'embedded_emissions_tco2e_per_tonne',
     'benchmark_tco2e_per_tonne', 'cleaner_than_benchmark',
     'factor_scaled_eur_per_tonne', 'benchmark_shielded_eur_per_tonne', 'ratio']]
"""),
    code("""
print(reference_case.format_reference_check(reference_case.run_reference_check()))
"""),
    md("""
## 8b. Choice and timing

Not an optimisation - a ranking over the small set of pathways/corridors the literature actually supports.
Answers "which one, and when," not "what does it cost."
"""),
    code("""
ranking = outputs.pathway_cost_ranking(emissions, commercial)
ranking[ranking.is_cheapest][['corridor', 'product', 'pathway', 'pathway_visible_cost_eur_per_tonne']]
"""),
    md("""
Cheapest pathway is production cost + CBAM only (conversion/shipping/maritime are pathway-invariant so they
cancel out of the ranking - see the function docstring for the caveat on why that cancellation could break).
At 2030 medium prices the dirtiest route wins everywhere, and stays cheapest under low/medium/high prices too
(`pathway_choice_price_robustness` below) - CBAM does not change the commercial choice.
"""),
    code("""
outputs.pathway_choice_price_robustness(emissions, commercial)
"""),
    code("""
outputs.corridor_crossover_year(compliance)
"""),
    md("""
The two products no longer behave the same way, and that split is a direct consequence of the free
allocation mechanism selected in section 8.

**Ammonia** follows the pattern the earlier drafts described. Ningbo-Felixstowe is cheaper only in 2026,
because UK CBAM does not exist yet; the ordering flips in 2027, the year it starts, and stays flipped.
One flip, not a slow overtake.

**Hydrogen** does not flip at all. Ningbo-Felixstowe is cheaper in every year from 2026 to 2030 and there
is no crossover on the baseline UK price path. The reason is the benchmark shield: the CBAM hydrogen
benchmark is 5.089 tCO2e per tonne against Canadian grey hydrogen's 10.07, so roughly half the embedded
emissions are chargeable from the start, and the chargeable share grows as free allocation is withdrawn.
EU liability therefore climbs steeply while the UK rate fraction climbs far more slowly.

On the `linked` UK price path, which is explicitly not law, Halifax-Hamburg takes the lead in 2027 and
holds it, because a UK price converging upward on the EU price raises UK CBAM enough to reverse the
ordering. So every hydrogen corridor claim has to name the price path it is on.

Two superseded versions of this paragraph are quoted in documents written before 8 August 2026. Under the
factor-scaled form hydrogen followed the ammonia pattern and never reverted. Under the benchmark form with
the EU ETS benchmark wrongly netted off, hydrogen flipped to Halifax-Hamburg in 2027 and back from 2028.
Neither survives the benchmark correction.
"""),
    code("""
outputs.abatement_breakeven_year(emissions, commercial)
"""),
    md("""
Check `carbon_price_varies_by_year` before reading a UK row: the UK ETS price is frozen (only 2026 was ever
sourced), so a UK pathway showing no breakeven year is an artefact of that, not evidence switching never pays.
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

_Counts below are printed rather than typed, so this section cannot go stale the way an earlier
version of it did._

**Solid.** The maritime layer is complete and carries no invented inputs, and every one of Gayu's
published figures reproduces exactly. Embedded emissions and production costs are Riya's real sourced
figures for both products and both corridors. The UK ETS price anchor is an official determination and
the UK CBAM rate is traced through primary legislation. The regulatory logic is pinned by the test
suite, including the specific facts this project has previously got wrong.

**Resolved since the first build.** UK ETS price anchors. Cargo tonnage, from Gayu's capacity
notebook, which is what lets compliance cost per tonne run end to end. Riya's emissions and production
costs. The UK CBAM rate mechanism. The GBP/EUR, CAD/EUR and USD/EUR reference rates. Canada's revised
industrial carbon price path. The 2026-2030 EU ETS product benchmarks. The Ramsook cross-check, which
reconciles once the benchmark form of the obligation is used.

**Still open.**

1. **Production, conversion and freight cost per tonne.** Production cost is now real; conversion and
   freight still have no owner, and they are the only thing standing between compliance cost and full
   delivered cost.
2. **Supervisor confirmation of the EU CBAM free-allocation mechanism.** The model moved to
   `benchmark_shielded` on 7 August 2026 and section 8 gives the reasoning, but that is Samir's
   decision and Frano has not yet ruled on it. It is the one open item that changes a headline
   result rather than adding one. Both forms stay implemented so the decision can be reversed by
   one constant. Note that IR 2025/2620 settles which form the law requires; what is owed is a
   ruling on how to present it, not on which is correct.
3. **Whether IR 2025/2620 has been amended since 29 June 2026.** Its recital 10 requires the CBAM
   benchmarks to be reviewed within one month of the final 2026-2030 EU ETS benchmarks being
   published, with updated values applying to goods imported from 1 January 2027. No amending
   regulation was found on 8 August 2026. If one appears, the 2027-2030 hydrogen benchmark moves
   and every corridor result moves with it.
"""),
    code("""
print(f"Gayu figures reproduced: "
      f"{len(gayu_reproduction.check_gas_carrier()) + len(gayu_reproduction.check_container_ship()) + len(gayu_reproduction.check_cargo_capacity())}")
print(f"EU CBAM mechanism in use: {rc.EU_CBAM_DEFAULT_MECHANISM}")
print(f"CBAM benchmarks: {rc.CBAM_BENCHMARK_TCO2E_PER_TONNE} "
      f"({rc.CBAM_BENCHMARK_SOURCE}, retrieved {rc.CBAM_BENCHMARK_RETRIEVED})")
print(f"CSCF: {rc.cbam_cscf(2026)} (sourced={rc.CBAM_CSCF_IS_SOURCED})")
print(f"Placeholder inputs remaining: {data_io.using_placeholder_data()}")
"""),
]

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}
nbf.write(nb, ROOT / "run_model.ipynb")
print("wrote run_model.ipynb")
