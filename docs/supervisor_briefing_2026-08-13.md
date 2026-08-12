# Technical supervisor briefing, 13 August 2026

Written for the meeting with Josh. Two parts: the questions worth raising, then
the explanation of the code. Every number here was regenerated from the current
repository on 12 August 2026, so it supersedes anything in
`docs/how_the_code_works.md` section 4 and all of `docs/cost_model_formulas.md`.

State of the repo: 216 tests pass, 6,159 lines in `cbam_model`, 24 CSV outputs
and 6 charts in `cbam_model/outputs/`. Model due 16 August.

---

## Part 1. Data questions

Short answer to "do we have data questions": no external blocker remains. Nobody
is waiting on anybody. What is left are five judgement calls, and four of them
are worth Josh's opinion because they are all trade-offs between accuracy and
the three days remaining.

### 1. The UK ETS price is an approximation of the statutory series, not the series

This is the one to lead with. SI 2026/809 regulation 3, implementing Finance Act
2026 s.149(3), defines the price input to the UK CBAM rate as the mean of all UK
ETS auction clearing prices in the preceding quarter. The model uses GBP
49.41/tCO2e, which is an annual mean of UKA December futures settlement prices
from the UK ETS Authority determination. The two track each other closely, so it
is defensible, but they are not the same quantity.

UK ETS auction results are published, so the real quarterly path could be
sourced. Doing it would also close the separate problem that the baseline UK
price is held flat across 2026 to 2030 while the EU price rises 58%.

**Ask:** source the quarterly auction series now, or state it in the methodology
as an approximation of the statutory series and move on? My view is the latter,
because two labelled forward paths already exist alongside the flat baseline
(`linked`, built on EU-UK scheme linkage, and `desnz`, the UK government's own
published traded carbon values), and the ammonia corridor result is identical
under all three.

### 2. The CSCF is assumed at 1.0 and nobody has published a 2026 value

The cross-sectoral correction factor appears in Equations 2 and 6 of IR
2025/2620 and multiplies the free allocation shield. It was 100% every year from
2021 to 2025 and no 2026 figure had been published when this was last checked on
8 August. The code holds it at 1.0, sets `CBAM_CSCF_IS_SOURCED = False`, and
carries that flag into the output files.

**Ask:** is a flagged assumption acceptable here, or does he know where a 2026
value would surface? A CSCF below 1 shrinks the shield and raises every EU CBAM
figure.

### 3. The CBAM benchmarks may be revised before submission

IR 2025/2620 recital 10 says the CBAM benchmarks applying from January 2026 are
built on estimated 2026 to 2030 ETS benchmarks, and must be reviewed within one
month of the final ones appearing, with revised values applying to goods
imported from 1 January 2027. The final ETS benchmarks were published on 29 June
2026, so a revision was due around the end of July. None had appeared on
8 August.

If one lands, the 2027 to 2030 hydrogen benchmark moves and every hydrogen
corridor result moves with it.

**Ask:** how to handle a regulatory change that arrives after the results freeze.
Re-run and re-freeze, or note it as a live risk in limitations?

### 4. Green bunker fuel only changes the FuelEU term, not the ETS term

This is the most technical question of the five. The model has a green bunker
scenario where the vessel burns its own cargo product as fuel. That scenario
changes the FuelEU Maritime intensity penalty, but EU and UK ETS still charge
the voyage's actual CO2 as if the ship were burning VLSFO. The docstring in
`model/total_cost.py` is explicit that this isolates the FuelEU compliance effect
rather than re-modelling the voyage.

It is defensible as a stated boundary, since the maritime layer is Gayu's and her
published figures are VLSFO. But a technical reader could reasonably say the
comparison is incomplete.

**Ask:** leave it as a labelled partial comparison, or is it worth extending the
propulsion emissions to respond to the bunker choice?

### 5. Two production-cost figures are still assembled across separate studies

Canada hydrogen spans three papers and China ammonia spans two. This is Riya's
input rather than mine, and it is already mitigated: every abatement verdict was
recomputed on the IEA cost sheet, which prices all pathways under one
methodology, and on the Ayub et al. costs. Every verdict holds its sign under all
three sourcings, and a test fails if that stops being true.

Worth mentioning only so he hears it from us first. It does not need a decision.

---

## Part 2. Explaining the code

### The one-paragraph version

It is a deterministic calculator, not a simulation and not a forecast. Give it a
corridor, a product, a production pathway, a year and a carbon price scenario,
and it returns what carbon regulation costs to move one tonne of that product
along that corridor in that year. Nothing in it is random, so the same inputs
give the same answer to the last decimal, which is why it can be checked by a
test suite rather than by eyeballing charts.

Two corridors, chosen for regulatory asymmetry rather than convenience. Halifax
to Hamburg sits under EU CBAM, EU ETS Maritime and FuelEU Maritime. Ningbo to
Felixstowe sits under UK CBAM from 2027 and UK ETS Maritime, and carries no
FuelEU cost at all because Felixstowe is outside EU jurisdiction. Two products,
hydrogen and ammonia, so four corridor-product combinations.

### How it is laid out

```
cbam_model/
  config/
    regulatory_constants.py   1,003 lines: every legal figure with its citation
    vessel_logistics.py         292 lines: Gayu's vessel and voyage arithmetic
    scenarios.py                 59 lines: the scenario grid and its labels
    unresolved.py                53 lines: the sentinel that refuses to guess
  model/
    cbam.py                     240 lines: the border charge, EU and UK
    ets_maritime.py             111 lines: the voyage charge, EU and UK
    fueleu.py                   105 lines: the fuel intensity penalty
    total_cost.py               354 lines: joins per-voyage and per-tonne
    switching.py                197 lines: corridor lock-in under contract tenor
  validation/
    unit_checks.py              211 lines: rejects malformed input
    gayu_reproduction.py        232 lines: pins Gayu's published figures
    reference_case.py           264 lines: checks against a published paper
  analysis/
    outputs.py                1,656 lines: results tables and charts
    sensitivity.py              402 lines: what actually drives the answer
  data_io.py                    738 lines: loads and documents the input tables
  runner.py                     242 lines: runs the whole scenario grid
```

Two rules hold everywhere. Every regulatory number lives in
`regulatory_constants.py` and nowhere else, so there is one file to check against
the legislation. And no function invents a value it was not given.

### What happens on a run

Five steps.

**Load and check.** Three CSV inputs: Riya's embedded emissions, Gayu's voyage
logistics, and the commercial table. Before anything reaches a formula,
`unit_checks.py` tests it against the agreed contract. It rejects a distance in
kilometres presented as nautical miles, an emissions column in kilograms
presented as tonnes, a corridor label with a typo, and a fuel total that does not
equal distance times burn rate. A units error produces a plausible answer that is
wrong by a factor of a thousand, and a plausible wrong answer is more dangerous
than a crash.

**Price the voyage.** Gayu's figures give fuel burned, which gives CO2e emitted,
which the two trading schemes charge for. They are not symmetrical, and that
asymmetry is the study's central point. The EU charges half of an international
voyage. The UK charges none of the ocean crossing and all of the time at berth,
so for Ningbo to Felixstowe the entire sea passage is free and only the
Felixstowe port call costs anything.

**Price the border.** Embedded emissions, less the free allocation shield, times
the certificate price, less any carbon price already paid in the producing
country. Canada prices industrial carbon so Canadian cargo arrives with a
deduction. China does not price hydrogen or ammonia production, so Chinese cargo
arrives with none.

**Join the two.** Gayu's costs are per voyage, the border charge is per tonne.
Converting between them needs cargo tonnage, which her original notebooks never
stated because they never needed it. Her cargo capacity notebook of 25 July
supplied it: an 84,000 cubic metre carrier at the IMO 98% filling limit holds
56,142 tonnes of ammonia or 5,828 tonnes of liquid hydrogen. That nine to one
ratio is why hydrogen absorbs so much more shipping cost per tonne.

**Write the outputs.** 24 CSV files and 6 charts covering the cost tables, the
corridor comparison, the sensitivity ranking and the lock-in analysis.

### One number, start to finish

Ammonia, Halifax to Hamburg, regulatory default pathway, 2030, medium carbon
price. The model returns **68.02 euros per tonne**. This is the current figure
under the benchmark mechanism. If anyone quotes 54.67 from the August 7
walkthrough, that is the superseded factor-scaled form.

The voyage: a very large gas carrier covers 2,962 nautical miles at 14.8 knots,
8.3 days at sea, burning 342.8 tonnes of fuel and emitting 1,097.0 tonnes of
CO2e. CO2e bundles methane and nitrous oxide in with the carbon dioxide, and both
schemes have charged all three since 2026.

EU ETS charges half of an international voyage. FuelEU charges the gap between
the ship's actual fuel intensity of 90.8 gCO2e/MJ and the 2030 target of 85.6904,
converted into tonnes of fuel oil equivalent at 2,400 euros each. Spread across
56,142 tonnes of cargo, the whole maritime side comes to **2.06 euros per tonne**.

The border charge:

```
embedded default              1.98 tCO2e/t
default-value mark-up         x 1.01           = 1.9998
free allocation shield        CBAM benchmark 1.522 x (1 - 0.485) x CSCF 1.0
                                               = 0.7838
chargeable                    1.9998 - 0.7838  = 1.2160 tCO2e/t
net certificate price         126.00 - 71.75 (Canadian industrial price)
                                               = 54.25 EUR
CBAM cost                     1.2160 x 54.25   = 65.97 EUR/t
```

Total: 65.97 + 2.06 = **68.02 euros per tonne**.

The proportion carries a finding. By 2030 the border charge is roughly thirty-two
times the shipping charge, where in 2026 it is ten times. The maritime side
matters early and is close to irrelevant by 2030, so any conclusion drawn from a
single year is really a conclusion about that year's position in the phase-in
schedule.

| Year | CBAM per tonne | Maritime per tonne | Total |
|---|---|---|---|
| 2026 | 10.69 | 1.02 | 11.71 |
| 2027 | 16.12 | 1.13 | 17.25 |
| 2028 | 25.58 | 1.24 | 26.83 |
| 2029 | 42.74 | 1.35 | 44.10 |
| 2030 | 65.97 | 2.06 | 68.02 |

### How the code avoids lying

This is the part worth dwelling on with a technical supervisor, because it is the
engineering contribution rather than the economics one. It exists because earlier
drafts got four separate regulatory facts wrong by assuming rather than checking.

**It refuses to guess.** An unsourced value is not set to zero or to something
plausible. It is set to an `Unresolved` object that raises on any arithmetic, any
comparison, even any attempt to test whether it is true. A missing figure stops
the calculation at the exact line that needed it, with a message naming what to
go and look up. Delivered cost is blocked this way: conversion and freight have
no source, so asking for a delivered cost raises rather than returning a number
built on invention.

**It reproduces Gayu's notebooks exactly.** Thirty-four of her published figures
are written into the test suite as expected values, seventeen for the gas carrier,
eleven for the container ships and six for cargo capacity. Change the fuel carbon
factor or the engine load assumption and those tests fail by name, rather than the
model drifting quietly away from the maritime work it is built on.

**It refuses to call a coin flip.** Where a cost is compared against a threshold,
the verdict has three states. Anything within 10% of the line reads `marginal`
instead of pass or fail. That band exists for a concrete case: Chinese green
ammonia comes out 1% below the carbon price, on a figure assembled from two
unrelated papers. As a boolean that is a confident yes. Honestly reported it is a
coin flip.

**It keeps currencies apart.** EU costs in euros, UK costs in pounds, nothing
converts silently. Where a chart needs one axis the column is named
`gbp_equivalent` and the rate is a single fixed ECB reference rate from 23 July
2026, held constant across the horizon. That is a real limitation and it bites
hardest where the two corridors sit close together.

**It labels what is not law.** Two of the three UK price paths are scenarios
rather than legislation, and the proposed extension of the UK scheme to
international voyages is a consultation that never passed. Each carries its
status in its own label, and a test fails if a new scenario is added without one.

### What it deliberately does not do

Say this before he asks.

It does not produce a delivered cost. Production cost is real, from Riya's
literature review. Conversion and freight are not sourced and have no owner, so
they are a declared scope boundary rather than a pending input. Both terms are
invariant to production pathway, so they cancel out of every within-corridor
comparison the study actually makes.

It does not optimise. No solver, nothing being searched. Where it picks a
cheapest pathway it is ranking a handful of routes that exist in the literature.
Calling it an optimisation model would overclaim.

It does not forecast prices. The carbon price scenarios are a bracket, not a
distribution, and no probability attaches to any of them.

It does not model a real liquid hydrogen ship, because no commercial fleet
exists. The hydrogen figures apply an ammonia carrier's geometry to hydrogen on
purpose, to isolate what cargo density alone does to cost per tonne. That is a
counterfactual and is labelled as one.

### The correction that cost us three findings

Worth volunteering rather than being caught by. Until 8 August the model netted
off the **EU ETS product benchmark** when computing the free allocation shield.
That is the wrong instrument. IR 2025/2620 defines a distinct **CBAM benchmark**,
derived from the ETS benchmarks but not equal to them.

| Good | EU ETS benchmark | CBAM benchmark |
|---|---|---|
| Ammonia | 1.522 | 1.522 |
| Hydrogen | 7.98 | 5.089 |

Ammonia is unaffected, so every ammonia figure survived. Hydrogen was being
shielded by 56.8% more than the law allows, so EU hydrogen liability was
understated in every year. Correcting it killed three findings outright:
hydrogen's corridor crossover, hydrogen's lock-in reversal, and the finding that
absolute cost and competitive exposure pointed in opposite directions. All three
are recorded as dead in `docs/findings_2026-08-08.md` and guarded by tests that
fail if any returns.

The honest framing is that the most counterintuitive result the model produced
turned out to be an artefact, and what replaced it is simpler and more
defensible but less interesting.

### Current headline results

2030, medium prices, regulatory default pathway:

| | Halifax-Hamburg | Ningbo-Felixstowe |
|---|---|---|
| Ammonia | GBP 58.03 | GBP 71.07 |
| Hydrogen | GBP 546.63 | GBP 434.41 |

**Ammonia** is the robust result. Ningbo-Felixstowe is cheaper in 2026 alone,
because UK CBAM has not started. Halifax-Hamburg leads from 2027 and holds it.
That ordering is identical under all three UK price paths and under both CBAM
mechanisms, so no qualification is needed.

**Hydrogen** needs its price path named every single time. Ningbo-Felixstowe is
cheaper in every year on `frozen` and `desnz`, with no crossover at all. On
`linked`, Halifax-Hamburg leads from 2027 instead. And `linked` is a scenario,
not law.

**Lock-in** is the piece Frano rated the main contribution, and it now rests on
ammonia alone. Deciding in 2026, at 8% real over a ten-year tenor, the
spot-cheapest corridor is the wrong commitment: regret is 33.5% and breakeven is
GBP 38.72 per tonne of annual contracted volume. The reversal survives both
beyond-horizon treatments in the same direction, so it is not an artefact of the
extrapolation assumption. No switching cost is claimed. The finding is the
threshold, and `docs/switching_cost_evidence.md` argues real corridor-specific
sunk costs plausibly sit above it.

### Two documents that used to contradict this one

Both were fixed on 12 August, so the whole docs set now agrees. Noted here only in
case an older copy is circulating.

`docs/cost_model_formulas.md` printed the EU CBAM obligation in the factor-scaled
form the model abandoned on 7 August, and its line citations into the code had
drifted. It now carries the benchmark form, the CSCF term, the CBAM benchmark
values, the `factor_scaled` variant labelled as superseded, and corrected
citations throughout. The UK section now cites SI 2026/809 rather than the draft
regulations, and carries the price-basis and direct-only caveats.

`docs/how_the_code_works.md` section 4 arrived at 54.67 euros for the worked
example, because it was written before the mechanism switch. It now arrives at
68.02 with the shield shown step by step, and a new section 4a explains the
benchmark correction and the three findings it killed.

If anyone on the team quotes 54.67 or the factor-scaled formula, they have an old
copy.

### Running it

```bash
.venv/bin/python -m pytest -q           # 216 tests
.venv/bin/jupyter lab run_model.ipynb   # the whole thing end to end
.venv/bin/streamlit run dashboard.py    # the point and click version
```

The dashboard is the thing to open if he wants to see it rather than read it.
Four tabs, live recalculation, and it calls the same tested functions the
notebook does so it cannot drift from the model. Anything policy-uncertain is
labelled on screen rather than presented as a forecast.
