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
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

.venv/bin/jupyter lab run_model.ipynb   # the main run
.venv/bin/python -m pytest -q           # the test suite
.venv/bin/ruff check .                  # lint, configured in pyproject.toml
.venv/bin/streamlit run dashboard.py    # interactive scenario explorer
```

`requirements.txt` is the Streamlit Cloud deployment set and is deliberately
minimal; `requirements-dev.txt` adds matplotlib, pytest, ruff and the notebook
and PDF build tooling on top of it.

`run_model.ipynb` is the entry point and produces everything end to end.
Outputs land in `cbam_model/outputs/`: the long-format scenario table, a
compliance cost table, a corridor comparison, the sensitivity sweep and three
charts.

`dashboard.py` is a Streamlit UI over the same fixed scenario matrix (pick
corridor, product, pathway, year, price/vessel/route scenario) without reading
CSVs or running the notebook. It was originally built as a client-facing tool;
since the industry partner withdrew on 6 August 2026 it is an internal one,
used to generate figures for the dissertation and the defence presentation. It calls
`cbam_model` live, so it can never drift from the tested regulatory logic. It
does not accept arbitrary routes or ports — only the two corridors already
built and covered by the test suite. Any remaining placeholder input is flagged
in the UI; as of Riya's 4 August 2026 delivery that is conversion and shipping
cost alone, since ammonia emissions and production cost are both real and
sourced. The UK CBAM rate is shown at its real legislated value, derived from
the Finance Act 2026 baseline and the year's Article 16(14) factor, with an
opt-in slider to override it as an explicitly-labelled what-if.

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
literal expected values and checks that this model reproduces every one of them,
so divergence shows up as a test failure rather than quiet drift.

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

Figures below regenerated 5 August 2026 after the Canada origin carbon price
correction and Gayu's CO2e update. Both moved the Halifax-Hamburg column and
neither touched Ningbo-Felixstowe, since Canada's origin price is a EU-side
Article 9 deduction and China's is zero either way. The earlier text quoted
EUR 13.07 (2026) and EUR 411.00 (2030); those are pre-correction and must not
be cited.

**2026, hydrogen.** Halifax-Hamburg's primary scenario pays EUR 15.97 per
tonne in total carbon compliance cost, bracketed by a EUR 10.44-15.02
literature sensitivity range. Ningbo-Felixstowe pays GBP 0.50 per tonne
regardless of pathway, more than thirty times less, because UK CBAM has not
started and UK ETS does not price the ocean leg, so pathway-specific embedded
emissions don't yet matter for that corridor at all.

**2030**, with UK CBAM running at its real legislated rate (32.96% of the UK
ETS price in 2030, derived from the 86.49% baseline free allocation and the
Article 16(14) factor of 0.775; see `regulatory_constants.uk_cbam_rate_fraction`):
Ningbo-Felixstowe's primary scenario reaches GBP 434.41 per tonne, against
EUR 389.90 for Halifax-Hamburg's. CBAM dominates both totals by then and the
maritime terms become close to irrelevant.

The 2026 figure rose and the 2030 figure fell for the same reason: the
corrected Canada carbon price path is *lower* than the old flat CAD 110 in
2026 (CAD 95, so less is deducted and CBAM costs more) and *higher* by 2030
(CAD 115, so more is deducted and CBAM costs less).

Running UK CBAM at 100% instead, as a labelled upper-bound what-if rather than
a forecast, Ningbo-Felixstowe's primary scenario reaches GBP 1,316.78 per tonne.
That figure is an artefact of the override, not the legislated mechanism, and
should be reported as such.

In both years and both corridors, the CBAM-default anchor sits **above** the
literature "high" bracket, not between the two literature brackets — a direct
consequence of the regulation's deliberate mark-up design, not a modelling
artefact.

The corridor asymmetry is a window, not a permanent feature, and it closes
earlier than the 2026-versus-2030 contrast above suggests. `analysis.outputs
.corridor_crossover_year` puts the first flip in **2027**, the year UK CBAM
starts, for both products: Ningbo-Felixstowe is cheaper in 2026 only because UK
CBAM does not exist yet.

What happens after 2027 depends on the product, under the `benchmark_shielded`
mechanism adopted on 7 August 2026.

**Ammonia** stays flipped. Halifax-Hamburg is cheaper every year from 2027 and
the gap narrows from GBP 19.08 to GBP 13.04 by 2030. One flip followed by
convergence, not a slow overtake.

**Hydrogen** flips back. Halifax-Hamburg is cheaper in 2027 only (GBP 63.23),
then Ningbo-Felixstowe takes the lead again from 2028 and holds it through 2030
(GBP 13.56, 69.44 and 43.31 ahead). The driver is the benchmark shield: the EU
hydrogen benchmark of 7.98 tCO2e/t sits close to Canadian grey hydrogen's 10.07,
so early EU liability is small but climbs steeply as free allocation is
withdrawn, while the UK rate fraction climbs far more slowly. Two flips, not
one, and the second is the one worth writing up.

### The corridor finding survives every UK price path

Added 6 August 2026. The UK price was held flat across 2026-2030 because only
the 2026 figure was ever sourced, which made every forward UK claim partly an
artefact. There are now three labelled paths, selectable with
`uk_price_variant`:

| Variant | 2026 | 2030 | What it is |
|---|---|---|---|
| `frozen` | 49.41 | 49.41 | The sourced 2026 determination held flat. Baseline. |
| `linked` | 49.41 | 107.50 | EU-UK ETS linkage convergence. Not law. |
| `desnz` | 38.00 | 50.00 | The UK government's own published traded carbon values. |

`desnz` comes from DESNZ, *Traded carbon values used for modelling purposes,
2025*, published 3 February 2026. It is the only forward UK path here with an
official source. Read its caveats at `UK_ETS_PRICE_DESNZ_BY_YEAR` before
quoting it: it is in **real 2025 prices** while every other price in the model
is nominal, DESNZ states plainly that these are not forecasts, and it models a
standalone UK ETS that excludes linking, so `desnz` and `linked` are
alternative views of the same uncertainty rather than compatible ones.

The 2026 gap is worth reporting rather than resolving. DESNZ central is GBP 38
against the GBP 49.41 the model anchors on, but these are not rival estimates
of one quantity: 49.41 is a backward-looking average of actual UKA futures
settlements published for civil-penalty purposes, 38 is a forward
policy-appraisal scenario in real terms.

**The result, under the `benchmark_shielded` mechanism adopted on 7 August
2026: ammonia is robust to the price path, hydrogen is not.**

Ammonia gives the same ordering under all three paths, Ningbo-Felixstowe in
2026 only and Halifax-Hamburg every year after. For ammonia the "UK price is
frozen" caveat is genuinely retired.

Hydrogen does not, and the split is now wider than a late-horizon flip. On the
frozen and DESNZ paths Ningbo-Felixstowe is cheaper in **every** year and there
is no crossover at all. On the linkage path Halifax-Hamburg takes the lead in
2027 and holds it, because a UK price converging upward on the EU price raises
UK CBAM enough to reverse the ordering outright.

| Path | Hydrogen ordering, 2026 to 2030 |
|---|---|
| `frozen` | NF, NF, NF, NF, NF |
| `desnz` | NF, NF, NF, NF, NF |
| `linked` | NF, HH, HH, HH, HH |

So on hydrogen the corridor conclusion rests entirely on the UK price
assumption, and every hydrogen corridor claim has to name the path it is on.
The linkage path is explicitly not law.

Both tables above come from `outputs/corridor_ordering_by_price_path.csv` and
`outputs/corridor_crossover_by_price_path.csv`, added 9 August 2026. They exist
because `write_all` builds every other corridor artefact from a single
compliance frame, so the whole 8 August result freeze went out on `frozen`
alone and this section could only be checked by re-running the model three
times. Pass `compliance_by_variant` to `write_all` to regenerate them. The
`uk_price_variant_label` column carries the not-law caption on `linked` into
the data itself, so it cannot be separated from the number.

Two superseded versions of this section exist and must not be requoted. Under
`factor_scaled` all three paths agreed on both products, and that was claimed as
a settled robustness result. Under `benchmark_shielded` with the EU ETS
benchmark wrongly netted off, hydrogen read NF, HH, NF, NF, NF on frozen and
DESNZ, described as a flip out and back. The benchmark correction of 8 August
2026 replaced that with no crossover at all.

### A mark-up bug, found by checking the Commission's own workbook

Fixed 7 August 2026. The IR 2025/2621 mark-up on default emissions values is
**not uniform**: fertiliser goods carry a flat 1% in every year, while
hydrogen, iron and steel ramp 10/20/30. The model applied 10/20/30 to
everything.

Ammonia is a fertiliser good for CBAM (CN 2814); hydrogen is not (CN 2804). So
ammonia's default emissions were overstated by 8.9% in 2026 rising to 28.7%
from 2028, on the primary scenario and the EU corridor.

Verified directly against the Commission's adopted default values workbook,
which publishes each value before and after mark-up, so the schedule divides
out exactly: Canada ammonia 1.98 to 1.9998 in all years, Canada hydrogen 10.82
to 11.902 / 12.984 / 14.066.

`default_value_markup` now requires the product and raises without it, because
a defaulted argument would silently restore a bug whose output looks plausible.

Two consequences. **The lock-in finding strengthens**: ammonia's EU cost falls,
so the 2026 commitment to the UK corridor looks worse, with regret rising from
95% to 146% and the breakeven from GBP 75.36 to GBP 91.60. Those four figures
measure the fertiliser fix alone under the `factor_scaled` mechanism then in
force, and the benchmark correction of 8 August superseded all of them; current
ammonia figures are regret 33.45% / breakeven GBP 38.72 on `truncate` and
26.91% / GBP 76.99 on `hold_final`. **The CBAM mechanism choice narrows**: both
mechanisms now agree on ammonia's corridor ordering, and only hydrogen still
inverts.

### Policy timeline is now machine readable

`cbam_model/data/policy_events.csv`, 50 events across Canada, the UK, the EU
and China, loaded by `data_io.load_policy_events()`. Each row carries the legal
instrument type and status, so an Act and a consultation that closed without a
decision are not treated as the same kind of fact, plus the quantified
translation and the model parameter it bears on.

A test cross-checks the timeline against the code, and every quantified event
agrees. See `docs/policy_timeline_gaps.md` for what is still unfilled, and for
the one substantive gap it surfaced: **UK CBAM charges direct emissions only
until 2029 at the earliest, which the model does not represent.**

### Competitiveness: the two rankings now agree everywhere

Added 6 August 2026. `analysis.outputs.competitiveness_burden` and
`competitiveness_asymmetry`, answering the competitiveness half of the EU-UK
asymmetry objective. Every other output reports compliance cost in absolute
terms, which says how much carbon regulation costs but not whether it is
material to the traded good.

Compliance cost as a share of production cost, `cbam_default`, medium prices,
on the CBAM benchmark corrected 8 August 2026:

| Product | Year | Halifax-Hamburg | Ningbo-Felixstowe | More exposed |
|---|---|---|---|---|
| Ammonia | 2027 | 3.86% | 9.51% | UK |
| Ammonia | 2030 | 15.22% | 20.00% | UK |
| Hydrogen | 2027 | 40.38% | 20.52% | EU |
| Hydrogen | 2029 | 87.96% | 29.00% | EU |
| Hydrogen | 2030 | 104.26% | 43.12% | EU |

**A finding was lost here on 8 August 2026 and the write-up must not requote
it.** This section previously reported that absolute cost and competitive
exposure point in opposite directions, so that reporting only absolute cost
would state the asymmetry backwards. That claim was made twice, at hydrogen
2030 under `factor_scaled` and at hydrogen 2027 under `benchmark_shielded` with
the EU ETS benchmark wrongly netted off. Neither survives the benchmark
correction. Ningbo-Felixstowe is now both the cheaper corridor and the less
exposed one in every product-year, so the two rankings agree everywhere.
`test_burden_ranking_no_longer_diverges_from_the_absolute_cost_ranking` fails if
a divergence ever returns.

The hydrogen 2029 near-tie is also gone. It split the corridors by 0.04
percentage points under `factor_scaled` and now sits 58.96 points apart. The
closest row anywhere in the matrix is ammonia 2026 at 2.61 points, a 198%
relative margin, so nothing currently trips the `marginal` band.

What remains is the scale of EU hydrogen exposure. Halifax-Hamburg hydrogen
passes 100% of production cost by 2030, meaning carbon compliance would cost
more than making the product. Read that as what the regime implies on the
`cbam_default` pathway rather than as a forecast of trade: a real declarant
facing that number would move to verified actual emissions, a cleaner pathway,
or another market long before 2030. That response is outside what this model
represents.

Three caveats travel with any figure here. The denominator is **production
cost, not market price**, because no price series exists for these corridors;
since a traded price normally exceeds production cost this **overstates** the
burden against a revenue-based measure like Ramsook et al.'s 22%, though the
direction is consistent across both corridors so the asymmetry is more robust
than either level. Conversion and freight are excluded because they remain
placeholders. The UK figure is converted at the single 23 July 2026 ECB rate.

### Lock-in: the 2026 cost ranking is a trap

Added 6 August 2026, after the supervisor asked for the transaction-cost layer
to go into the model rather than sit beside it. `analysis.outputs
.corridor_lock_in` and `model/switching.py`.

The crossover result above assumes corridor choice is remade every year at no
cost. Under Transaction Cost Economics it is not: route concessions, port
access, insurance written against a named route and fixed shore infrastructure
are all corridor-specific and non-redeployable, and offtake is contracted over
roughly a decade because that is what finances specific assets.

Once the decision is a commitment rather than an annual re-pick, **the corridor
that is cheaper in 2026 is the wrong one to commit to for ammonia.** A firm
reading the 2026 ammonia cost table picks Ningbo-Felixstowe; the present value
of the tenor says Halifax-Hamburg. At 8% real over the modelled years, medium
prices, `truncate`:

| Product | Decision year | Spot-cheapest | PV-cheapest | Regret | Breakeven switching cost |
|---|---|---|---|---|---|
| Ammonia | 2026 | Ningbo-Felixstowe | Halifax-Hamburg | 33.5% | GBP 38.72 |
| Hydrogen | none | Ningbo-Felixstowe | Ningbo-Felixstowe | 0% | n/a |

Switching costs are **GBP per tonne of annual contracted volume**, not per tonne
shipped. Read the units note in `model/switching.py` before quoting either.

**Lock-in is an ammonia-only finding as of 8 August 2026.** Hydrogen's spot and
tenor choices agree in every year, so there is no trap to report on it. Two
superseded versions of this result are quoted in documents written before that
date and must not be requoted:

| Superseded version | Ammonia | Hydrogen |
|---|---|---|
| `factor_scaled` | 2026, toward HH, regret 146%, breakeven GBP 91.60 | 2026, toward HH, regret 109%, breakeven GBP 491.95 |
| `benchmark_shielded` on the ETS benchmark | 2026, toward HH, regret 33.5%, breakeven GBP 38.72 | 2027, toward NF, regret 4.2%, breakeven GBP 43.24 |

The second of those was reported as the more interesting finding, because the
two products implied opposite corridor commitments under one regime. Correcting
the benchmark to the CBAM benchmark required by IR 2025/2620 removed hydrogen's
reversal and with it the opposition. Ammonia's figures are unchanged throughout,
because its CBAM benchmark and its ETS benchmark are the same number.

The ammonia reversal is confined to 2026 and survives both beyond-horizon
treatments, so it is not an artefact of the extrapolation assumption; a test
enforces that. Only the magnitude moves, breakeven GBP 38.72 under `truncate`
against GBP 76.99 under `hold_final`. The mechanism is regulatory timing alone:
UK CBAM starting a year later than the EU's creates a one-year advantage that a
ten-year commitment converts into a liability. That is the institutional-theory
half of the argument and the asset-specificity half meeting in one number.

No switching cost is claimed. The finding is the **threshold**, and the
discussion argues about which side of it real corridor-specific sunk costs fall.

This result rests on the CBAM mechanism choice, which is Samir's decision of
7 August 2026, taken without a supervisor ruling and defended on the law rather
than deferred. See unresolved item 1 below and present it in the methodology as
a defended choice, not as a pending question.

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

1. **The EU CBAM mechanism is a defended choice, not an open question.** No
   supervisor ruling was sought and none is required; the choice is settled on
   the law and carried in the methodology. Everything downstream rests on it,
   which is why the reasoning is recorded here in full.

   The model computes the obligation as
   `max(0, embedded - CBAM_benchmark x (1 - CBAM_factor) x CSCF)`, netting off
   free allocation. The superseded alternative scaled embedded emissions by the
   CBAM factor instead. **The benchmark form is the one the law describes**, and
   as of 8 August 2026 that is no longer an inference: Commission Implementing
   Regulation (EU) 2025/2620 of 16 December 2025, adopted under Article 31(2),
   sets out the calculation directly (Annex Equations 1, 2 and 6). Both forms
   stay implemented and `analysis.outputs.cbam_mechanism_comparison` reports
   them side by side, so the size of the choice stays visible.

   What remains is presentation, not correctness. The switch was Samir's
   decision of 7 August 2026 and it changes a headline finding, so it belongs in
   the methodology as a defended choice rather than in a changelog.

   **A material error was found and fixed on 8 August 2026.** Until that date
   the model netted off the **EU ETS product benchmark**. That is the wrong
   instrument. IR 2025/2620 defines a distinct **CBAM benchmark**, derived from
   the ETS benchmarks but not equal to them:

   | Good | EU ETS benchmark | CBAM benchmark | Gap |
   |---|---|---|---|
   | Ammonia (CN 2814 10 00) | 1.522 | 1.522 | none |
   | Hydrogen (CN 2804 10 00) | 7.98 | **5.089** | ETS figure 56.8% too high |

   Ammonia is unaffected, which is why every ammonia figure in this README is
   unchanged. Hydrogen was being shielded by 56.8% more than the law allows, so
   EU hydrogen liability was understated in every year. Correcting it removed
   hydrogen's corridor crossover entirely, removed its lock-in reversal, and
   removed the competitiveness divergence finding. Those three losses are
   recorded in their own sections above.

   The CSCF term from Equations 2 and 6 was also missing entirely and is now
   represented. It is held at **1.0 as a stated assumption, not a sourced
   figure**: the CSCF was 100% across 2021-2025 and no 2026 value was found on
   8 August 2026. `CBAM_CSCF_IS_SOURCED` is False and the outputs carry it.

   **One thing to re-check before submission.** IR 2025/2620 recital 10 says the
   CBAM benchmarks applying from 1 January 2026 are based on *estimated*
   2026-2030 ETS benchmarks, to be reviewed within one month of the final ones
   being published, with updated values applying to goods imported from
   1 January 2027. IR 2026/1412 published the final ETS benchmarks on 29 June
   2026, so a revision was due by roughly end of July. No amending regulation
   was found on 8 August 2026. If one appears, the 2027-2030 hydrogen benchmark
   changes again and every corridor result with it.

   The gap between the two forms is not uniform in sign. Under the benchmark
   form green pathways sitting below the benchmark owe zero CBAM, while
   pathways above it owe much more. So the superseded form materially
   **understated how far CBAM closes the green premium**, and the primary
   `cbam_default` scenario sat on the understated side. The finding that the
   production cost gap dwarfs the CBAM differential holds under both.
2. **Two production-cost gaps are still built from separate studies, but the
   results do not depend on it.** Canada hydrogen spans three papers (grey
   S0957582024004336, blue S036031992206236X, green S0960148125012959) and China
   ammonia spans two (Nature s43247-025-02056-z, S0360319922016019).

   **Why this cannot be fixed the way China hydrogen was.** One study, Ayub et
   al. (2024) (S0957582024004336, already the primary grey source), does report
   costs for all three Canadian pathways under a single framework, so the
   consolidation looks available at first glance. It is not, for two reasons
   checked against the paper on 9 August 2026:

   - **Its emissions side is not physically valid.** Table 2 uses 15 kg CO2 per
     kg of coal and 9 per kg of natural gas. Stoichiometry caps coal near 2.6
     and methane at 2.75, so those factors exceed what mass balance allows.
     They propagate into Table 1's throughputs to give 107.27 kg CO2/kg H2 for
     coal gasification, against the ~20 reported elsewhere and the 20.09 this
     model uses. Recomputed on a valid factor the same arithmetic yields about
     18.4, which is consistent with the literature. So unlike
     S0360319925010602, which supplied China with credible emissions *and*
     costs, this paper cannot supply both.
   - **Its green cost is not route-appropriate.** Equation 12 prices
     electrolysis at Table 4's regional electricity price, sourced from
     Statista household tariffs (Canada, 0.192 $/kWh). That is grid
     electrolysis at retail rates, not the wind-driven electrolysis
     Halifax-Hamburg actually represents, which is why it returns 10.80 $/kg
     against the wind-specific study's ~4.11. The paper also contradicts
     itself here: section 4.2.3 states 18.80 for Canada where Table 7 gives
     10.80.

   Ayub is therefore retained as a **cost** cross-check only, which is how
   `data_io.ayub_production_costs` uses it. Its grey figure agrees with the
   primary almost exactly (USD 700/t against 700/t). Its green figure does not
   constitute a like-for-like check, since it compares a wind-driven cost to a
   retail-grid one, and the resulting gap is a definitional difference rather
   than evidence of cost uncertainty. Say that wherever the comparison is
   reported.

   Rather than leave the gap as a bare disclaimer, `analysis.outputs
   .abatement_source_robustness` recomputes every abatement result on the IEA
   cost sheet, which prices all pathways on both corridors under one
   methodology, and reports the two side by side
   (`outputs/abatement_source_robustness.csv`). **Every verdict holds its sign
   under both sourcings, and under both the IEA onshore wind and solar PV green
   routes.** A test fails if that ever stops being true. Every verdict also
   holds under the Ayub costs, checked 9 August 2026, so there are three
   independent sourcings in agreement rather than two. The IEA figures are not
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
4. **Conversion and freight cost per tonne.** A stated scope boundary, not a
   pending input. No public source was identified and the industry partner
   route closed on 6 August 2026, so the study reports carbon compliance cost
   per tonne rather than delivered cost, and says so in the methodology.
   Production
   cost is no longer in this list: Riya delivered it on 4 August 2026. Note
   these two terms are invariant to production pathway, so they cancel out of
   any within-corridor pathway comparison and do not block the marginal
   abatement cost results.
5. **The baseline UK ETS price is held flat across 2026-2030** while the EU
   price rises 58% over the same span, because only the 2026 UK figure was ever
   sourced. UK-side costs from 2027 on are therefore understated on the
   `frozen` baseline.

   This is no longer a sourcing gap. Two labelled forward paths exist alongside
   it, `linked` and `desnz`, and the DESNZ series is the UK government's own
   published traded carbon values. See "The corridor finding survives every UK
   price path" above for what each one is and the caveats that travel with them.

   What remains open is a **reporting obligation, not an input**. Earlier
   versions of this item claimed the corridor finding survives the price
   assumption because UK is the understated side. That is true for ammonia and
   **false for hydrogen**, whose corridor ordering depends entirely on which
   path is chosen: no crossover at all on `frozen` and `desnz`, Halifax-Hamburg
   from 2027 on `linked`. Every hydrogen corridor claim must name its path, and
   note that `linked` is explicitly not law.

   **What the law specifies, established 9 August 2026.** For the UK CBAM rate
   the ETS price input is not a free choice. SI 2026/809 regulation 3,
   implementing Finance Act 2026 s.149(3) Step 1, defines it as "the mean
   average of all auction clearing prices for UK ETS allowances during the
   quarter preceding quarter Q", falling back to the most recent quarter that
   held an auction. The statutory quantity is therefore a **quarterly mean of
   auction clearing prices**.

   GBP 49.41 is neither quarterly nor auction-derived: it is an annual mean of
   UKA December futures settlement prices. The two track each other closely, so
   this is a defensible approximation rather than a wrong number, but the
   methodology must describe it as an approximation of the statutory series
   rather than as the series itself. UK ETS auction results are published, so
   sourcing the real quarterly path is achievable and would close both this and
   the flat 2027-2030 assumption in one step. This reframes the item: it is no
   longer "only one year could be sourced", it is "the statutory basis is known
   and we approximate it".

**Resolved 4 August 2026.** China hydrogen now comes from one study.
`green_electrolysis`, `coal_gasification` and `blue_ccs` all take both emissions
and production cost from S0360319925010602, agreed with Riya. Previously the row
drew on four papers: grey emissions from S0360319921042737 (29.02, now 20.09),
blue from S0959652622021151 (7.91, now 6.28), and all three costs from
S097308262400214X. This moves blue hydrogen's abatement cost from EUR 8.3 to
EUR 40.0/tCO2 and green's from EUR 106.6 to EUR 238.6. Both verdicts survive,
blue still beats the UK carbon price and green still does not, but the EUR 8
figure was an artefact of mixing studies and must not be published. (Green's
figure moved again on 9 August, to EUR 302.41, when this cell was reconciled
against Riya's current sheet. The verdict is unchanged.) An earlier
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
    switching.py              corridor lock-in under asset specificity
    total_cost.py             the two layers and the compliance join
  validation/
    unit_checks.py            data contract enforcement
    gayu_reproduction.py      pins every one of Gayu's published figures
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
shipping) had no owner. Production was delivered by Riya on 4 August 2026.
Conversion and shipping are now a declared scope boundary, per item 4 above:
the study reports carbon compliance cost per tonne, not delivered cost.

**The reference case reconciled on 4 August 2026, and the answer was not the
one expected.** The divergence against Ramsook et al. was never about inputs or
about the burden being measured against total rather than EU-bound export
revenue. It is that the two compute the free allocation adjustment in
structurally different ways: this model scales the importer's own emissions by
the CBAM factor, while Article 31 shields a product benchmark. See
`validation/reference_case.py`.

## What the tests protect

The suite pins the three facts this project has already got wrong once each:

- The CBAM factor is 2.5% in 2026, not 97.5%. Tested by asserting it sums to one
  with the free allocation share in every year, and that it rises over time.
- UK ETS ignores the international voyage. Tested by showing a 10,000 tCO2 ocean
  crossing changes the Felixstowe cost by nothing at all.
- The proposed UK ETS extension is opt-in and cannot be selected before 2028.

It also guards the two results most likely to be misread:

- The lock-in reversal is confined to 2026 and holds under **both**
  beyond-horizon treatments, which err in opposite directions. A finding that
  survived only one of them would be an artefact of the extrapolation.
- No benchmark-based CBAM figure can be produced without the
  `benchmark_is_current` flag travelling with it, and the benchmark mechanism
  refuses to run without an explicit benchmark rather than defaulting to zero,
  which would silently collapse it into the factor-scaled form.

Expected values are hand-calculated in the test bodies rather than copied from a
previous run.
