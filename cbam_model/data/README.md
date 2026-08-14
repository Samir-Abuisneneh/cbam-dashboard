# Data contracts

Three input tables. Two have owners. One does not, which is the main gap to
close.

Everything below is what the validation layer in `validation/unit_checks.py`
actually enforces. If a column is renamed or a unit changes, the model refuses
to run rather than producing a plausible wrong answer.

---

## 1. `emissions_table.csv` (owner: Riya, Student 1)

| column | type | unit | notes |
|---|---|---|---|
| `corridor` | str | | exactly `halifax_hamburg` or `ningbo_felixstowe` |
| `product` | str | | exactly `hydrogen` or `ammonia` |
| `pathway` | str | | e.g. `grey_smr`, `blue_smr_ccs`, `green_electrolysis`, `coal_gasification` |
| `embedded_emissions_tco2e_per_tonne` | float | tCO2e per tonne of product | **not kg** |
| `origin_carbon_price_eur_per_tco2e` | float | EUR/tCO2e | 0 where none is paid at origin |
| `source` | str | | `IR_2025_2621` or a literature citation |

Enforced: no value at or above 50 (that would indicate kg), no negatives, no
duplicate corridor/product/pathway rows, corridor and product labels exact.

Note on units: for both hydrogen and ammonia, kgCO2 per kg of product is
numerically identical to tCO2e per tonne, so the Part C literature figures
(9 to 12 for grey hydrogen, 5.2 to 9.0 for brown ammonia) transfer across
directly. That coincidence is also why a units error here is easy to miss.

---

## 2. `corridor_logistics.csv` (DELIVERED by Gayu, Student 2)

Generated from her notebooks by `config/vessel_logistics.py` rather than hand
transcribed, and checked against her published outputs by
`validation/gayu_reproduction.py`.

| column | type | unit | notes |
|---|---|---|---|
| `corridor` | str | | |
| `vessel_class` | str | | `VLGC/VLAC` for the primary gas carrier case |
| `distance_nm` | float | nautical miles | Eurostat SeaRoute |
| `service_speed_knots` | float | knots | |
| `voyage_days` | float | days | |
| `fuel_consumption_t_per_nm` | float | tonnes fuel per nm | derived |
| `voyage_fuel_total_t` | float | tonnes | |
| `voyage_co2_t` | float | tCO2 | before any coverage fraction |
| `voyage_co2e_t` | float | tCO2e | CO2 + CH4 + N2O on a GWP basis. **Required.** Added 5 Aug 2026 with Gayu's CO2e update; this, not `voyage_co2_t`, is what the EU and UK ETS costs are computed from, since both schemes cover all three gases from 2026 |
| `port_in_port_emissions_t` | float | tCO2 | auxiliary engines during the port call |
| `port_in_port_emissions_co2e_t` | float | tCO2e | the CO2e counterpart of the row above. **Required.** This is the only emissions figure UK ETS charges at all, since the ocean leg is out of scope |
| `voyage_energy_mj` | float | MJ | |
| `fueleu_actual_intensity_gco2e_mj` | float | gCO2e/MJ | 90.8, EC worked example for MDO |

Enforced: `distance_nm` between 1,000 and 20,000 (below suggests kilometres,
above exceeds even the Cape of Good Hope routing of 14,815 nm), the fuel total is
internally consistent with distance times rate to within 1%, berth emissions are
smaller than voyage emissions, and the FuelEU intensity sits between 0 and 150.

### Cargo capacity, DELIVERED 25 July 2026

Source: Gayu, `cargo_capacity_and_density_v2.ipynb`. This closed the gap between
her per-voyage unit and the per-tonne unit CBAM works in.

| input | value | source |
|---|---|---|
| Vessel cubic capacity | 84,000 m3 | Seo et al. (2024), *Sustainability* 16(2) 827 |
| Filling limit | 98% | IMO IGC Code, Ch. 15.1.1 |
| Ammonia density | 682 kg/m3 | PubChem (NIH), CID 222 |
| Hydrogen density | 70.8 kg/m3 | Seo and Han (2021), *Energies* 14(24) 8326 |

Giving 82,320 m3 usable, so **56,142 t of ammonia or 5,828 t of liquid
hydrogen**, a ratio of 9.6 to 1. Held in `config/vessel_logistics.py` and pinned
by `validation/gayu_reproduction.py`.

Capacity comes from the same peer-reviewed vessel study already used for service
speed and port time, so all three operational assumptions now trace to one
consistent source.

**Caveat for the write-up.** The 84,000 m3 figure is an ammonia carrier, running
at about -33 C, and cannot physically hold liquid hydrogen at -253 C. The largest
liquid hydrogen vessel built is 1,250 m3. Applying this geometry to hydrogen is a
deliberate counterfactual that isolates cargo density by holding the vessel
constant, and should be labelled as such rather than presented as a shipping
option available today.

## 3. `commercial_inputs.csv` (owner: UNASSIGNED, production cost partly filled 4 Aug 2026)

| column | type | unit |
|---|---|---|
| `corridor` | str | |
| `product` | str | |
| `pathway` | str | |
| `production_cost_eur_per_tonne` | float | EUR per tonne of product |
| `conversion_cost_eur_per_tonne` | float | EUR per tonne, liquefaction, cracking, storage |
| `shipping_cost_eur_per_tonne` | float | EUR per tonne, freight rate excluding carbon costs |
| `source` | str | |

**Still the gap, but smaller.** `total_delivered_cost` has six terms. Riya's
emissions table feeds the CBAM term, Gayu's feeds the ETS and FuelEU terms.
Nobody is formally contracted to supply the other three, but Riya's 4 August
2026 delivery included two production-cost sheets ("Production Costs -
Literature" and "Production Costs (IEA)") alongside her emissions update, so
`production_cost_eur_per_tonne` is now real, literature-sourced figures
(USD converted to EUR at the 23 July 2026 ECB rate) rather than invented
placeholders - see `data_io._placeholder_commercial()` for the per-pathway
sourcing. Production cost was the largest single component of delivered cost
by a wide margin, so this is real progress, but `run_delivered_cost()` stays
blocked: `conversion_cost_eur_per_tonne` and `shipping_cost_eur_per_tonne`
are still on invented placeholder numbers with no source at all.

Two open items:

1. Conversion cost (liquefaction, cracking, storage) and shipping cost
   (freight rate) still need an owner. Two options, and one of them needs
   picking soon: Samir sources both from the literature, or Gayu extends her
   scope to cover the freight rate specifically, since it sits closest to her
   corridor work, and Samir takes conversion cost alone.
2. The IEA sheet ("Production Costs (IEA)") is year- and method-specific
   (2025 vs 2030, several production methods per country) and is not yet
   used - the model only has one flat production-cost figure per pathway, not
   a year-varying one. Incorporating it means deciding whether production
   cost should move by scenario year the way carbon prices already do.

Worth noting that the shipping cost here must exclude carbon compliance costs,
otherwise the ETS and FuelEU terms double count.

---

## Placeholder data

`placeholder/` holds synthetic versions of all three tables so the model runs
end to end before the real ones land. Every row is marked `PLACEHOLDER` in its
`source` column, and `data_io.using_placeholder_data()` checks for that marker.
Real tables go in `data/` directly, where they take precedence automatically.
