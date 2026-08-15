# Methodology source pack: Samir section (CBAM)

Everything needed to write the 500-word CBAM methodology section due 12 August
2026, plus the CBAM share of the shared 500-word Limitations.

Assembled 11 August 2026 from `cbam_model/model/cbam.py`,
`cbam_model/config/regulatory_constants.py`, `README.md` and
`docs/findings_2026-08-08.md`. Every value below carries its source and the date
it was retrieved.

---

## READ THIS FIRST: check the date on any formula you copy

**Fixed 12 August 2026.** `docs/cost_model_formulas.md` was dated 7 August and
printed the EU CBAM obligation as

    EU CBAM cost/t = max(0, emissions x cbam_factor(year) x (cert price - origin price))

That is the **factor-scaled** form, which the model stopped using on 7 August and
which the benchmark correction of 8 August superseded entirely. That file now
carries the benchmark form with the CSCF term, and its line citations were
re-checked against the code, so it is safe to write from again.
`docs/how_the_code_works.md` section 4 was corrected the same day, from 54.67 to
68.02 euros per tonne on the worked example.

The warning stands for any older copy of either file that is still circulating,
and for anything drafted from one before 12 August. If a draft contains 54.67 or
the factor-scaled formula, it predates the fix.

---

## 1. Scope: what is yours

The methodology chapter is four sections of 500 words. On the division the team
has been using since the literature review split:

| Owner | Methodology section |
|---|---|
| Riya | Production pathways, emissions inputs, CBAM defaults as primary scenario |
| Samir | **CBAM: both regimes, the free allocation adjustment, carbon prices** |
| Alex | Policy scenarios and the timeline |
| Gayu | Maritime: vessels, voyages, EU/UK ETS maritime, FuelEU |

Interfaces you should name but not explain, because they belong to someone else:
embedded emissions per tonne arrive from Riya's table, cargo tonnage arrives from
Gayu's capacity notebook and is the only point where the per-voyage and
per-tonne layers touch.

---

## 2. What has to be in 500 words

Ranked. Items 1 to 4 are compulsory and will consume the full budget if written
tightly. Everything below them goes to Limitations or the appendix.

1. **The EU obligation is a benchmark netting, not a factor scaling**, with
   IR 2025/2620 as the authority. This is the single most important sentence in
   your section because every EU number depends on it.
2. **The departure from the research proposal.** The proposal states CBAM cost is
   "the product of the obligation factor and the ETS price". You do not do that.
   Declare the change and why.
3. **The CBAM benchmark is not the EU ETS product benchmark.** They coincide for
   ammonia and differ by 56.8% for hydrogen. State the correction of 8 August.
4. **The two regimes are structurally different instruments**, certificate
   surrender against a tax, which is why the UK rate nets free allocation inside
   the rate and the EU nets it off the emissions base.

Suggested split of the 500: roughly 150 on the EU form and its authority, 100 on
the benchmark distinction and the correction, 120 on the UK rate formula, 80 on
carbon price inputs and scenarios, 50 on the mechanism comparison being retained
as a labelled alternative.

---

## 3. The formulas, exactly as implemented

### EU CBAM, per tonne of product

    E_used     = E x (1 + markup(year, product))        if using a regulatory default
               = E                                       if using a literature pathway

    chargeable = max(0, E_used - BM x (1 - f_y) x CSCF_y)

    cost/t     = max(0, chargeable x (P_cert - P_origin))

Where `f_y` is the CBAM factor, `1 - f_y` is the share of free allocation still
remaining, `BM` is the CBAM benchmark per tonne of product, and `CSCF_y` is the
cross-sectoral correction factor.

Source: `eu_cbam_cost()`, `cbam_model/model/cbam.py:43`.
Authority: IR 2025/2620 Annex, Equations 1, 2 and 6:

    FAA  = SEFA x M
    SEFA = CBAM_y x CSCF_y x BM      (Equation 6, defaults)
    SFA  = CBAM_y x CSCF_y x BM*     (Equation 2, actuals)

`CBAM_y` in the regulation is the Article 10a(1a) factor, the share of free
allocation remaining, which is `1 - cbam_factor(year)` in this model's terms.
Getting that inversion wrong has been caught twice in this project.

Floors at zero. Recital 16 confirms the adjustment may exceed embedded
emissions, leaving nothing due, and never produces a credit.

**Unit contract.** The benchmark is defined per tonne of product, so it can only
be netted off embedded emissions expressed per tonne of product. Every caller in
the model honours this. A caller passing whole-shipment emissions would get a
silently near-zero deduction.

**Origin carbon price.** Enters on the same basis as the obligation it offsets,
not as a flat subtraction from the total. Under Regulation (EU) 2023/956
Article 9 it reduces the number of certificates to be surrendered. Writing it as
a flat subtraction is a unit error that was present in the build spec and
corrected.

### UK CBAM, per tonne of product

    liability/t = E x r_y x (P_UK - P_origin)

    r_y         = 1 - (baseline free allocation % x Article 16(14) factor)

Zero for years before 2027. Source: `uk_cbam_cost()`,
`cbam_model/model/cbam.py:147`.

Authority: SI 2026/809, the Carbon Border Adjustment Mechanism (Calculation of
CBAM Rate and Determination of Carbon Price Relief) Regulations 2026, made and
in force 1 January 2027, implementing Finance Act 2026 s.149(4). Citation
updated 9 August 2026: these are no longer draft regulations, and earlier drafts
of the write-up called them draft.

Design intent, from the Analytical Annex "Free Allocation for CBAM Sectors": the
import charge is pegged to what a UK domestic producer in the same sector
effectively pays after their own free allowances, not to the full UK ETS price.

---

## 3a. The primary-law chain, read 11 August 2026

Read from the OJ text of Regulation (EU) 2023/956 (OJ L 130, 16.5.2023, p. 52).
**This is the original text, not the consolidated version.** See the warning at
the end of this section.

### Article 31, verbatim

> **Article 31, Free allocation of allowances under the EU ETS and obligation
> to surrender CBAM certificates**
>
> 1. The CBAM certificates to be surrendered in accordance with Article 22 of
> this Regulation shall be adjusted to reflect the extent to which EU ETS
> allowances are allocated free of charge in accordance with Article 10a of
> Directive 2003/87/EC to installations producing, within the Union, the goods
> listed in Annex I to this Regulation.
>
> 2. The Commission is empowered to adopt implementing acts laying down detailed
> rules for the calculation of the adjustment as referred to in paragraph 1 of
> this Article. Such detailed rules shall be elaborated by reference to the
> principles applied in the EU ETS for the free allocation of allowances to
> installations producing, within the Union, the goods listed in Annex I, taking
> account of the different benchmarks used in the EU ETS for free allocation
> **with a view to combining those benchmarks into corresponding values for the
> goods concerned**, and taking into account relevant input materials
> (precursors).

The emphasised clause is the primary-law basis for the CBAM benchmark being
**derived from but not equal to** the EU ETS benchmark. Until now that claim
rested on IR 2025/2620's Annex table plus recital 15. It now rests on the
enabling Article itself. Cite Article 31(2) for it.

### Article 6(2)(c): the statutory order of operations

> the total number of CBAM certificates to be surrendered, corresponding to the
> total embedded emissions [...] after the reduction that is due on the account
> of the carbon price paid in a country of origin in accordance with Article 9
> and the adjustment necessary to reflect the extent to which EU ETS allowances
> are allocated free of charge in accordance with Article 31

So the statutory sequence is: embedded emissions, less the Article 9 origin
carbon price reduction, less the Article 31 free allocation adjustment. That is
the model's structure.

### Article 9: the origin price reduces certificate *count*, not price

Article 9(1) gives "a reduction in the number of CBAM certificates to be
surrendered", and 9(4) empowers implementing acts on converting the yearly
average carbon price paid "into a corresponding reduction of the number of CBAM
certificates to be surrendered".

The model implements this as a price differential, `chargeable x (P_cert -
P_origin)`. That is arithmetically identical to a certificate-count reduction:
reducing the count by the ratio `P_origin / P_cert` and valuing the remainder at
`P_cert` gives the same total. **Say this explicitly in methodology.** The
Article speaks in certificate counts and the model works in prices, and the
equivalence is one line to state and awkward to be caught not having noticed.

### Article 7(1) and Annex II: hydrogen is direct-emissions only

> Embedded emissions in goods shall be calculated pursuant to the methods set
> out in Annex IV. **For goods listed in Annex II only direct emissions shall be
> calculated and taken into account.**

Annex II, under "Chemicals", lists exactly one entry: **2804 10 00 Hydrogen**.
Ammonia (2814) is not in Annex II, so ammonia carries direct plus indirect.

Two consequences.

1. The model already gets this right, but only because the IR 2025/2621 default
   values happen to carry no indirect figure for hydrogen. Cite Article 7(1)
   and Annex II as the reason instead. It is a rule, not a coincidence in a
   table.
2. **It explains the 56.8% benchmark gap, which the repo has been calling a
   plausible reading.** IR 2026/1412's recital says the section 2 benchmarks now
   "take into account their indirect emissions from electricity consumption", so
   the ETS hydrogen benchmark of 7.98 is a direct-plus-indirect figure. CBAM
   charges hydrogen on direct emissions only. IR 2025/2620 recital 17 states
   that mechanism for steel: where CBAM scope is narrower than ETS scope, only
   the direct emission share of the ETS benchmark is carried into the CBAM
   benchmark. Hydrogen is in the same position by Annex II. 5.089 / 7.98 = 0.638,
   so the CBAM benchmark is the roughly 64% of the ETS benchmark that is direct.

   The constants file's note that "hydrogen appears nowhere in the recitals" is
   still true, but the reasoning no longer depends on reading across from steel
   alone. Article 7(1) plus Annex II puts hydrogen in the narrower-scope
   category directly.

### Article 2(3)(a): there is a de minimis, and it is value-based

> this Regulation shall not apply to [...] goods [...] provided that the
> intrinsic value of such goods does not exceed, per consignment, the value
> specified for goods of negligible value as referred to in Article 23 of
> Council Regulation (EC) No 1186/2009

This applies to every Annex I good, hydrogen included. The research proposal's
introduction states that hydrogen "does not benefit from any minimum volume
exemption threshold" and that consequently every shipment triggers an
obligation. That claim needs re-checking against the 50-tonne mass threshold
introduced by Regulation (EU) 2025/2083, which is not in the text read here.

### WARNING: this was the original text, and two model constants disagree with it

EUR-Lex records the current consolidated version as **20 October 2025**, and the
act "has been changed", including by Regulation (EU) 2025/2083. The text above
is the 2023 original. Two places where the model and the original disagree, both
of which most likely resolve in the amendments:

| Model constant | Original text says |
|---|---|
| `EU_CBAM_FIRST_SURRENDER_DEADLINE = "2027-09-30"` | Article 22(1) and Article 6(1): **31 May**, first time in 2027 for 2026 |
| `CBAM_CERT_PRICE_AVERAGING = {2026: "quarterly", 2027: "weekly"}` | Article 21(1): **weekly**, with no 2026 carve-out |

Neither affects a cost result. Both need the consolidated text to confirm, and
both are exactly the kind of detail a viva picks. Pull the consolidated version
before citing Article 31, Article 21 or Article 22 in the write-up.

---

## 4. Every constant, with source and retrieval date

### EU

| Constant | Value | Source |
|---|---|---|
| CBAM factor | 2026 2.5%, 2027 5%, 2028 10%, 2029 22.5%, 2030 48.5%, reaching 100% in 2034 | Regulation (EU) 2023/956, free allocation phase-out schedule |
| CBAM benchmark, hydrogen (CN 2804 10 00) | **5.089** tCO2e/t | IR 2025/2620 Annex point 5, read from the OJ PDF, retrieved 8 Aug 2026 |
| CBAM benchmark, ammonia (CN 2814 10 00) | **1.522** tCO2e/t | same |
| EU ETS product benchmark 2026-2030, hydrogen | 7.98 | IR 2026/1412, adopted OJ text, published 29 June 2026, retrieved 6 Aug 2026 |
| EU ETS product benchmark 2026-2030, ammonia | 1.522 | same |
| EU ETS product benchmark 2021-2025 | hydrogen 6.84, ammonia 1.570 | IR 2021/447 Annex section 2 |
| CSCF | **1.0, assumed not sourced** | Was 100% across 2021-2025; no 2026 value published as of 8 Aug 2026. `CBAM_CSCF_IS_SOURCED = False` |
| Default value mark-up, ammonia | 1% flat, every year | IR 2025/2621, verified 7 Aug 2026 by division against the Commission's adopted workbook `DVs as adopted_v20260204.xlsx` |
| Default value mark-up, hydrogen | 10% (2026), 20% (2027), 30% (2028 onward) | same |
| Certificate price mechanism | Quarterly averaging 2026, weekly from 2027 | IR 2025/2548. Note this is a different regulation from 2025/2621, which was miscited once in this project |
| Q1 2026 certificate price, actual | EUR 75.36/tCO2e | EEX published figure. Used as a bounds check on the scenario range, not as a direct model input |
| First surrender deadline | 30 September 2027, for 2026 imports | Regulation (EU) 2023/956 |
| Hydrogen de minimis exemption | None | Unlike other covered goods, hydrogen has no mass or volume exemption threshold |

The decimal comma trap: the OJ prints "1,522" for 1.522 and "7,98" for 7.98.
Also, the draft annex circulated on 11 May 2026 does **not** match the adopted
IR 2026/1412 text on every row, so the draft must never be cited. Ammonia and
hydrogen happen to be unchanged between draft and adoption, but that could not
have been known in advance.

### UK

| Constant | Value | Source |
|---|---|---|
| Start | 1 January 2027 | HMRC CBAM policy summary. Ningbo-Felixstowe carries zero CBAM in 2026 |
| Instrument | Tax, no purchase or trading of certificates | Finance Act 2026; House of Commons Library CBP-9935 |
| Baseline free allocation | **86.49%**, mean of scheme years 2019, 2022, 2023 | Finance Act 2026 s.149(4) defines the three-year basis. 2019 from the Union Registry bulk export, installation ID 201961, retrieved 31 July 2026. 2022 and 2023 from Analytical Annex Table 4 |
| Article 16(14) factor | 2027 0.975, 2028 0.95, 2029 0.9, 2030 0.775 | Retained Delegated Regulation (EU) 2019/331 as amended by the Greenhouse Gas Emissions Trading Scheme (Amendment) Order 2026 |
| Resulting rate fraction | 15.7% of the UK ETS price in 2027, rising to 33.0% in 2030 | Computed, `uk_cbam_rate_fraction()` |
| Statutory UK ETS price | Quarterly mean of auction clearing prices for the preceding quarter | SI 2026/809 reg. 3, implementing FA 2026 s.149(3) Step 1 |
| Price actually used | GBP 49.41/tCO2e, annual mean of 2026 UKA December futures settlement prices | UK ETS Authority determination. **An approximation of the statutory series, not the series itself.** Say so |
| Country differentiation | None in year one, single flat default per CN code | HMRC policy summary |
| Indirect emissions | From 2029 at the earliest | Policy position, not statutory. FA 2026 s.148 defines embodied emissions broadly and lets the Treasury narrow it by regulation, so cite the policy papers and secondary legislation for this, **never the Act** |
| Value threshold | GBP 50,000, a value threshold not the EU's 50-tonne mass threshold | HMRC policy summary |
| First payment deadline | 31 May 2028, for the 2027 accounting period | HMRC policy summary |

### Carbon prices in

| Input | Treatment |
|---|---|
| EU ETS / CBAM certificate price | Three scenarios, low/medium/high, anchored and linearly interpolated between anchor years. Article 21 pegs the certificate price to the EU ETS average, which is why the same price feeds both |
| UK ETS price | Three labelled forward paths: `frozen`, `desnz` (DESNZ published traded carbon values), `linked` (EU-UK linkage, **explicitly not law**) |
| Origin carbon price, Canada | CAD 95 (2026), 100 (2027-2029), 115 (2030). In EUR at 1 CAD = 0.62393, the ECB reference rate of 23 July 2026: 59.27, 62.39, 71.75 |
| Origin carbon price, China | Zero in every year. China's national ETS covers power, steel, cement and aluminium; it has not been extended to chemicals, so neither hydrogen nor ammonia production is priced |

---

## 5. Departures from the research proposal that must be declared

The proposal is at `~/Downloads/CBAM Research Proposal.pdf`. Three of its
methodology commitments no longer describe what the model does.

| Proposal says | Model does | Where to declare it |
|---|---|---|
| "CBAM cost is the product of the obligation factor and the ETS price" (s.5) | Benchmark netting per IR 2025/2620 | **Methodology.** This is item 2 in section 2 above |
| Total delivered cost = production + conversion and carrier + shipping + CBAM + ETS maritime + FuelEU (s.6) | **Three of six.** `total_compliance_cost_per_tonne` = CBAM + EU ETS + FuelEU + UK ETS. Production cost exists in the model but is a comparator and a denominator, never summed into a delivered cost. Conversion, carrier and freight are absent. **No delivered cost figure exists in any of the 30 output artefacts** | Limitations, and the objective and RQ wording need fixing |
| Validation against MCG's HyPACT 2.0 dataset (p.1, s.6, timeline) | Not available. The proposal pre-authorises the fallback: "If access is delayed, complete a transparent limitation section and use public/peer-reviewed benchmarks instead" | Limitations, quoting the proposal's own contingency |

The proposal's reference list does not contain IR 2025/2620, which is now the
central instrument. It cites IR 2025/2621 (default values) and IR 2025/2548
(certificate price) only. Update the reference list.

---

## 6. What the model retains as a labelled alternative

Both mechanisms stay implemented. `EU_CBAM_MECHANISMS = ("factor_scaled",
"benchmark_shielded")`, default `benchmark_shielded`, and
`analysis.outputs.cbam_mechanism_comparison` reports them side by side into
`outputs/cbam_mechanism_comparison.csv`.

Worth one sentence in methodology: the size of the modelling choice stays
visible in the results rather than being asserted away.

---

## 7. CBAM material for the shared 500-word Limitations

Ranked by how much a marker would care. The Limitations budget is shared across
four people, so expect to get 125 words. Take the first two and offer the rest to
the appendix.

1. **The CBAM benchmarks are provisional.** IR 2025/2620 recital 10: the 2026
   benchmarks are based on *estimated* 2026-2030 ETS benchmarks, to be reviewed
   within one month of the final ones being published, with updated values
   applying to imports from 1 January 2027. IR 2026/1412 published the final ETS
   benchmarks on 29 June 2026, so a revision was due by roughly end of July. None
   found as of 8 August 2026. If one appears, the 2027-2030 hydrogen benchmark
   moves and every corridor result moves with it.
2. **CSCF is an assumption, not a source.** Held at 1.0. A CSCF below 1 would
   reduce the shield and raise EU CBAM liability on both products.
3. **The UK ETS price is an approximation of a known statutory series.** See the
   table above. The two track each other closely, so it is defensible, but it is
   an approximation of the quarterly auction mean rather than the mean itself.
4. **The UK direct-only rule is not represented.** UK CBAM charges direct
   emissions only until 2029; the model applies full embedded from 2027. Effect
   on the primary scenario: zero for hydrogen, which has no indirect default
   value at all, and 3.5% to 4.4% for ammonia in two years.
5. **Conversion, carrier and freight cost are a scope boundary**, not a pending
   input. All are invariant to production pathway, so they cancel out of every
   within-corridor comparison the study makes. The study reports carbon
   compliance cost per tonne, not delivered cost, and the write-up must say so
   in those words.

   **Sweep warning.** The README was converted to scope-boundary language on
   6 August but four other files still frame this as a missing owner:
   `total_cost.py:259` ("nobody owns those inputs yet"), `dashboard.py:315`,
   and `build_notebooks.py:40` and `:438`. `generate_status_report.py` also
   still lists ammonia emissions as pending Riya and production cost as having
   no owner, both of which were delivered on 4 August, so the PDF it generates
   is stale. Fix before any of these is shown to a supervisor or an examiner.
6. From the proposal's own limitations, still valid: deterministic design with
   static parameters per scenario; THETIS-MRV operator registration unavailable
   so shipping emissions are validated against IMO and EU MRV aggregates; static
   exchange rates across EUR, GBP and CAD.
7. From the proposal's limitations, **RESOLVED 15 August 2026**: it claims the
   model "cannot evaluate production pathway granularity for the
   Ningbo-Felixstowe corridor to the same extent" because UK CBAM uses a single
   default per CN code. The limitation still holds, and more narrowly than the
   proposal put it.

   It does not affect the literature pathways. Coal gasification, blue CCS and
   green electrolysis on that corridor use Riya's LCA figures and are unaffected
   by how the UK sets defaults, so pathway granularity is reported normally.

   It affects the `cbam_default` pathway only, and there it is worse than a
   granularity problem. UK CBAM defaults are a single global average per CN
   code, weighted by the production volumes of the UK's main trading partners.
   The government considered jurisdiction-specific values and rejected them as
   "deemed infeasible by 2027". HMRC has not published the figures: checked
   15 August 2026, ammonia-specific values expected late 2026, after
   submission. The model substitutes the EU's China-specific IR 2025/2621
   default, which is not what UK law specifies.

   State the direction of the error, since it is inferable and runs against
   intuition. A global average is diluted by cleaner origins, so it sits below
   a value set for a high-intensity exporter. The substitution therefore most
   likely **overstates** UK CBAM liability on this corridor.

   Cite CITP on the mechanism rather than presenting it as an original
   observation: using global averages instead of country-specific defaults
   understated emissions from high-intensity origins by 1.48 MtCO2e across four
   sectors in 2023, about GBP 1.62bn, roughly 10% of CBAM imports.
   https://citp.ac.uk/publications/default-values-in-the-uks-cbam

---

## 8. Appendix candidates

Material that is real, sourced and will not fit in 500 words.

- The full UK CBAM rate derivation: three baseline years, their emissions and
  free allocation figures, the 86.49% mean, the Article 16(14) factors, and the
  resulting 15.7% to 33.0% path.
- The mark-up verification table (the six goods checked by division against the
  Commission workbook).
- The CBAM benchmark against ETS benchmark comparison, and the 8 August
  correction with its three dead findings.
- `cbam_mechanism_comparison.csv` in full.
- The Canada origin carbon price path and the 5 August correction that replaced
  an extrapolated CAD 110 flat figure.

---

## 9. Verification status of what you are about to cite

| Item | Status |
|---|---|
| IR 2025/2620 Annex point 5 benchmark table | Read from the OJ PDF |
| IR 2025/2620 recitals 10, 15, 17 | Read from the OJ PDF |
| IR 2026/1412 Annex section 2 | Read from the adopted OJ text |
| SI 2026/809 reg. 3 | Read, legislation.gov.uk |
| Finance Act 2026 s.148, s.149 | Read |
| House of Commons Library CBP-9935 | Read from the briefing PDF |
| Regulation (EU) 2023/956 Articles 6, 7, 9, 21, 22, 31, Annexes I, II, IV | **Read 11 August 2026, original OJ text.** See section 3a. Consolidated version (20 October 2025) still to be checked |
| IR 2025/2621 mark-up schedule | Verified by division against the Commission's adopted workbook, not from the regulation text |

The remaining gap is the **consolidated** version of 2023/956. Article 31 itself
is now read and quoted in section 3a, which closes outstanding item 4 on the
literature review source list, but two model constants disagree with the
original text in ways that point at the amendments.
