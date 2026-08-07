# CBAM Corridor Cost Model: Project Overview for the Team

*Written 5 August 2026, for Gayu, Riya and Alex to understand what the integrated model
does with the inputs each of you has supplied, so each of you can write the dissertation
section you own with an accurate picture of how it fits together.*

*Revised 7 August 2026. Unlike the dated `findings_*.md` notes, this document is meant to
track the current model, so it is updated in place rather than left as a snapshot. Three
things changed since the 5 August version and all three affect what you write:*

- ***Ammonia's CBAM default-value mark-up is 1%, not 30%.*** *Any ammonia CBAM or
  compliance figure taken from this model before 7 August is overstated (8.9% in 2026,
  28.7% from 2028) on the EU corridor. Regenerate, do not reuse.*
- ***The EU CBAM benchmark question is no longer blocked on data,*** *and now only
  changes the answer for hydrogen. See §7.*
- ***A third UK carbon price path exists*** *(`desnz`), alongside `frozen` and `linked`.*

---

## 1. What this model answers

The dissertation compares the delivered cost of shipping **hydrogen** and **ammonia**
along two real trade corridors, under two different carbon-regulation regimes:

| Corridor | Route | Regime that applies |
|---|---|---|
| **Halifax → Hamburg** | Canada to Germany | EU CBAM, EU ETS Maritime, FuelEU Maritime |
| **Ningbo → Felixstowe** | China to UK | UK CBAM (from 2027), UK ETS Maritime. No FuelEU (Felixstowe is outside EU jurisdiction) |

The central question: **what does carbon regulation cost per tonne of product on each
corridor, and how does that cost compare between hydrogen and ammonia, between
production pathways, and between the EU and UK regimes?**

The model is deliberately *not* a full "delivered cost" model (see §6, two of six
cost terms are a declared scope boundary). What it *does* fully answer, end to end, is the **carbon
compliance cost per tonne** (CBAM plus maritime ETS plus FuelEU) for every
corridor/product/pathway/year/price-scenario combination, and a bounded but real answer
to which production pathway is worth switching to on carbon-cost grounds alone
(marginal abatement cost).

**A methodological point worth stating explicitly if you're writing the methodology
chapter:** this is a **deterministic scenario calculator, not an optimisation model**.
There is no objective function, no decision variables being solved for, and no search
over a solution space. It enumerates a fixed scenario matrix and computes a closed-form
cost for each combination. Where it does identify a "best" option (cheapest pathway,
cheaper corridor, see §8), that is a ranking over a small enumerated candidate set of
routes that actually exist in the literature, not a solver result. Describing it as an
optimisation model would overclaim.

---

## 2. Who owns which input, and how it flows into the model

The model is built from three "layers" that plug into three data tables, one per
teammate:

```
Riya (Student 1)  -->  emissions_table.csv     -->  CBAM layer (cbam.py)
Gayu (Student 2)  -->  corridor_logistics.csv  -->  Maritime layer (ets_maritime.py, fueleu.py)
Samir (Student 3) -->  regulatory_constants.py, the model code, the join, the analysis
Riya (partial)    -->  commercial_inputs.csv    -->  Delivered-cost layer (still blocked)
Alex (Student 4)  -->  origin carbon price research (Canada, feeds regulatory_constants.py)
```

**Riya → embedded emissions.** For every corridor/product/pathway combination, the
tCO2e emitted per tonne of product produced. Four production pathways are modelled per
product where the literature supports them: `green_electrolysis`, `grey_smr` (or
`coal_gasification` on the China side), `blue_smr_ccs` (or `blue_ccs`), and
`cbam_default`, the IR 2025/2621 regulatory default value the EU/UK impose when a
declarant doesn't supply verified actual data. Riya's 4 August 2026 delivery also added
real, literature-sourced **production cost** per pathway (the largest single term in a
delivered cost), converted from USD to EUR at a fixed ECB reference rate.

**Gayu → maritime voyage data.** Distance, vessel specification, fuel burn, and the
resulting voyage CO2 (and now CO2e, see §5) for each corridor, at three speed
scenarios and (for Ningbo-Felixstowe) two routes (Suez vs. the Cape of Good Hope
diversion). Also delivered the **cargo tonnage per voyage** (§4), which is the number
that lets the model convert her per-voyage maritime costs into the per-tonne unit CBAM
works in.

**Alex → origin carbon price for Canada.** Under EU CBAM Article 9, an importer can
deduct any carbon price already effectively paid in the country of origin. Alex sourced
and corrected Canada's federal industrial (OBPS) carbon price schedule on 5 August 2026
(see §7 for the correction that was needed).

**Samir → everything that turns those two/three tables into a cost.** The regulatory
formulas (CBAM, ETS, FuelEU), the constants each formula depends on (all sourced from
primary legislation, see `regulatory_constants.py`), the join between the maritime and
CBAM layers, the validation that rejects malformed inputs before they reach the model,
and the analysis/sensitivity/plotting layer that turns model output into results-chapter
material.

---

## 3. The three cost layers, and how they combine

### Layer 1: CBAM (the border carbon tax)

A tax/certificate liability charged **per tonne of product**, based on its embedded
emissions, when it crosses into the EU or UK.

**EU CBAM:**

```
emissions_used   = embedded_emissions × (1 + markup(year, product))   [only if using a regulatory-default value]
EU CBAM cost/t   = max(0, emissions_used × cbam_factor(year) × (cert_price − origin_carbon_price))
```

- `cbam_factor(year)` is the EU's certificate-surrender phase-in: **2.5% in 2026, rising
  to 100% by 2034**. (Note: this is *not* the free-allocation share, which is the
  inverse. Confusing the two has inverted the whole result twice already in this
  project, hence the loud warning comment in the code.)
- `markup(year, product)`, penalises using the regulatory default instead of a verified
  actual emissions figure. Two things about it, and both were bugs that got fixed rather
  than design choices:
  - It applies **only** to the `cbam_default` pathway row, never to a literature pathway
    (fixed 29 July, see §7).
  - It is **not uniform across goods** (fixed 7 August). Fertiliser goods carry a flat
    **1%** in every year; everything else ramps **10%/20%/30%** (2026/2027/2028+). For
    this study that split matters directly: **ammonia is a fertiliser good** for CBAM
    purposes (CN 2814) and **hydrogen is not** (CN 2804). Riya and Alex in particular:
    any ammonia CBAM figure taken from this model before 7 August was overstated by
    8.9% in 2026 rising to 28.7% from 2028, on the EU corridor and on the study's
    primary scenario. Regenerate rather than reuse.
- The origin carbon price is credited **1-for-1 against the liability**, scaled by the
  same emissions and factor as the obligation itself, and floors at zero (also a fixed
  bug, the original spec had a units error here, see §7).

**UK CBAM** (from 2027 only, Ningbo-Felixstowe carries zero CBAM liability in 2026):

```
UK CBAM cost/t = embedded_emissions × rate_fraction × (UK_carbon_price − origin_carbon_price)
rate_fraction  = 1 − (baseline_free_allocation% × Article_16(14)_factor)
```

The UK scheme is structurally different from the EU's: it's a flat tax, not a
certificate-surrender system, and there's no smooth phase-in curve. `rate_fraction`
rises from **15.7% of the UK ETS price in 2027 to 33.0% by 2030**, derived from a real
UK installation's (Teesside Hydrogen Plant) historical free-allocation performance
under the retained EU ETS and the UK ETS. This was the single hardest regulatory fact
in the whole model to resolve (§7).

### Layer 2: Maritime (the ship's own voyage emissions, priced per voyage)

This is entirely Gayu's domain, translated into cost. The asymmetry between the two
maritime regimes **is one of the study's central findings**:

- **EU ETS** charges **50%** of an extra-EEA voyage's emissions (Halifax-Hamburg is
  extra-EEA) plus 100% of in-port emissions (currently disabled by default so results
  match Gayu's published figures exactly).
- **UK ETS** charges **0%** of the international ocean leg and **100%** of time spent
  in a UK port. For Ningbo-Felixstowe, that means the entire multi-week ocean crossing
  contributes nothing to UK ETS cost. Only the Felixstowe berth call does. This was
  re-verified against 7 independent sources after two earlier drafts of this project got
  it wrong by assuming EU-equivalent coverage.
- **FuelEU** (EU corridor only) is a pass/fail fuel-intensity penalty, not a smooth
  emissions charge: if the vessel's actual well-to-wake GHG intensity is above a
  yearly-tightening target, it pays €2,400 per tonne of VLSFO-equivalent deficit.
  Felixstowe is outside EU jurisdiction, so Ningbo-Felixstowe carries **no FuelEU cost
  at all**, a real cost difference between the corridors, not a modelling gap.

Underneath all three: daily fuel burn is fixed by engine power × load × SFOC (does
**not** vary with speed, a stated simplification, not a real ship's fuel curve); voyage
days = distance ÷ speed; voyage fuel = days × daily fuel; voyage CO2 = fuel × VLSFO
carbon factor (3.151 tCO2/t, from IMO MEPC 82/6/38).

### Layer 3: Marginal abatement cost (a separate question, not a border charge)

What does it cost to avoid one tonne of CO2 by switching from the dirtiest literature
pathway to a cleaner one, compared against that corridor's own carbon price?

```
MAC = (production_cost_alt − production_cost_ref) / (emissions_ref − emissions_alt)
```

This is the one delivered-cost-style question the model can answer **exactly** despite
conversion and shipping cost being unsourced, because both terms are pathway-invariant
and cancel out of the comparison. Verdicts are reported as `justified` / `marginal` /
`not justified` (a 10%-band "too close to call" middle state was added deliberately,
see §7, the China green ammonia case is a real example of why this matters).

### The join

```
Total compliance cost/t = CBAM cost/t + (EU ETS + FuelEU + UK ETS, per voyage) / cargo_tonnes
```

Only one regime's maritime terms are ever non-zero for a given corridor. EUR and GBP are
**never converted or combined** in a result, this is a deliberate modelling choice that
runs through the entire codebase (see §4).

---

## 4. The join between Gayu's and Riya's halves of the study

Gayu's maritime costs are per **voyage**. CBAM liability is per **tonne of product**.
Nothing in either original brief specified how many tonnes a voyage actually carries. This was a real gap, closed on 25 July when Gayu delivered her cargo-capacity notebook.

An 84,000 m³ carrier (the same peer-reviewed vessel class used for speed and port time)
at the IMO's 98% filling limit gives 82,320 m³ usable, which is:

- **56,142 t of ammonia** (density 682 kg/m³, NIH PubChem)
- **5,828 t of liquid hydrogen** (density 70.8 kg/m³, peer-reviewed corroboration)
- a ratio of **9.6 : 1**

This ratio is not a footnote. It drives the hydrogen-vs-ammonia comparison on its own:
every tonne of hydrogen absorbs 9.6× more of a voyage's carbon cost than a tonne of
ammonia does, purely from cargo density, before any pathway or regulatory difference is
even considered.

**Important caveat to carry into any write-up that uses the hydrogen figures:** the
84,000 m³ vessel is an ammonia carrier (operates at ‑33°C). It cannot physically hold
liquid hydrogen, which needs ‑253°C cryogenic containment, the largest liquid hydrogen
carrier ever built is 1,250 m³, and 40,000 m³ designs are still in development. Applying
the ammonia carrier's geometry to hydrogen is a **deliberate counterfactual** to isolate
the effect of cargo density alone, not a real shipping option today. Boil-off losses for
liquid hydrogen are not modelled. Label this explicitly wherever hydrogen per-tonne
figures appear.

---

## 5. What changed most recently (5 August 2026)

Two independent deliveries landed the same day and are both folded into the model:

1. **Gayu's maritime CO2e update.** From 1 Jan 2026, EU ETS maritime scope expanded
   beyond CO2 to also cover CH4 and N2O on a CO2-equivalent basis (UK ETS mirrors this
   from 1 July 2026 with identical factors). This moves the two headline maritime carbon
   costs up slightly (EU ETS Halifax-Hamburg mid-price: €43,208 → **€43,880**; UK ETS
   Ningbo-Felixstowe official price: £2,891 → **£2,936**). Distances, engine
   assumptions, and the FuelEU penalty are unaffected.

2. **Alex's Canada origin carbon price correction.** The figure used through 4 August
   (CAD 110/tCO2e flat) was an extrapolation from a superseded December 2020 policy
   document, never checked against a primary source. The real, currently-published path
   (after Bill C-4 permanently repealed the *consumer* carbon charge but left the
   *industrial* system in place) is **CAD 95 (2026) → 100 (2027-29) → 115 (2030)**, a
   materially lower and flatter schedule than the old figure implied, and now
   year-varying rather than flat throughout the whole 2026-2030 run.

3. **A second Canada hydrogen production-cost cross-check** (Ayub et al. 2024), added by
   Riya as a robustness check, not a primary input, see §6.

---

## 6. What is real vs. what is still a placeholder

This matters a lot for how confidently each of you can state results in your section.

| Table | Status |
|---|---|
| `emissions_table.csv` | **Real.** Riya, both products, both corridors, literature + IR 2025/2621 defaults. |
| `corridor_logistics.csv` | **Real.** Generated directly from Gayu's notebooks, pinned by 31 automated reproduction checks. |
| `commercial_inputs.csv`, production cost | **Real** as of 4 Aug 2026 (Riya). |
| `commercial_inputs.csv`, conversion & shipping cost | **Placeholder, and a declared scope boundary rather than a pending input.** No public source identified; the partner data route closed 6 Aug 2026. Both terms are pathway-invariant, so they cancel out of every within-corridor comparison the study actually makes. |

Because two of six delivered-cost terms (conversion, shipping) are still unsourced,
`run_delivered_cost()` in the code deliberately **raises an error** rather than silently
returning a wrong number. What *does* run end to end without any placeholder involved is
`run_compliance_matrix()`, the carbon-regulation cost per tonne (CBAM + maritime),
which is the dissertation's actual headline metric. The marginal abatement cost
(Layer 3) also runs cleanly despite the gap, because those two missing terms cancel out
of a pathway-to-pathway comparison.

The directory is still called `data/placeholder/` for historical reasons even though
most of what it now holds is real, sourced data. Worth knowing before assuming
"placeholder" means "fake" when reading the code.

---

## 7. Errors already found and fixed (worth knowing before you cite a number)

Several genuine bugs and regulatory misreadings were caught during development. All are
fixed and each is now covered by an automated test so it can't silently reappear, but
they're worth knowing about because early/cached numbers or intuitions from before the
fixes are wrong.

1. **Halifax-Hamburg distance was overstated by more than 2×** in the original build
   spec (~6,300 nm vs. the actual SeaRoute figure of 2,962 nm), which would have
   overstated that corridor's entire voyage emissions by the same factor.
2. **The origin-carbon-price deduction had a units error**, the spec subtracted a
   EUR-per-tonne *price* from a EUR *total*, which could even flip a positive liability
   negative. Fixed to scale the deduction by the same emissions and CBAM factor as the
   liability itself.
3. **The FuelEU penalty formula was missing a divisor**, overstating the penalty by
   roughly 90×. Re-derived from Annex IV Part B before implementing.
4. **The default-value markup (10/20/30%) was applied to every emissions row**, not
   just the `cbam_default` pathway rows it's legally meant to penalise, found and fixed
   29 July 2026. This changed literature-pathway EU CBAM figures by the markup
   percentage (9% too high in 2026, growing toward 30% too high by 2028+). UK CBAM
   figures were never affected by this bug.
5. **UK ETS maritime scope was assumed to mirror the EU's 50% international-voyage
   coverage** in two earlier drafts. It doesn't. The UK charges 0% of the international
   leg. Re-verified against 7 independent sources before finalising.
6. **The Canada origin carbon price was a stale, superseded extrapolation** (§5).
7. **A bare `justified`/`not justified` boolean would have hidden a 1%-margin call.**
   China green ammonia's abatement cost sits within 1% of the UK carbon price in 2030,
   a genuine coin-flip given how the underlying cost gap is sourced, not a clean
   pass/fail. A three-state verdict (`justified`/`marginal`/`not justified`) was added so
   this can't be reported as more confident than it is.

There is also one **known, currently unresolved modelling simplification** worth
flagging for the discussion chapter: the EU CBAM obligation in the model uses
`chargeable = embedded × CBAM_factor`, but Regulation (EU) 2023/956 Article 31 actually
requires `max(0, embedded − benchmark × (1 − CBAM_factor))`, i.e. the obligation should
be adjusted against a product benchmark, not just scaled by the phase-in factor. The two
formulas only agree in 2034. Reproducing a published external result (Ramsook et al.
2025, Trinidad & Tobago ammonia) confirms the benchmark form is the legally correct one.
The code currently understates that paper's published CBAM burden by roughly a third
under the simpler form.

**Updated 7 August 2026, and the status changed twice since this was written.** The data
blocker is gone: the revised 2026-2030 product benchmarks were read out of the Official
Journal text of IR 2026/1412 on 6 August (ammonia 1.522, hydrogen 7.98) and are in the
model. Switching is now blocked on a **decision, not a lookup**, because flipping the
mechanism does not rescale the results, it inverts which corridor the study concludes is
cheaper. That is Frano's call, not a code change.

The fertiliser mark-up fix then halved its scope. With ammonia's mark-up corrected, both
mechanisms now agree on ammonia and **only hydrogen still flips**. So if you are writing
the ammonia side, this open question no longer changes your direction, only the magnitude
of the lock-in penalty. If you are writing hydrogen, it still changes the answer.

Both formulas are implemented side by side in `validation/reference_case.py` and
`analysis/outputs.cbam_mechanism_comparison` sizes the choice on the current benchmarks,
so the effect is visible even though the headline model hasn't switched over.

---

## 8. Headline results (medium price scenario)

**2026, hydrogen:** Halifax-Hamburg's primary scenario (CBAM-default anchor) pays
**€15.97/t** in total carbon compliance cost. Ningbo-Felixstowe pays **£0.50/t**,
over 30× less, because UK CBAM hasn't started yet and UK ETS doesn't price the ocean
leg at all in 2026.

**2030, hydrogen**, with UK CBAM running at its real legislated rate (33.0% of the UK
ETS price): Ningbo-Felixstowe's primary scenario reaches **£434.41/t**, against
**€389.90/t** for Halifax-Hamburg. By 2030, CBAM dominates the total cost on both
corridors and the maritime terms become close to irrelevant.

**The corridor ordering flips in 2027, not 2030.** Ningbo-Felixstowe is cheaper in 2026
*only* because UK CBAM doesn't exist yet; it starts in 2027 and the ordering reverses
immediately. From there the gap **narrows** each year as the EU's CBAM factor ramps
(hydrogen: £181/t in 2027 down to £102/t by 2030). So the correct characterisation is
one sharp flip in 2027 followed by convergence, not a gradual UK overtake completing
in 2030. If you're writing the discussion chapter, this is the shape to describe.

> **IMPORTANT. If you have an earlier copy of this document or the README, the
> Halifax-Hamburg figures changed.** They previously read €13.07 (2026) and €411.00 (2030). Those
> predate the 5 August Canada origin carbon price correction and Gayu's CO2e update.
> Do not cite them. Ningbo-Felixstowe's figures are unaffected, Canada's origin price
> is an EU-side Article 9 deduction, and China's is zero either way. The 2026 figure
> went *up* and the 2030 figure went *down* for the same reason: the corrected Canada
> price path is lower than the old flat CAD 110 in 2026 (less deducted, so CBAM costs
> more) and higher by 2030 (more deducted, so CBAM costs less).

In every year and both corridors, the CBAM-default anchor sits **above** the literature
"high" bracket, a direct consequence of the regulation's deliberate conservative
mark-up design (it's meant to penalise not using verified data), not a modelling
artefact.

### Does carbon pricing actually change what a producer would choose? (added 5 Aug)

Four new analyses answer the "so what should they do" question rather than just
reporting cost. The headline answer is **no, not at these carbon prices**:

At 2030 medium prices, the **dirtiest pathway is still the cheapest** on every corridor
and every product, and that holds under the low, medium *and* high carbon price
scenarios. The recommendation doesn't flip, which means it isn't a restatement of the
price assumption, it's a finding.

The reason is a straightforward magnitude comparison. CBAM does penalise the dirty
route, but nowhere near enough to close the production cost gap:

| Corridor | Product | Green production premium | CBAM advantage to green | Share of gap closed |
|---|---|---|---|---|
| Halifax-Hamburg | hydrogen | €2,993/t | €233/t | **7.8%** |
| Halifax-Hamburg | ammonia | €481/t | €41/t | **8.5%** |
| Ningbo-Felixstowe | hydrogen | €4,235/t | €339/t | **8.0%** |
| Ningbo-Felixstowe | ammonia | €306/t | €102/t | **33.3%** |

Three of the four sit near 8%. The outlier is **Chinese ammonia at 33%**, and that is
exactly why China green ammonia is the one pathway in the whole study whose abatement
verdict comes out `marginal` rather than `not justified`. The two results are the same
fact seen from two directions, which is a useful consistency check on both.

**For the discussion chapter:** this is arguably the study's most policy-relevant
finding. CBAM at its legislated 2030 rates does not make green hydrogen or ammonia
commercially competitive on either corridor. It closes roughly a twelfth of the gap.
Note the honest caveat though. This rests on production cost figures where green
hydrogen has a 2.6× spread across three sources (see §7 and the Ayub cross-check), so
the *direction* is solid but the precise percentage is not.

---

## 9. How to run it / where to look

- `run_model.ipynb` is the entry point and produces every output end to end.
- `dashboard.py` (Streamlit), interactive scenario explorer over the same tested model,
  for exploring corridor/product/pathway/year/price combinations without touching code.
  Placeholder inputs and policy-uncertain what-ifs (e.g. UK CBAM phase-in overrides) are
  explicitly labelled in the UI rather than presented as forecasts.
- `tests/test_model.py`, the regulatory test suite. It pins every one of Gayu's
  published maritime figures exactly, so any future drift shows up as a test failure
  rather than a silent divergence. Run `pytest -q` for the current count rather than
  quoting one here, since it moves every time a fact gets pinned.

Output CSVs in `cbam_model/outputs/`. The five added 5 August 2026 for the choice and
timing questions:

| File | What it answers |
|---|---|
| `pathway_cost_ranking.csv` | Which production pathway is cheapest, per corridor/product |
| `pathway_choice_price_robustness.csv` | Does that answer survive the low/medium/high price scenarios? |
| `corridor_cost_comparison.csv` | Both corridors side by side, per year, in one currency |
| `corridor_crossover_year.csv` | The year the cheaper corridor flips (2027) |
| `abatement_breakeven_year.csv` | The year a pathway switch starts paying for itself |

Two caveats to read before quoting any of these. **`pathway_cost_ranking` is not a
delivered cost**, it's production cost plus CBAM only, because conversion, shipping and
maritime cost are all pathway-invariant and therefore cancel out of the *ranking* even
though they'd be needed for an absolute figure. That cancellation holds only while
conversion and shipping stay pathway-invariant, which is a property of how they're
currently populated, not a law of nature. **`abatement_breakeven_year` has a
`carbon_price_varies_by_year` column that must be read**, it's `False` on the UK
corridor because the UK ETS price is frozen (only 2026 was ever sourced), so a UK row
reporting no breakeven year is an artefact of that assumption, *not* evidence that
switching never pays there.
- `docs/cost_model_formulas.md`, the complete formula reference, one layer at a time,
  with a direct link from every formula to the function that implements it.
- `README.md`, the fullest narrative account of the project, including every
  correction and open item in more detail than this summary.
- `cbam_model/data/README.md`, the data contract for each of the three input tables:
  exact columns, units, and what's enforced automatically.

## 10. Open items

1. **Conversion and shipping cost per tonne**, a declared scope boundary, not a
   pending input, since 6 August 2026. It is what would be needed for a true
   delivered-cost figure (as opposed to the compliance-cost figure, which is
   unblocked and complete), and it is stated as a limitation in the methodology
   rather than left open. Both terms are pathway-invariant as currently held, so
   they cancel out of the within-corridor comparisons the study reports.
2. **UK ETS price held flat 2026-2030 in the baseline**, only the 2026 figure was ever
   sourced from a primary source. Two labelled alternatives now exist and neither is the
   baseline: `linked` (EU-UK ETS linkage, NOT law) and `desnz` (the UK government's own
   published traded carbon values, added 6 August, the only forward UK path with an
   official source). The DESNZ series is in **real 2025 prices** while every other price
   in the model is nominal, and it models a standalone UK ETS, so `desnz` and `linked`
   are alternative views of the same uncertainty and must never be combined.
3. **The EU CBAM benchmark-adjustment question** (§7), no longer a lookup. The
   2026-2030 benchmarks are in the model as of 6 August; what remains is a supervisor
   decision, and after the fertiliser fix it only changes the answer for **hydrogen**.
4. **Two production-cost gaps still span separate studies** (Canada hydrogen, China
   ammonia) rather than one internally-consistent source each. Every finding that
   depends on these has already been re-run against an independent IEA cost sourcing as
   a robustness check, and every verdict holds its sign under both, but this should
   still be stated as a limitation, not silently smoothed over.
