# CBAM Corridor Cost Model — Formula Reference

This is the complete cost model, one layer at a time, matching the implementation in
`cbam_model/model/`, `cbam_model/config/regulatory_constants.py` and
`cbam_model/config/vessel_logistics.py` exactly. Each formula links to the function it
comes from.

**Updated 12 August 2026, and the EU CBAM formula changed.** Between 7 and 8 August the
model switched from the factor-scaled obligation to the benchmark-shielded one, and then
corrected which benchmark it nets off. This file was not updated at the time and printed
the superseded formula for four days. If you took the EU CBAM formula from here before
12 August, take it again from section "Layer 1 — CBAM" below or from
`cbam_model/model/cbam.py` directly. Every line citation in this file was also re-checked
against the code on 12 August.

Previously updated 7 August 2026 for the fertiliser mark-up correction (the mark-up now
takes the product, and is 1% flat for ammonia rather than the 10/20/30 ramp), and
5 August 2026 for the CO2e maritime update and the year-varying Canada origin carbon
price. See `docs/findings_2026-08-05.md` and `docs/findings_2026-08-08.md` for what
changed and why.

## Top level

$$
\text{Total compliance cost per tonne} = \text{CBAM cost per tonne} + \frac{\text{EU ETS} + \text{FuelEU} + \text{UK ETS (per voyage)}}{\text{cargo tonnes}}
$$

Only one regime's maritime terms are ever non-zero for a given corridor — EU trips carry
EU ETS + FuelEU, UK trips carry UK ETS only. EUR and GBP are never converted or combined.

Source: `compliance_cost_per_tonne()`, `cbam_model/model/total_cost.py:247`

---

## Layer 1 — CBAM (border tax on the fuel's embedded emissions)

### EU

$$
\text{emissions}_{\text{used}} =
\begin{cases}
\text{embedded emissions} \times (1 + \text{markup}(year, product)) & \text{using the regulatory default} \\
\text{embedded emissions} & \text{using a literature pathway}
\end{cases}
$$

The obligation nets off the free allocation a domestic EU producer would still receive,
measured against a product benchmark. This is the `benchmark_shielded` mechanism and it
is the model's default.

$$
\text{chargeable} = \max\Big(0,\ \text{emissions}_{\text{used}} - \text{BM}_g \times \big(1 - \text{cbam\_factor}(year)\big) \times \text{CSCF}(year)\Big)
$$

$$
\text{EU CBAM cost/t} = \max\Big(0,\ \text{chargeable} \times \big(\text{cert price} - \text{origin carbon price}(year)\big)\Big)
$$

| Term | Meaning |
|---|---|
| `cbam_factor(year)` | EU's certificate-surrender phase-in: 2.5% (2026) rising to 100% by 2034. Note it enters as `1 - cbam_factor`, because IR 2025/2620's CBAM\_y is the share of free allocation **remaining**, not the phase-in share |
| $\text{BM}_g$ | **CBAM benchmark**, IR 2025/2620 Annex point 5.3. Hydrogen **5.089**, ammonia **1.522**, both tCO2e per tonne of product. This is *not* the EU ETS product benchmark: the two coincide for ammonia and differ by 56.8% for hydrogen (ETS hydrogen is 7.98). Netting off the ETS figure was the material error corrected on 8 August 2026 |
| `CSCF(year)` | Cross-sectoral correction factor from Equations 2 and 6. **Held at 1.0 as a stated assumption, not a sourced figure.** It was 100% across 2021-2025 and no 2026 value had been published. `CBAM_CSCF_IS_SOURCED` is False and the outputs carry the flag |
| `markup(year, product)` | Penalty for using the default instead of verified data. **Not uniform across goods** (corrected 7 Aug 2026): fertiliser goods, which for CBAM purposes includes **ammonia** (CN 2814), carry a flat **1%** in every year; everything else, including **hydrogen** (CN 2804), ramps **10% (2026) / 20% (2027) / 30% (2028+)**. Verified by division against the Commission's adopted default-values workbook, which publishes each value before and after mark-up |
| origin carbon price(year) | Credited 1-for-1 against the liability, floored at zero. Year-varying for Canada as of 5 Aug 2026 — see below |

Unit warning: the benchmark is defined per tonne of product, so it can only be netted off
an emissions figure that is itself per tonne of product. Every caller in this model passes
it that way. A caller passing whole-shipment emissions would get a silently near-zero
deduction, and nothing inside the function can detect that.

**The superseded form is still implemented and still reachable**, as the `factor_scaled`
mechanism, so the results chapter can show both side by side
(`analysis.outputs.cbam_mechanism_comparison`, `outputs/cbam_mechanism_comparison.csv`):

$$
\text{chargeable}_{\text{factor\_scaled}} = \text{emissions}_{\text{used}} \times \text{cbam\_factor}(year)
$$

Do not quote that one as the model's answer. The two forms only converge in 2034, and the
gap between them is not uniform in sign: under the benchmark form a green pathway sitting
below the benchmark owes zero CBAM, while a pathway above it owes considerably more.

Source: `eu_cbam_cost()`, `cbam_model/model/cbam.py:43` · Regulation (EU) 2023/956 Art. 9
and Art. 31, IR 2025/2620 (Annex Equations 1, 2 and 6), IR 2025/2621 (default values)

**Origin carbon price (Canada), corrected and made year-varying 5 August 2026.** The
figure used through 4 August, CAD 110/tCO2e flat, was an extrapolation from a December
2020 plan that was superseded before it was ever checked against a primary source. The
real path, published 15 May 2026 after Bill C-4 permanently repealed the adjacent
consumer carbon charge:

| Year | CAD/tCO2e | EUR/tCO2e |
|---|---|---|
| 2026 | 95 | 59.27 |
| 2027 | 100 | 62.39 |
| 2028 | 100 | 62.39 |
| 2029 | 100 | 62.39 |
| 2030 | 115 | 71.75 |

Converted at the 23 July 2026 ECB reference rate, 1 CAD = 0.62393 EUR. China's origin
price is 0 in every year — hydrogen and ammonia production are confirmed out of scope of
China's national ETS. Source: `origin_carbon_price_eur(corridor, year)`,
`cbam_model/config/regulatory_constants.py`. Full background:
`docs/political_economy_canada.md`.

### UK

$$
\text{UK CBAM cost/t} = \text{embedded emissions} \times \text{rate fraction} \times \big(\text{UK carbon price} - \text{origin carbon price}\big)
$$

$$
\text{rate fraction} = 1 - (\text{baseline free allocation \%} \times \text{Article 16(14) factor})
$$

Zero if `year < 2027` (the scheme does not exist yet). The rate fraction was resolved on
31 July 2026 from the CBAM (Calculation of CBAM Rate and Determination of Carbon Price
Relief) Regulations and Finance Act 2026 s.149(4). Those Regulations are **no longer
draft**: they were made as **SI 2026/809**, in force 1 January 2027, confirmed 9 August
2026. Cite the SI, not the draft.

Baseline free allocation is 86.49%, averaged over scheme years 2019, 2022 and 2023. The
Article 16(14) factors run 0.975 (2027), 0.95 (2028), 0.9 (2029), 0.775 (2030), giving a
rate of 15.7% of the UK ETS price in 2027 rising to 33.0% by 2030. Years outside 2027-2030
raise rather than extrapolate. China's origin price is 0 in every year, same reasoning as
the EU side.

**Two caveats on this layer, both to carry into the write-up.**

*The UK carbon price is an approximation of the statutory series.* SI 2026/809 regulation
3, implementing s.149(3) Step 1, defines the price input as "the mean average of all
auction clearing prices for UK ETS allowances during the quarter preceding quarter Q",
falling back to the most recent quarter that held an auction. The model uses GBP
49.41/tCO2e, which is an **annual** mean of UKA December futures settlement prices from
the UK ETS Authority determination. The two track each other closely, so this is a
defensible approximation rather than a wrong number, but the methodology must describe it
as an approximation of the statutory series rather than as the series itself. Three
labelled price paths exist: `frozen` (GBP 49.41 held flat), `linked` (EU-UK scheme
linkage, a scenario and not law) and `desnz` (the UK government's published traded carbon
values).

*The direct-only rule is not represented.* UK CBAM charges direct emissions only until
2029 at the earliest, and the model applies full embedded emissions from 2027. The effect
on the primary scenario is zero for hydrogen, which has no indirect default value at all,
and 3.5% to 4.4% for ammonia in two years. Confirmed against primary text on 9 August
2026: direct-only is a launch-scope policy position, not a statutory restriction. Finance
Act 2026 s.148 defines embodied emissions broadly and lets the Treasury narrow it by
regulation, so cite the policy papers and secondary legislation for this, never the Act.

Source: `uk_cbam_cost()`, `cbam_model/model/cbam.py:147` ·
`rc.uk_cbam_rate_fraction()` for the full derivation

---

## Layer 2 — Maritime (the ship's own voyage emissions, per voyage)

### CO2e, added 5 August 2026

From 1 January 2026, EU ETS maritime scope covers CH4 and N2O alongside CO2, on a
CO2-equivalent basis (EMSA's ETS extension page). UK ETS mirrors this from 1 July 2026
with identical factors (SI 2026/392, Schedule 2A). Both ETS cost formulas below now take
CO2e, not CO2, as of this update — this is Gayu's notebook update
(`FINAL_shipping_maritime_cost_model_updated.ipynb`), section 5b.

$$
\text{CO}_2\text{e} = \text{CO}_2 + \big(\text{fuel} \times f_{\text{CH}_4} \times \text{GWP}_{\text{CH}_4}\big) + \big(\text{fuel} \times f_{\text{N}_2\text{O}} \times \text{GWP}_{\text{N}_2\text{O}}\big)
$$

| Term | Value | Source |
|---|---|---|
| $f_{\text{CH}_4}$ | 0.00005 g CH4 / g fuel | IMO MEPC.391(81), Annex 10, Appendix 2 |
| $f_{\text{N}_2\text{O}}$ | 0.00018 g N2O / g fuel | IMO MEPC.391(81), Annex 10, Appendix 2 |
| $\text{GWP}_{\text{CH}_4}$ | 28 | IMO MEPC.391(81) §2.4, IPCC AR5 |
| $\text{GWP}_{\text{N}_2\text{O}}$ | 265 | IMO MEPC.391(81) §2.4, IPCC AR5 |

Applied separately to the voyage total and the port call, at slightly different rounding
precision to match Gayu's notebook exactly (4dp/2dp/1dp for the voyage, 5dp/3dp/2dp for
the port).

Source: `voyage_co2e_tonnes()`, `port_co2e_tonnes()`, `cbam_model/config/vessel_logistics.py`

### EU ETS

$$
\text{EU ETS cost} = \Big(\text{voyage CO}_2\text{e} \times 0.50 + \text{berth CO}_2\text{e} \times 1.00\Big) \times \text{phase-in}(year) \times \text{ETS price}
$$

0.50 because the corridor is an extra-EEA voyage (EU only taxes half of an international
leg's emissions); the berth term is 1.00 (intra-EEA rate) but disabled by default so
results reproduce the reference maritime dataset exactly.

Source: `eu_ets_maritime_cost()`, `cbam_model/model/ets_maritime.py:12`

### UK ETS

$$
\text{UK ETS cost} = \Big(\text{port CO}_2\text{e} \times 1.00 + \text{voyage CO}_2\text{e} \times c\Big) \times \text{UK carbon price}
$$

$$
c = \begin{cases} 0 & \text{current law} \\ 0.50 & \text{proposed international expansion (not law)} \end{cases}
$$

Source: `uk_ets_maritime_cost()`, `cbam_model/model/ets_maritime.py:42`

### FuelEU (EU only)

$$
\text{balance} = \big(\text{target intensity}(year) - \text{actual intensity}\big) \times \text{energy consumed (MJ)}
$$

$$
\text{FuelEU cost} =
\begin{cases}
0 & \text{balance} \ge 0 \ \text{(compliant)} \\[6pt]
\dfrac{|\text{balance}|}{\text{actual intensity} \times 41{,}000} \times \text{€}2{,}400 & \text{balance} < 0 \ \text{(deficit)}
\end{cases}
$$

A pass/fail cliff-edge, not a smooth cost — the target tightens every year (89.34 gCO2e/MJ in
2026 → 85.69 in 2030), and the penalty rate (€2,400 per tonne-VLSFO-equivalent) is fixed by
regulation. Not affected by the CO2e update — FuelEU is a fuel-intensity standard, not an
emissions charge, so it was never CO2-only in the first place.

Source: `fueleu_cost()`, `cbam_model/model/fueleu.py:24` · Regulation (EU) 2023/1805 Annex IV Part B

---

## Underneath both — how voyage fuel/CO2/CO2e are built

$$
\text{daily fuel (t)} = \frac{\text{engine power (kW)} \times \text{load fraction} \times \text{SFOC (g/kWh)} \times 24}{1{,}000{,}000}
$$

$$
\text{voyage days} = \frac{\text{distance (nm)}}{\text{speed (knots)} \times 24}, \qquad
\text{voyage fuel} = \text{voyage days} \times \text{daily fuel}
$$

$$
\text{voyage CO}_2 = \text{voyage fuel} \times \text{VLSFO carbon factor} \ (3.151\ \text{tCO}_2/\text{t fuel})
$$

$$
\text{port fuel} = \text{daily fuel} \times \text{aux share} \times \text{port days}, \qquad
\text{port CO}_2 = \text{port fuel} \times \text{VLSFO carbon factor}
$$

CO2e for both is then the CH4/N2O addition described above.

Note: `daily_fuel_tonnes()` does **not** take speed as an input — fuel burn per day is fixed
by engine power/load/SFOC alone, so a faster voyage only reduces total fuel by shortening
`voyage_days`. This is a stated modelling simplification, not a real-ship fuel curve (real
vessels burn more fuel per day at higher speed).

Source: `daily_fuel_tonnes()`, `voyage_days()`, `voyage_fuel_and_co2()`, `port_fuel_tonnes()` —
`cbam_model/config/vessel_logistics.py:143`

---

## Final join

$$
\text{cargo tonnes} = \text{fixed per-product figure from the maritime dataset}
$$

$$
\text{maritime cost per tonne} = \frac{\text{EU ETS} + \text{FuelEU} + \text{UK ETS}}{\text{cargo tonnes}}
$$

This division is the only point where the maritime (per-voyage) and CBAM (per-tonne) layers
touch. `cargo_tonnes` must be supplied explicitly — an unresolved or missing value raises
rather than silently defaulting.

Source: `compliance_cost_per_tonne()`, `cbam_model/model/total_cost.py:247`

---

## Layer 3 — Marginal abatement cost (pathway comparison, not a border charge)

Separate from CBAM and the maritime layer: the cost of avoiding one tonne of CO2 by
switching from the dirtiest literature pathway to a cleaner one, compared against that
corridor's own carbon price.

$$
\text{MAC} = \frac{\text{production cost}_{\text{alt}} - \text{production cost}_{\text{ref}}}{\text{embedded emissions}_{\text{ref}} - \text{embedded emissions}_{\text{alt}}}
$$

$$
\text{margin vs carbon price \%} = \frac{\text{carbon price} - \text{MAC}}{\text{carbon price}} \times 100
$$

Verdict: `justified` if MAC sits below the carbon price, `marginal` if the margin is
within 10% either way (too close to call), `not justified` if MAC exceeds the carbon
price. `reference_pathway` is always the highest-emitting literature
pathway for that corridor/product; `cbam_default` rows are excluded on both sides, since
they are a regulatory default figure, not a real production route.

Production cost and embedded emissions cancel their conversion/freight components in
this comparison (both pathways ship the same way), which is why this is the one
delivered-cost-style question the model can answer exactly despite conversion and
freight cost being unsourced.

**Robustness checks, not primary inputs.** Two of the four corridor-product cost gaps
are subtractions across separate studies (Canada hydrogen, China ammonia), so
`abatement_source_robustness()` reruns the same MAC formula on IEA production costs and
reports both side by side. Every verdict holds its sign under both sourcings, and under
both the IEA onshore wind and solar PV green routes. A test fails if that stops being
true.

The Canada-only cross-check (Ayub et al. 2024, `ayub_production_costs()`) was run through
on 9 August 2026 and every verdict holds under it too, so there are three independent
sourcings in agreement rather than two. Two limits on how it may be cited, both checked
against the paper: its **emissions** side is not physically valid (Table 2's fuel carbon
factors exceed what mass balance allows, giving 107.27 kg CO2/kg H2 for coal gasification
against the ~20 used here), so it is a **cost** cross-check only; and its green figure
prices grid electrolysis at retail household tariffs rather than the wind-driven route
Halifax-Hamburg represents, so the gap against the primary source is a definitional
difference, not evidence of cost uncertainty. Say that wherever the comparison is
reported. Its grey figure agrees with the primary almost exactly (USD 700/t against
700/t).

**Verdict band.** `marginal` is a 10% band either side of the carbon price, not a vague
"few percent". One row in the whole matrix trips it: green ammonia on the UK corridor at
2030 medium, MAC EUR 57.31 against a carbon price of EUR 57.90, a 1% margin. Report it as
marginal, never as justified.

Source: `marginal_abatement_cost()`, `abatement_source_robustness()`,
`cbam_model/analysis/outputs.py:208`
