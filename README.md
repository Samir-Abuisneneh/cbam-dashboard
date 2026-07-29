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
electrolysis = low, grey SMR / coal gasification = high). **Ammonia has no
CBAM regulatory default yet** (pending Riya sourcing it from Annex I), so
ammonia figures remain literature-only until then.

**2026, hydrogen.** Halifax-Hamburg's primary scenario pays EUR 13.07 per
tonne in total carbon compliance cost, bracketed by a EUR 10.03-12.55
literature sensitivity range. Ningbo-Felixstowe pays GBP 0.50 per tonne
regardless of pathway — about 25 times less — because UK CBAM has not started
and UK ETS does not price the ocean leg, so pathway-specific embedded
emissions don't yet matter for that corridor at all.

**2030**, running UK CBAM at 100% as a labelled what-if since the phase-in
factor remains unresolved: Ningbo-Felixstowe's primary scenario reaches
GBP 1,316.78 per tonne — CBAM now dominates the total and the maritime terms
become close to irrelevant. Halifax-Hamburg's primary scenario reaches
EUR 411.00 per tonne.

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

1. **Ammonia embedded emissions** (Riya). Hydrogen emissions are real, sourced
   data for both corridors, including CBAM regulatory default values. Ammonia
   is still placeholder literature ranges on both corridors, and critically
   **has no CBAM regulatory default value at all yet** — Riya's 29 July 2026
   proposal to anchor the model on CBAM defaults as the primary scenario can't
   fully extend to ammonia until that default is sourced from IR 2025/2621
   Annex I. By 2030 CBAM dominates every other term, so this is now the
   largest source of uncertainty in the study for ammonia specifically. The
   `origin_carbon_price_eur_per_tco2e` column matters most: Canada prices
   industrial carbon and China prices it lower, and a large enough Canadian
   price would cut Halifax-Hamburg's CBAM liability sharply, possibly
   reversing the corridor comparison.
2. **Production, conversion and freight cost per tonne.** No owner assigned. The
   only thing standing between compliance cost and full delivered cost.
3. **The UK CBAM phase-in factor.** Blocks a non-hypothetical 2027-onward UK
   result and drives the entire 2030 comparison. Currently only runnable as an
   explicitly labelled what-if (see the dashboard's phase-in slider).
4. **GBP to EUR rate.** No reference date chosen, so no conversion happens.

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
