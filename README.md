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

Hydrogen does not. The frozen and DESNZ paths both flip back to
Ningbo-Felixstowe from 2028, while the linkage path keeps Halifax-Hamburg
cheaper for the rest of the horizon, because a UK price converging upward on
the EU price raises UK CBAM enough to hold the ordering. So on hydrogen the
corridor conclusion from 2028 rests on the UK price assumption and has to be
reported with the path named. Note the linkage path is explicitly not law.

This split appeared when the mechanism moved. Under `factor_scaled` all three
paths agreed on both products, and the README previously claimed that as a
settled robustness result.

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
95% to 146% and the breakeven from GBP 75.36 to GBP 91.60. **The open CBAM
mechanism decision narrows**: both mechanisms now agree on ammonia's corridor
ordering, and only hydrogen still inverts.

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

### Competitiveness: absolute cost and exposure point opposite ways

Added 6 August 2026. `analysis.outputs.competitiveness_burden` and
`competitiveness_asymmetry`, answering the competitiveness half of the EU-UK
asymmetry objective. Every other output reports compliance cost in absolute
terms, which says how much carbon regulation costs but not whether it is
material to the traded good.

Compliance cost as a share of production cost, `cbam_default`, medium prices:

| Product | Year | Halifax-Hamburg | Ningbo-Felixstowe | More exposed |
|---|---|---|---|---|
| Ammonia | 2027 | 1.03% | 9.51% | UK |
| Ammonia | 2030 | 15.62% | 20.00% | UK |
| Hydrogen | 2027 | 4.85% | 20.52% | UK |
| Hydrogen | 2029 | 28.96% | 29.00% | **marginal, do not report a direction** |
| Hydrogen | 2030 | 63.45% | 43.12% | **EU** |

The 2030 hydrogen row is the finding. In absolute terms Halifax-Hamburg is the
cheaper corridor that year, but it carries the **heavier** burden relative to
what the product costs to make, because Chinese hydrogen production cost
(EUR 1,180.7/t) is nearly double the Canadian figure (EUR 614.5/t). Reporting
only absolute cost would state the competitiveness asymmetry backwards. A test
pins that divergence.

Hydrogen 2029 splits the corridors by 0.04 percentage points and is banded
`marginal` on the same 10% relative rule used for abatement verdicts.

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
that is cheaper in 2026 is the wrong one to commit to, on both products.** A
firm reading the 2026 cost table picks Ningbo-Felixstowe; the present value of
the tenor says Halifax-Hamburg. At 8% real over the modelled years:

| Product | Spot-cheapest 2026 | PV-cheapest | Lock-in regret | Breakeven switching cost |
|---|---|---|---|---|
| Ammonia | Ningbo-Felixstowe | Halifax-Hamburg | 146% | GBP 91.60 |
| Hydrogen | Ningbo-Felixstowe | Halifax-Hamburg | 109% | GBP 491.95 |

Switching costs are **GBP per tonne of annual contracted volume**, not per tonne
shipped. Read the units note in `model/switching.py` before quoting either.

The reversal is confined to 2026 and survives both beyond-horizon treatments, so
it is not an artefact of the extrapolation assumption; a test enforces that. The
mechanism is regulatory timing alone: UK CBAM starting a year later than the EU's
creates a one-year advantage that a ten-year commitment converts into a
liability. That is the institutional-theory half of the argument and the
asset-specificity half meeting in one number.

No switching cost is claimed. The finding is the **threshold**, and the
discussion argues about which side of it real corridor-specific sunk costs fall.

**This result is conditional on the CBAM mechanism choice**, and the mechanism
moved to `benchmark_shielded` on 7 August 2026, so the figures above have been
re-derived on it. The reversal now splits by product:

| product | decision year | myopic | committed | regret | breakeven (GBP/t annual volume) |
|---|---|---|---|---|---|
| Ammonia | 2026 | Ningbo-Felixstowe | Halifax-Hamburg | 33.5% | 38.72 |
| Hydrogen | 2027 | Halifax-Hamburg | Ningbo-Felixstowe | 4.2% | 43.24 |

The *existence* of a myopia trap survives both mechanisms; its year, direction
and magnitude do not. Hydrogen's 4.2% regret is thin enough that it should be
reported as marginal rather than as a decision, on the same principle the
abatement and switching verdicts already apply. See unresolved item 1 below:
the mechanism is Samir's decision and is not yet confirmed by the supervisor,
so this section should be written up with that stated.

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
   Both sit side by side in `validation/reference_case.py`.

   **Benchmarks sourced 6 August 2026, and the blocker is gone.** Commission
   Implementing Regulation (EU) 2026/1412 of 26 June 2026, published 29 June
   2026, Annex section 2, read off the adopted Official Journal text:

   | Benchmark | 2021-2025 (IR 2021/447) | 2026-2030 (IR 2026/1412) | Change |
   |---|---|---|---|
   | Ammonia | 1.570 | 1.522 | -3.1% |
   | Hydrogen | 6.84 | 7.98 | **+16.7%** |

   The directions differ and the hydrogen rise is not an error. Delegated
   Regulation (EU) 2024/873 folded hydrogen from water electrolysis into the
   hydrogen benchmark, and section 2 benchmarks now count indirect emissions
   from electricity consumption, so a wider and more electricity-intensive
   population lifts the hydrogen benchmark even while the overall free
   allocation envelope falls by more than 16%. Do not cite the draft annex
   circulated on 11 May 2026: it differs from the adopted text on several rows
   (heat 7,4 to 7,2, fuel 10,7 to 10,4, aromatics 0,0117 to 0,0116), though
   ammonia and hydrogen happen to be unchanged.

   **The default mechanism was switched to `benchmark_shielded` on 7 August
   2026, on Samir's decision, and is not yet confirmed by the supervisor.**
   The plan had been to flip `EU_CBAM_DEFAULT_MECHANISM` once the benchmarks
   landed, and that is what happened. For **hydrogen** it does not rescale the
   results, it **inverts the headline corridor finding**, so it is recorded
   here as a methodological decision rather than a configuration change. Both
   forms stay implemented and one constant reverses it.

   Figures re-derived 7 August 2026, after the fertiliser mark-up fix. That fix
   is what narrowed this: cutting ammonia's mark-up from 30% to the legislated
   1% lowered EU ammonia liability enough that the benchmark shield no longer
   flips the ammonia ordering. **The decision is now a hydrogen-only question.**

   | | Cheaper corridor, 2026 → 2030 | First lock-in reversal | Regret | Breakeven switching cost |
   |---|---|---|---|---|
   | **Ammonia**, `factor_scaled` | NF, then HH 2027 onward | 2026 | 145.7% | GBP 91.60 |
   | **Ammonia**, `benchmark_shielded` (current default) | NF, then HH 2027 onward — *identical* | 2026 | 33.5% | GBP 38.72 |
   | **Hydrogen**, `factor_scaled` | NF, then HH 2027 onward | 2026 | 108.7% | GBP 491.95 |
   | **Hydrogen**, `benchmark_shielded` (current default) | NF, HH 2027, then **NF 2028 onward** | 2027 | 4.2% | GBP 43.24 |

   So for ammonia the choice never changed *which* corridor to commit to, only
   how costly the wrong choice is. For hydrogen it changes the direction, which
   is why the switch has to be defended in the methodology rather than noted in
   a changelog.

   The asymmetry is structural: the EU corridor's liability rises steeply in the
   early years under the benchmark form, while the UK corridor is untouched,
   because the UK scheme nets free allocation off inside its own rate fraction.
   So this is not a neutral modelling refinement, it changes which regime the
   study concludes is more exposed for hydrogen.
   `test_the_mechanism_choice_inverts_the_corridor_finding` pins every ordering
   in the table above and fails loudly if either form's results move without
   the findings being rewritten.

   The gap is also not uniform in sign across pathways. Under the benchmark
   form **every green pathway on the EU corridor owes zero CBAM in every
   modelled year**, because they sit below the benchmark and free allocation
   shields it. Pathways above the benchmark owe much more: `cbam_default`
   hydrogen goes from EUR 6.17 to EUR 85.44 per tonne in 2026 (13.9x) and from
   EUR 370.09 to EUR 540.13 in 2030 (1.5x). So the superseded `factor_scaled`
   form materially **understated how far CBAM closes the green premium**, and
   the primary `cbam_default` scenario sat on the understated side. Adopting
   the benchmark form is what corrects that. The finding that the
   production cost gap dwarfs the CBAM differential holds either way.
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
4. **Conversion and freight cost per tonne.** A stated scope boundary, not a
   pending input. No public source was identified and the industry partner
   route closed on 6 August 2026, so the study reports carbon compliance cost
   per tonne rather than delivered cost, and says so in the methodology.
   Production
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
