# CBAM Corridor Cost Model

Deterministic techno-economic model comparing the delivered cost of hydrogen and
ammonia along two maritime corridors under two different carbon regimes.

- **Halifax to Hamburg**: EU CBAM, EU ETS Maritime, FuelEU Maritime.
- **Ningbo to Felixstowe**: UK CBAM (from 2027), UK ETS Maritime. No FuelEU.

Student 3 deliverable (Samir Abuisneneh), MSc Data Science for Business,
University of Bristol, 2026.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install pandas numpy matplotlib plotly pytest searoute nbformat jupyter streamlit

.venv/bin/jupyter lab run_model.ipynb   # the main run
.venv/bin/python -m pytest tests/ -q    # 81 tests
.venv/bin/streamlit run dashboard.py    # interactive scenario explorer
```

`run_model.ipynb` is the entry point and produces everything end to end.
Outputs land in `cbam_model/outputs/`: the long-format scenario table, a
compliance cost table, a corridor comparison, the sensitivity sweep and three
charts.

`dashboard.py` is a Streamlit UI over the same fixed scenario matrix, for MCG
to explore interactively (pick corridor, product, pathway, year, price/vessel/
route scenario) without reading CSVs or running the notebook. It calls
`cbam_model` live, so it can never drift from the tested regulatory logic. It
does not accept arbitrary routes or ports — only the two corridors already
built and covered by the test suite. Placeholder inputs (ammonia emissions,
commercial costs) are flagged in the UI, and the UK CBAM phase-in factor is
exposed as an explicitly-labelled what-if slider rather than a silent
assumption, since it is still unresolved in UK law.

### Why the library is .py and the entry point is .ipynb

The runnable model is a notebook, matching how the rest of the group works. The
modules under `cbam_model/` stay as `.py` because notebooks cannot be imported
as modules: the notebook imports them, and so does the test suite. Splitting it
this way is what lets the regulatory logic be tested at all.
`build_notebooks.py` regenerates `run_model.ipynb` and is tooling rather than
part of the model.

## Maritime inputs come from Gayu

Distances, vessel specifications, fuel burn, voyage CO2 and the resulting EU ETS,
UK ETS and FuelEU costs all come from Gayu's notebooks (Student 2, received
25 July 2026). `validation/gayu_reproduction.py` holds her published figures as
literal expected values and checks that this model reproduces all 31 of them, so
divergence shows up as a test failure rather than quiet drift.

Her figures supersede the build spec wherever the two disagree. The largest
correction is the Atlantic distance: the spec said roughly 6,300 nm for
Halifax-Hamburg, and the actual SeaRoute figure is **2,962 nm**. The spec was
overstating that corridor's voyage emissions by more than a factor of two. Suez
routing for Ningbo-Felixstowe moves from 11,200 to 10,403 nm, the Cape diversion
from +3,500 to +4,412 nm, and the VLSFO carbon factor from 3.114 to 3.151
tCO2/t.

## Two layers, now joinable

Gayu's maritime costs are **per voyage**. CBAM liability is **per tonne of
product**. Her cargo capacity notebook supplies the tonnage that converts
between them, so **total carbon compliance cost per tonne now runs end to end**.

An 84,000 m3 carrier at the IGC Code 98% filling limit gives 82,320 m3 usable,
which is **56,142 t of ammonia or 5,828 t of liquid hydrogen**, a ratio of 9.6
to 1. Every input is sourced: capacity from the same peer-reviewed vessel study
already used for speed and port time, the filling limit from IMO regulation,
ammonia density from the NIH chemistry database, hydrogen density corroborated
by a second peer-reviewed paper.

Currencies are still never converted anywhere, matching how Gayu presents her
tables.

### An implementation bug found and fixed, 29 July 2026

`run_cbam_matrix()` and `cbam_cost_per_tonne()` applied the IR 2025/2621
10/20/30 percent default-value mark-up to every emissions row in a run, using
one `using_default_values` flag for the whole batch. The mark-up is only
supposed to apply to the `cbam_default` pathway, never to literature-sourced
pathways (green electrolysis, grey SMR, blue SMR+CCS, coal gasification) —
`data_io.py`'s own docstring already said as much, but the code didn't enforce
it. Fixed so `using_default_values` is now derived per row from
`pathway == "cbam_default"` unless explicitly overridden.

This changes literature-pathway **EU CBAM** figures (Halifax-Hamburg) by the
mark-up percentage for that year: about 9% too high in 2026 before the fix,
growing toward 30% too high from 2028 onward. **UK CBAM figures were never
affected** — `uk_cbam_cost()` has no mark-up concept at all and never took a
`using_default_values` argument, bug or no bug. `cbam_model/outputs/*.csv` and
the headline figures below are regenerated under the fix.

### Headline results, medium price scenario

Following Riya's proposal of 29 July 2026: the **primary scenario** for each
pathway is anchored on the CBAM regulatory default embedded-emissions value
(the `cbam_default` pathway) where one exists, since IR 2025/2621 sets these
deliberately conservatively to penalise not using verified actual data.
Literature-sourced pathways bracket it as sensitivity scenarios (green
electrolysis = low, grey SMR / coal gasification = high). Ammonia has CBAM
regulatory defaults on both corridors (1.98 tCO2e/t Canada, 4.36 China),
delivered by Riya on 3 August 2026, so it is treated the same way as hydrogen.

**2026, hydrogen.** Halifax-Hamburg's primary scenario pays EUR 13.07 per
tonne in total carbon compliance cost, bracketed by a EUR 10.03-12.55
literature sensitivity range. Ningbo-Felixstowe pays GBP 0.50 per tonne
regardless of pathway, more than twenty times less, because UK CBAM has not
started and UK ETS does not price the ocean leg, so pathway-specific embedded
emissions don't yet matter for that corridor at all.

**2030**, with UK CBAM running at its real legislated rate (32.96% of the UK
ETS price in 2030, derived from the 86.49% baseline free allocation and the
Article 16(14) factor of 0.775; see `regulatory_constants.uk_cbam_rate_fraction`):
Ningbo-Felixstowe's primary scenario reaches GBP 434.40 per tonne, against
EUR 411.00 for Halifax-Hamburg's. CBAM dominates both totals by then and the
maritime terms become close to irrelevant.

Running UK CBAM at 100% instead, as a labelled upper-bound what-if rather than
a forecast, Ningbo-Felixstowe's primary scenario reaches GBP 1,316.78 per tonne.
That figure is an artefact of the override, not the legislated mechanism, and
should be reported as such.

In both years and both corridors, the CBAM-default anchor sits **above** the
literature "high" bracket, not between the two literature brackets — a direct
consequence of the regulation's deliberate mark-up design, not a modelling
artefact.

The corridor asymmetry is a window, not a permanent feature. That belongs in
the discussion chapter.

### A caveat to label in the write-up

An 84,000 m3 ammonia carrier operates at about -33 C and cannot physically hold
liquid hydrogen, which needs -253 C. The largest liquid hydrogen vessel built is
the Suiso Frontier at 1,250 m3, and designs under development are around
40,000 m3. Applying the ammonia carrier's geometry to hydrogen is a deliberate
counterfactual that isolates the effect of cargo density by holding the vessel
constant. It is a legitimate way to answer "what does density alone do to
per-tonne cost", but it is not a shipping option available today, and liquid
hydrogen boil-off losses are not modelled.

## What is still unresolved

1. **The EU CBAM obligation uses the wrong functional form.** The model computes
   `chargeable = embedded x CBAM_factor`. Regulation (EU) 2023/956 Article 31
   adjusts the obligation for the free allocation an EU installation making the
   same good would receive, and free allocation under Article 10a of Directive
   2003/87/EC is measured against a product benchmark, so the correct form is
   `max(0, embedded - benchmark x (1 - CBAM_factor))`. The two agree only in
   2034, when free allocation reaches zero. The benchmark form reproduces
   Ramsook et al.'s published 22% burden at 20.7%; the current form gives 14.5%.
   Both sit side by side in `validation/reference_case.py`. Switching is blocked
   on reading out the revised 2026-2030 benchmarks the Commission adopted on
   29 June 2026; the values in code (ammonia 1.570, hydrogen 6.84, from IR
   2021/447) are the 2021-2025 set. Individual CBAM figures move a lot under the
   switch, but the headline finding holds: the production cost gap dwarfs the
   CBAM differential either way.
2. **Two production-cost gaps are still built from separate studies, but the
   results do not depend on it.** Canada hydrogen spans three papers (grey
   S0957582024004336, blue S036031992206236X, green S0960148125012959) and China
   ammonia spans two (Nature s43247-025-02056-z, S0360319922016019). Riya
   confirmed on 4 August 2026 that no single study covers the Canadian pathways,
   so unlike China hydrogen this cannot be fixed by swapping papers.

   Rather than leave it as a bare disclaimer, `analysis.outputs
   .abatement_source_robustness` recomputes every abatement result on the IEA
   cost sheet, which prices all pathways on both corridors under one
   methodology, and reports the two side by side
   (`outputs/abatement_source_robustness.csv`). **Every verdict holds its sign
   under both sourcings, and under both the IEA onshore wind and solar PV green
   routes.** A test fails if that ever stops being true. The IEA figures are not
   used as primary because they are regional (North America, not Canada) and are
   an agency benchmark rather than a peer-reviewed country-specific study, so
   promoting them would trade a sourcing problem for a geography problem.

   Suggested methodology wording, from Riya: costs were sourced where possible
   from studies applying a consistent techno-economic framework across multiple
   production pathways, and where pathway-specific regional studies were
   unavailable, supplementary literature and IEA benchmark estimates were used.
3. **Green ammonia on the UK corridor is too close to call.** At 2030 medium
   prices its abatement cost is EUR 57.31/tCO2 against a carbon price of
   EUR 57.90, a margin of 1%, and that gap is one of the two built across
   separate studies. The bare boolean says "justified"; it is not reportable as
   one. `marginal_abatement_cost` now carries a three-state `verdict` column
   with a 10% marginal band, and this row reads `marginal`. Under IEA costs it
   moves to comfortably justified (EUR 27.57) on the wind route and stays
   marginal (EUR 56.21) on solar, so the direction is stable even though the
   confidence is not.
4. **Conversion and freight cost per tonne.** No owner assigned. Production
   cost is no longer in this list: Riya delivered it on 4 August 2026. Note
   these two terms are invariant to production pathway, so they cancel out of
   any within-corridor pathway comparison and do not block the marginal
   abatement cost results.
5. **UK ETS price is held flat across 2026-2030** while the EU price rises 58%
   over the same span. Only the 2026 UK figure was ever sourced. UK-side costs
   from 2027 on are therefore understated. The finding that the UK corridor
   overtakes the EU one by 2030 survives this, because UK is the understated
   side, but the assumption has to be stated. A labelled EU-UK linkage variant
   exists in the code as an alternative price path.

**Resolved 4 August 2026.** China hydrogen now comes from one study.
`green_electrolysis`, `coal_gasification` and `blue_ccs` all take both emissions
and production cost from S0360319925010602, agreed with Riya. Previously the row
drew on four papers: grey emissions from S0360319921042737 (29.02, now 20.09),
blue from S0959652622021151 (7.91, now 6.28), and all three costs from
S097308262400214X. This moves blue hydrogen's abatement cost from EUR 8.3 to
EUR 40.0/tCO2 and green's from EUR 106.6 to EUR 238.6. Both verdicts survive,
blue still beats the UK carbon price and green still does not, but the EUR 8
figure was an artefact of mixing studies and must not be published. An earlier
proposal in this repo to switch blue to the 13.99 with-CCS figure is superseded:
it would have paired grey and blue while leaving green on a third paper.

**Resolved 25 July 2026.** UK ETS price anchors, from the UK ETS Authority
determination of GBP 49.41/tCO2e for the scheme year beginning 1 January 2026.
Formally the civil-penalty price, but calculated from twelve months of 2026 UKA
December futures settlement prices, so market-derived rather than administrative.
Cargo tonnage, from Gayu's capacity notebook.

## Layout

```
cbam_model/
  config/
    regulatory_constants.py   every law-derived value, each with its source
    unresolved.py             sentinel for values that must not be guessed
    scenarios.py              the scenario matrix
    vessel_logistics.py       Gayu's vessels, distances and fuel model
  model/
    cbam.py                   EU and UK CBAM
    ets_maritime.py           EU and UK maritime ETS
    fueleu.py                 FuelEU penalty and the RFNBO reward factor
    total_cost.py             the two layers and the compliance join
  validation/
    unit_checks.py            data contract enforcement
    gayu_reproduction.py      pins all 31 of Gayu's published figures
    reference_case.py         cross-check against Ramsook et al. (2025)
  analysis/
    sensitivity.py            one-at-a-time sweep and driver ranking
    outputs.py                tables and charts
  data/                       real inputs go here; see data/README.md
  data/placeholder/           synthetic inputs, marked PLACEHOLDER
tests/test_model.py
run_model.ipynb
build_notebooks.py
```

## Functional units

**Maritime layer:** cost per voyage, in the regime's own currency. Gayu's unit.

**CBAM layer:** cost per tonne of product landed, since embedded emissions are
expressed per tonne.

**Compliance layer:** the two joined, per tonne of product, using Gayu's cargo
tonnage. Still in the regime's own currency; no exchange rate is applied
anywhere.

## Three corrections made to the build spec

The spec was followed except where it was wrong. Each of these is documented in
the relevant source file.

**1. The origin carbon price adjustment had a units error.** The spec wrote
`(emissions x factor x price) - origin_carbon_price`, subtracting a
EUR-per-tonne price from a EUR total. With 10 tCO2e, a 2.5% factor, EUR 80/t and
an origin price of EUR 30/t that gives 20.00 - 30.00 = -10.00, a negative cost
from a positive liability. Under Regulation (EU) 2023/956 Article 9 the origin
price reduces the certificates to be surrendered, so it scales with the same
emissions and the same CBAM factor as the obligation. Implemented as
`emissions x factor x (price - origin_price)`, floored at zero.

**2. The FuelEU penalty was missing a divisor.** The spec wrote
`(deficit x energy / 41000) x 2400`. Annex IV Part B divides the compliance
balance by `GHGIE_actual x 41,000`, because that is what converts a gCO2e deficit
into tonnes of VLSFO energy equivalent. Since GHGIE_actual sits around
90 gCO2e/MJ, the spec version overstates the penalty by roughly ninety times.
Verified against the regulation before implementing.

**3. The FuelEU target schedule stopped short of the scenario matrix.** The spec
carried only the 2025 to 2029 target of 89.34 gCO2e/MJ, but the matrix runs 2030,
where Article 4(2) tightens the reduction from 2% to 6%. The full step schedule
through 2050 is now in `FUELEU_REDUCTION_BY_PERIOD`. The 2025 to 2029 ceiling
uses the published 89.34 rather than the computed 89.3368, so results agree
exactly with Gayu's.

## Two things the spec did not cover

**Cargo tonnage was the join between the two halves of the study**, and it was
not in any data contract. Gayu supplied it on 25 July after it was raised. It
drives the hydrogen-versus-ammonia comparison on its own, since the 9.6 to 1 mass
ratio means each tonne of hydrogen absorbs 9.6 times more of a voyage's carbon
cost.

**Data contract gaps.** Three of the six cost terms (production, conversion,
shipping) have no owner.

**The reference case does not reconcile.** Fed the Part C grey ammonia intensity
and a plausible ammonia price, the model puts Trinidad and Tobago's 2034 CBAM
burden at 98% of export value against the 22% published by Ramsook et al. The
most likely explanation is that the published ratio is measured against total
export revenue while CBAM applies only to the EU-bound share, which would mean
the two figures are not comparable and the model is fine. This is left visible
and uncalibrated rather than tuned until it agrees. See
`validation/reference_case.py`.

## What the tests protect

The suite pins the three facts this project has already got wrong once each:

- The CBAM factor is 2.5% in 2026, not 97.5%. Tested by asserting it sums to one
  with the free allocation share in every year, and that it rises over time.
- UK ETS ignores the international voyage. Tested by showing a 10,000 tCO2 ocean
  crossing changes the Felixstowe cost by nothing at all.
- The proposed UK ETS extension is opt-in and cannot be selected before 2028.

Expected values are hand-calculated in the test bodies rather than copied from a
previous run.
