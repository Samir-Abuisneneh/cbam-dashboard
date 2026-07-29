# CBAM Corridor Cost Model — Formula Reference

This is the complete cost model, one layer at a time, matching the implementation in
`cbam_model/model/` and `cbam_model/config/vessel_logistics.py` exactly. Each formula
links to the function it comes from.

## Top level

$$
\text{Total compliance cost per tonne} = \text{CBAM cost per tonne} + \frac{\text{EU ETS} + \text{FuelEU} + \text{UK ETS (per voyage)}}{\text{cargo tonnes}}
$$

Only one regime's maritime terms are ever non-zero for a given corridor — EU trips carry
EU ETS + FuelEU, UK trips carry UK ETS only. EUR and GBP are never converted or combined.

Source: `compliance_cost_per_tonne()`, `cbam_model/model/total_cost.py:183`

---

## Layer 1 — CBAM (border tax on the fuel's embedded emissions)

### EU

$$
\text{emissions}_{\text{used}} =
\begin{cases}
\text{embedded emissions} \times (1 + \text{markup}(year)) & \text{using the regulatory default} \\
\text{embedded emissions} & \text{using a literature pathway}
\end{cases}
$$

$$
\text{EU CBAM cost/t} = \max\Big(0,\ \text{emissions}_{\text{used}} \times \text{cbam\_factor}(year) \times \big(\text{cert price} - \text{origin carbon price}\big)\Big)
$$

| Term | Meaning |
|---|---|
| `cbam_factor(year)` | EU's certificate-surrender phase-in: 2.5% (2026) rising to 100% by 2034 |
| `markup(year)` | Penalty for using the default instead of verified data: 10% (2026) / 20% (2027) / 30% (2028+) |
| origin carbon price | Credited 1-for-1 against the liability, floored at zero |

Source: `eu_cbam_cost()`, `cbam_model/model/cbam.py:37` · Regulation (EU) 2023/956 Art. 9, IR 2025/2621

### UK

$$
\text{UK CBAM cost/t} = \text{embedded emissions} \times \text{UK carbon price} \times \text{phase-in factor}
$$

Zero if `year < 2027` (scheme doesn't exist yet). Phase-in factor is not yet set by UK
legislation — it is exposed in the dashboard as an explicit what-if slider, never assumed.

Source: `uk_cbam_cost()`, `cbam_model/model/cbam.py:80`

---

## Layer 2 — Maritime (the ship's own voyage emissions, per voyage)

### EU ETS

$$
\text{EU ETS cost} = \Big(\text{voyage CO}_2 \times 0.50 + \text{berth CO}_2 \times 1.00\Big) \times \text{phase-in}(year) \times \text{ETS price}
$$

0.50 because the corridor is an extra-EEA voyage (EU only taxes half of an international
leg's emissions); the berth term is 1.00 (intra-EEA rate) but disabled by default so results
reproduce the reference maritime dataset exactly.

Source: `eu_ets_maritime_cost()`, `cbam_model/model/ets_maritime.py:12`

### UK ETS

$$
\text{UK ETS cost} = \Big(\text{port CO}_2 \times 1.00 + \text{voyage CO}_2 \times c\Big) \times \text{UK carbon price}
$$

$$
c = \begin{cases} 0 & \text{current law} \\ 0.50 & \text{proposed international expansion (not law)} \end{cases}
$$

Source: `uk_ets_maritime_cost()`, `cbam_model/model/ets_maritime.py:37`

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
regulation.

Source: `fueleu_cost()`, `cbam_model/model/fueleu.py:23` · Regulation (EU) 2023/1805 Annex IV Part B

---

## Underneath both — how voyage fuel/CO₂ are built

$$
\text{daily fuel (t)} = \frac{\text{engine power (kW)} \times \text{load fraction} \times \text{SFOC (g/kWh)} \times 24}{1{,}000{,}000}
$$

$$
\text{voyage days} = \frac{\text{distance (nm)}}{\text{speed (knots)} \times 24}, \qquad
\text{voyage fuel} = \text{voyage days} \times \text{daily fuel}
$$

$$
\text{voyage CO}_2 = \text{voyage fuel} \times \text{VLSFO carbon factor}
$$

$$
\text{port CO}_2 = \text{daily fuel} \times \text{aux share} \times \text{port days} \times \text{VLSFO carbon factor}
$$

Note: `daily_fuel_tonnes()` does **not** take speed as an input — fuel burn per day is fixed
by engine power/load/SFOC alone, so a faster voyage only reduces total fuel by shortening
`voyage_days`. This is a stated modelling simplification, not a real-ship fuel curve (real
vessels burn more fuel per day at higher speed).

Source: `daily_fuel_tonnes()`, `voyage_days()`, `voyage_fuel_and_co2()`, `port_co2_tonnes()` —
`cbam_model/config/vessel_logistics.py:123`

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

Source: `compliance_cost_per_tonne()`, `cbam_model/model/total_cost.py:183`
