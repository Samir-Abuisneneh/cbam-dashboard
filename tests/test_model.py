"""Tests for the corridor cost model.

Expected values are hand-calculated in the test body rather than copied from a
previous run, so a regression in the model cannot quietly update its own
expectations.
"""

import pytest

from cbam_model.config import regulatory_constants as rc
from cbam_model.config import scenarios
from cbam_model.config import vessel_logistics as vl
from cbam_model.config.unresolved import UnresolvedConstantError, is_unresolved
from cbam_model.model import cbam, ets_maritime, fueleu, total_cost
from cbam_model.validation import unit_checks, gayu_reproduction
from cbam_model.analysis import outputs
from cbam_model import data_io, runner

import pandas as pd


# ---------------------------------------------------------------------------
# Regulatory constants
# ---------------------------------------------------------------------------


def test_cbam_factor_and_free_allocation_sum_to_one():
    """The CBAM factor and the free allocation share are complements.

    This is the check that catches the single most repeated error in this
    project: using the free allocation share where the CBAM factor belongs.
    """
    free_allocation = {
        2026: 0.975, 2027: 0.95, 2028: 0.90, 2029: 0.775, 2030: 0.515,
        2031: 0.39, 2032: 0.265, 2033: 0.14, 2034: 0.0,
    }
    for year, factor in rc.CBAM_FACTOR.items():
        assert factor + free_allocation[year] == pytest.approx(1.0), (
            f"CBAM factor and free allocation do not sum to 1 in {year}"
        )


def test_cbam_factor_is_small_in_2026_not_large():
    """2026 charges 2.5%, not 97.5%. Directional guard against the inversion."""
    assert rc.cbam_factor(2026) == 0.025
    assert rc.cbam_factor(2026) < rc.cbam_factor(2030) < rc.cbam_factor(2034)


def test_cbam_cert_price_still_matches_ets_scenario_bounds():
    """The model substitutes the EU ETS price for the CBAM certificate price.

    That is only valid while the two stay close (Article 21 pegs them
    together by design). This fails loudly if the EU ETS scenario range is
    ever edited without checking it still brackets the real EEX print.
    """
    assert rc.cbam_cert_price_within_ets_scenario_bounds(2026)


def test_cbam_factor_saturates_at_one_after_2034():
    assert rc.cbam_factor(2035) == 1.00
    assert rc.cbam_factor(2050) == 1.00
    assert rc.cbam_factor(2025) == 0.0


def test_default_value_markup_holds_at_thirty_percent():
    assert rc.default_value_markup(2026) == 0.10
    assert rc.default_value_markup(2027) == 0.20
    assert rc.default_value_markup(2028) == 0.30
    assert rc.default_value_markup(2034) == 0.30


def test_fueleu_target_matches_published_2025_figure():
    """2% off the 91.16 baseline is the widely quoted 89.34."""
    assert rc.fueleu_target(2026) == pytest.approx(89.34, abs=0.01)


def test_fueleu_target_tightens_in_2030():
    """The spec only carried the 2025-2029 step. 2030 is a 6% reduction."""
    assert rc.fueleu_target(2030) == pytest.approx(91.16 * 0.94, abs=0.001)
    assert rc.fueleu_target(2030) < rc.fueleu_target(2029)


# ---------------------------------------------------------------------------
# EU CBAM
# ---------------------------------------------------------------------------


def test_eu_cbam_cost_hand_calculation():
    """10 tCO2e at 2.5% and EUR 80/t, no markup, no origin price."""
    cost = cbam.eu_cbam_cost(10.0, 2026, 80.0, using_default_values=False)
    assert cost == pytest.approx(10.0 * 0.025 * 80.0)  # 20.00
    assert cost == pytest.approx(20.0)


def test_eu_cbam_cost_with_default_value_markup():
    """The 2026 markup is 10%, so 10 tCO2e becomes 11 chargeable tonnes."""
    cost = cbam.eu_cbam_cost(10.0, 2026, 80.0, using_default_values=True)
    assert cost == pytest.approx(11.0 * 0.025 * 80.0)  # 22.00


def test_eu_cbam_is_zero_before_2026():
    assert cbam.eu_cbam_cost(10.0, 2025, 80.0) == 0.0


def test_origin_carbon_price_scales_with_emissions_not_flat_subtraction():
    """The origin price is EUR/tCO2e, so it must scale with the same emissions
    and the same CBAM factor as the liability it offsets.

    The build spec wrote this as a flat subtraction of the price from the total
    cost. With these inputs that would give 20.00 - 30.00 = -10.00, a negative
    cost from a positive liability, which is the tell that the units are wrong.
    """
    cost = cbam.eu_cbam_cost(
        10.0, 2026, 80.0, origin_carbon_price_eur_per_tco2e=30.0
    )
    assert cost == pytest.approx(10.0 * 0.025 * (80.0 - 30.0))  # 12.50
    assert cost > 0


def test_origin_carbon_price_above_ets_price_floors_at_zero():
    """A higher carbon price at origin cannot generate a negative CBAM cost."""
    cost = cbam.eu_cbam_cost(
        10.0, 2026, 80.0, origin_carbon_price_eur_per_tco2e=100.0
    )
    assert cost == 0.0


# ---------------------------------------------------------------------------
# UK CBAM
# ---------------------------------------------------------------------------


def test_uk_cbam_is_zero_in_2026():
    """The central asymmetry: Ningbo-Felixstowe has no CBAM liability in 2026."""
    assert cbam.uk_cbam_cost(10.0, 2026, 40.0) == 0.0


def test_uk_cbam_rate_fraction_matches_the_confirmed_baseline():
    """rate_fraction = 1 - (baseline_FA% x Article 16(14) factor).

    Baseline = (200228/221554 + 0.941176... + 0.75) / 3 ~= 0.8649 (2019 EU
    ETS + 2022/2023 UK ETS for Teesside Hydrogen Plant, installation 201961).
    """
    baseline = rc.UK_CBAM_BASELINE_FREE_ALLOCATION_PCT
    assert baseline == pytest.approx(0.8649, abs=0.0001)
    assert rc.uk_cbam_rate_fraction(2027) == pytest.approx(1 - baseline * 0.975)
    assert rc.uk_cbam_rate_fraction(2030) == pytest.approx(1 - baseline * 0.775)
    # Rising free-allocation squeeze (falling Article 16(14) factor) means a
    # rising CBAM rate, same directional logic as the EU's own CBAM factor.
    assert rc.uk_cbam_rate_fraction(2027) < rc.uk_cbam_rate_fraction(2030)


def test_uk_cbam_rate_fraction_undefined_year_raises():
    with pytest.raises(ValueError, match="Article 16"):
        rc.uk_cbam_rate_fraction(2031)


def test_uk_cbam_uses_the_real_rate_by_default():
    cost = cbam.uk_cbam_cost(10.0, 2027, 40.0)
    expected_fraction = 1 - rc.UK_CBAM_BASELINE_FREE_ALLOCATION_PCT * 0.975
    assert cost == pytest.approx(10.0 * expected_fraction * 40.0)


def test_uk_cbam_runs_with_explicit_override():
    cost = cbam.uk_cbam_cost(10.0, 2027, 40.0, rate_fraction=1.0)
    assert cost == pytest.approx(400.0)


# ---------------------------------------------------------------------------
# Maritime ETS
# ---------------------------------------------------------------------------


def test_eu_ets_charges_half_the_extra_eea_voyage():
    """1000 tCO2 voyage at 50% coverage, full phase-in, EUR 80/t."""
    cost = ets_maritime.eu_ets_maritime_cost(1000.0, 2026, 80.0, coverage_fraction=0.50)
    assert cost == pytest.approx(1000.0 * 0.50 * 1.0 * 80.0)  # 40,000


def test_eu_ets_charges_berth_emissions_at_full_coverage():
    """Berth emissions are intra-EEA, so 100% not 50%."""
    voyage_only = ets_maritime.eu_ets_maritime_cost(1000.0, 2026, 80.0, 0.50, 0.0)
    with_berth = ets_maritime.eu_ets_maritime_cost(1000.0, 2026, 80.0, 0.50, 100.0)
    assert with_berth - voyage_only == pytest.approx(100.0 * 1.00 * 80.0)  # 8,000


def test_eu_ets_phase_in_applies_before_2026():
    cost_2025 = ets_maritime.eu_ets_maritime_cost(1000.0, 2025, 80.0, 0.50)
    cost_2026 = ets_maritime.eu_ets_maritime_cost(1000.0, 2026, 80.0, 0.50)
    assert cost_2025 == pytest.approx(cost_2026 * 0.70)


def test_uk_ets_ignores_the_international_voyage():
    """The highest-error-risk fact in the project.

    A 10,000 tCO2 ocean voyage into Felixstowe contributes nothing. Only the
    50 tCO2 of berth emissions is chargeable.
    """
    cost = ets_maritime.uk_ets_maritime_cost(
        port_in_port_emissions_t=50.0,
        year=2030,
        uk_ets_price_gbp=40.0,
        voyage_co2_t=10_000.0,
    )
    assert cost == pytest.approx(50.0 * 1.00 * 40.0)  # 2,000, not 200,000


def test_uk_ets_voyage_emissions_do_not_change_the_answer():
    """Directly asserts zero sensitivity to voyage size under current scope."""
    small = ets_maritime.uk_ets_maritime_cost(50.0, 2030, 40.0, voyage_co2_t=1.0)
    huge = ets_maritime.uk_ets_maritime_cost(50.0, 2030, 40.0, voyage_co2_t=1_000_000.0)
    assert small == huge


def test_uk_ets_2026_is_not_prorated_on_a_per_voyage_basis():
    """A single voyage is either inside the first compliance period or outside it.

    Gayu's notebooks cost a single voyage and apply no proration, so the default
    matches. The half-year factor is available for annualised runs.
    """
    per_voyage_2026 = ets_maritime.uk_ets_maritime_cost(50.0, 2026, 40.0)
    per_voyage_2030 = ets_maritime.uk_ets_maritime_cost(50.0, 2030, 40.0)
    assert per_voyage_2026 == pytest.approx(per_voyage_2030)

    annualised = ets_maritime.uk_ets_maritime_cost(
        50.0, 2026, 40.0, first_period_fraction_2026=0.5
    )
    assert annualised == pytest.approx(per_voyage_2026 * 0.5)


def test_uk_ets_proposed_expansion_is_opt_in_only():
    baseline = ets_maritime.uk_ets_maritime_cost(50.0, 2030, 40.0, voyage_co2_t=10_000.0)
    expanded = ets_maritime.uk_ets_maritime_cost(
        50.0, 2030, 40.0, voyage_co2_t=10_000.0, include_intl_expansion=True
    )
    assert expanded == pytest.approx(baseline + 10_000.0 * 0.50 * 40.0)
    assert expanded > baseline


def test_uk_ets_expansion_cannot_apply_before_2028():
    with pytest.raises(ValueError, match="could not apply before"):
        ets_maritime.uk_ets_maritime_cost(
            50.0, 2026, 40.0, voyage_co2_t=1000.0, include_intl_expansion=True
        )


def test_uk_ets_price_anchors_are_resolved_and_below_eu():
    """Resolved from the UK ETS Authority 2026 determination, GBP 49.41/tCO2e.

    The build spec warned against reusing the EU figures because UK ETS trades
    below EU ETS. This asserts that relationship still holds after resolution.
    """
    assert rc.UK_ETS_PRICE_SCENARIOS["medium"] == 49.41
    assert not is_unresolved(rc.UK_ETS_PRICE_SCENARIOS["medium"])
    for scenario in rc.PRICE_SCENARIOS:
        assert rc.UK_ETS_PRICE_SCENARIOS[scenario] < rc.eu_ets_price(2026, scenario)


# ---------------------------------------------------------------------------
# FuelEU Maritime
# ---------------------------------------------------------------------------


def test_fueleu_is_zero_when_compliant():
    """Intensity below the target is a surplus, not a penalty."""
    assert fueleu.fueleu_cost(80.0, 1_000_000.0, 2026) == 0.0


def test_fueleu_penalty_hand_calculation():
    """Annex IV Part B, worked by hand.

    Actual 95 gCO2e/MJ against a 2026 target of 89.3368, over 10,000,000 MJ.
    Deficit = (95 - 89.3368) * 1e7 = 56,632,000 gCO2e.
    VLSFO equivalent = 56,632,000 / (95 * 41,000) = 14.5417 t.
    Penalty = 14.5417 * 2400 = EUR 34,900.
    """
    energy = 10_000_000.0
    actual = 95.0
    target = rc.fueleu_target(2026)
    deficit = (actual - target) * energy
    expected = (deficit / (actual * 41_000)) * 2400

    cost = fueleu.fueleu_cost(actual, energy, 2026)
    assert cost == pytest.approx(expected)
    assert cost == pytest.approx(34_900, rel=0.01)


def test_fueleu_divides_by_actual_intensity():
    """Guards the divisor the build spec omitted.

    Without dividing by GHGIE_actual the penalty would be roughly 95 times
    larger, so this test pins the order of magnitude.
    """
    energy = 10_000_000.0
    actual = 95.0
    cost = fueleu.fueleu_cost(actual, energy, 2026)
    spec_version = ((actual - rc.fueleu_target(2026)) * energy / 41_000) * 2400
    assert spec_version / cost == pytest.approx(actual, rel=0.01)


def test_fueleu_repeat_offender_multiplier():
    base = fueleu.fueleu_cost(95.0, 1e7, 2026, consecutive_deficit_periods=1)
    third = fueleu.fueleu_cost(95.0, 1e7, 2026, consecutive_deficit_periods=3)
    assert third == pytest.approx(base * 1.2)


def test_rfnbo_multiplier_lowers_effective_intensity():
    plain = fueleu.effective_intensity_with_rfnbo(90.0, 0.0, 2026)
    with_rfnbo = fueleu.effective_intensity_with_rfnbo(90.0, 0.5, 2026)
    assert plain == 90.0
    assert with_rfnbo < plain
    assert with_rfnbo == pytest.approx(90.0 / 1.5)


def test_rfnbo_multiplier_expires_after_2033():
    assert fueleu.effective_intensity_with_rfnbo(90.0, 0.5, 2034) == 90.0
    assert fueleu.effective_intensity_with_rfnbo(90.0, 0.5, 2033) < 90.0


def test_fueleu_does_not_apply_to_felixstowe():
    assert fueleu.fueleu_applies(rc.HALIFAX_HAMBURG)
    assert not fueleu.fueleu_applies(rc.NINGBO_FELIXSTOWE)


def test_green_bunker_fuel_zeroes_out_fueleu_penalty():
    """Green RFNBO bunker fuel reproduces Gayu's own worked example: already
    compliant, so FuelEU cost drops to zero versus the conventional case."""
    profile = vl.corridor_profile(rc.HALIFAX_HAMBURG, "gas_carrier", "base")
    conventional = total_cost.maritime_cost_per_voyage(
        profile, 2026, "medium", bunker_fuel="conventional"
    )
    green = total_cost.maritime_cost_per_voyage(
        profile, 2026, "medium", bunker_fuel="green_rfnbo"
    )
    assert conventional.fueleu_cost_eur == pytest.approx(13_229, rel=0.01)
    assert green.fueleu_cost_eur == 0.0
    # Bunker fuel choice only affects FuelEU in this model, not the voyage's
    # actual CO2 or the EU ETS cost charged on it.
    assert green.eu_ets_cost_eur == conventional.eu_ets_cost_eur
    assert green.voyage_co2_t == conventional.voyage_co2_t


def test_bunker_fuel_is_not_applicable_on_uk_corridor():
    profile = vl.corridor_profile(rc.NINGBO_FELIXSTOWE, "gas_carrier", "base")
    maritime = total_cost.maritime_cost_per_voyage(
        profile, 2026, "medium", bunker_fuel="green_rfnbo"
    )
    assert maritime.bunker_fuel == "n/a"
    assert maritime.fueleu_cost_eur == 0.0


# ---------------------------------------------------------------------------
# Validation layer
# ---------------------------------------------------------------------------


def _good_emissions():
    return pd.DataFrame({
        "corridor": [rc.HALIFAX_HAMBURG],
        "product": ["hydrogen"],
        "pathway": ["grey_smr"],
        "embedded_emissions_tco2e_per_tonne": [10.5],
        "origin_carbon_price_eur_per_tco2e": [0.0],
        "source": ["test"],
    })


def test_validation_catches_kg_instead_of_tonnes():
    df = _good_emissions()
    df["embedded_emissions_tco2e_per_tonne"] = [10_500.0]  # kg not tonnes
    with pytest.raises(unit_checks.ContractViolation, match="kgCO2e"):
        unit_checks.validate_emissions_table(df)


def test_validation_catches_corridor_label_typo():
    df = _good_emissions()
    df["corridor"] = ["halifax-hamburg"]  # hyphen not underscore
    with pytest.raises(unit_checks.ContractViolation, match="unexpected corridor"):
        unit_checks.validate_emissions_table(df)


def test_validation_catches_renamed_column():
    df = _good_emissions().rename(
        columns={"embedded_emissions_tco2e_per_tonne": "embedded_emissions"}
    )
    with pytest.raises(unit_checks.ContractViolation, match="missing required columns"):
        unit_checks.validate_emissions_table(df)


def test_validation_catches_km_instead_of_nm():
    _, logistics, _ = data_io.load_inputs(validate=False)
    logistics["distance_nm"] = logistics["distance_nm"] / 10.0
    logistics["voyage_fuel_total_t"] = (
        logistics["distance_nm"] * logistics["fuel_consumption_t_per_nm"]
    )
    with pytest.raises(unit_checks.ContractViolation, match="kilometres"):
        unit_checks.validate_logistics_table(logistics)


def test_placeholder_logistics_matches_gayu_distances():
    _, logistics, _ = data_io.load_inputs(validate=False)
    by_corridor = logistics.groupby("corridor")["distance_nm"].first()
    assert by_corridor[rc.HALIFAX_HAMBURG] == 2962
    assert by_corridor[rc.NINGBO_FELIXSTOWE] == 10403


def test_validation_catches_internally_inconsistent_fuel_total():
    _, logistics, _ = data_io.load_inputs(validate=False)
    logistics.loc[0, "voyage_fuel_total_t"] *= 2
    with pytest.raises(unit_checks.ContractViolation, match="does not match"):
        unit_checks.validate_logistics_table(logistics)


def test_input_tables_pass_their_own_validation():
    emissions, logistics, commercial = data_io.load_inputs(validate=True)
    # Logistics is per corridor per route: HH suez, NF suez, NF cape.
    assert len(emissions) > 0 and len(logistics) == 3 and len(commercial) > 0


# ---------------------------------------------------------------------------
# End to end, two layers
# ---------------------------------------------------------------------------


def test_maritime_matrix_is_free_of_unresolved_inputs():
    """The maritime layer is entirely Gayu's data and must run with no warnings."""
    maritime = runner.run_maritime_matrix()
    assert len(maritime) > 0
    assert set(maritime["corridor"].unique()) == set(rc.CORRIDORS)


def test_maritime_matrix_spans_gayu_scenario_dimensions():
    maritime = runner.run_maritime_matrix()
    assert set(maritime["speed_scenario"].unique()) >= {"lower", "base", "upper"}
    assert set(maritime["route_scenario"].unique()) == {"suez", "cape"}
    assert "VLGC/VLAC" in set(maritime["vessel_set"].unique())


def test_cape_routing_only_applies_to_the_uk_corridor():
    maritime = runner.run_maritime_matrix()
    cape = maritime[maritime["route_scenario"] == "cape"]
    assert set(cape["corridor"].unique()) == {rc.NINGBO_FELIXSTOWE}


def test_currencies_are_never_mixed():
    """EU costs are EUR, UK costs are GBP, and no row carries both."""
    maritime = runner.run_maritime_matrix()
    eu = maritime[maritime["corridor"] == rc.HALIFAX_HAMBURG]
    uk = maritime[maritime["corridor"] == rc.NINGBO_FELIXSTOWE]
    assert (eu["total_gbp"] == 0).all()
    assert (uk["total_eur"] == 0).all()
    assert (uk["eu_ets_cost_eur"] == 0).all()
    assert (uk["fueleu_cost_eur"] == 0).all()


def test_uk_corridor_maritime_cost_ignores_the_ocean_voyage():
    """Suez and Cape routings cost the same under current UK ETS scope."""
    maritime = runner.run_maritime_matrix()
    uk = maritime[
        (maritime["corridor"] == rc.NINGBO_FELIXSTOWE)
        & (maritime["year"] == 2026)
        & (maritime["price_scenario"] == "medium")
        & (maritime["speed_scenario"] == "base")
        & (maritime["vessel_set"] == "VLGC/VLAC")
    ]
    suez = uk[uk["route_scenario"] == "suez"]["total_gbp"].iloc[0]
    cape = uk[uk["route_scenario"] == "cape"]["total_gbp"].iloc[0]
    assert suez == pytest.approx(cape)


def test_cbam_matrix_runs_all_years_with_no_skips():
    """UK CBAM's rate mechanism is fully resolved, so nothing is skipped and
    Ningbo-Felixstowe carries a real, nonzero CBAM cost from 2027 onward."""
    cbam_results = runner.run_cbam_matrix()
    uk = cbam_results[cbam_results["corridor"] == rc.NINGBO_FELIXSTOWE]
    assert set(uk["year"].unique()) == set(scenarios.YEARS)
    assert (uk[uk["year"] == 2026]["uk_cbam_cost_gbp_per_tonne"] == 0.0).all()
    assert (uk[uk["year"] >= 2027]["uk_cbam_cost_gbp_per_tonne"] > 0.0).all()


def test_cbam_matrix_runs_fully_with_override():
    cbam_results = runner.run_cbam_matrix(
        uk_cbam_rate_override=1.0, skip_unresolved=False
    )
    emissions, _, _ = data_io.load_inputs()
    # len(scenarios.YEARS) years x 3 price scenarios per emissions-table row
    assert len(cbam_results) == len(emissions) * len(scenarios.YEARS) * 3


def test_cargo_tonnage_is_resolved_from_gayu():
    """Resolved 25 July 2026 from her cargo_capacity_and_density_v2 notebook."""
    assert not is_unresolved(vl.CARGO_TONNES)
    assert vl.CARGO_TONNES["ammonia"] == 56_142
    assert vl.CARGO_TONNES["hydrogen"] == 5_828
    # 98% IGC Code filling limit, not a full tank.
    assert vl.USABLE_VOLUME_M3 == pytest.approx(84_000 * 0.98)


def test_delivered_cost_is_now_blocked_on_commercial_costs_not_cargo():
    """The blocker moved. Cargo tonnage landed; production cost still has no owner."""
    with pytest.raises(UnresolvedConstantError, match="production, conversion and freight"):
        runner.run_delivered_cost()


def test_compliance_matrix_joins_both_layers():
    """UK CBAM is fully resolved, so this runs clean with no skips/warnings."""
    compliance = runner.run_compliance_matrix()
    assert len(compliance) > 0
    assert set(compliance["corridor"].unique()) == set(rc.CORRIDORS)
    # Every row carries both a CBAM term and a maritime term on one basis.
    for _, r in compliance.iterrows():
        assert r["total_compliance_cost_per_tonne"] == pytest.approx(
            r["cbam_cost_per_tonne"] + r["maritime_cost_per_tonne"]
        )


def test_hydrogen_absorbs_more_maritime_cost_per_tonne_than_ammonia():
    """Cargo density, not distance, drives the per-tonne maritime gap.

    The same voyage carries 9.6x more ammonia by mass, so each tonne of hydrogen
    absorbs 9.6x more of the voyage's carbon cost.
    """
    compliance = runner.run_compliance_matrix()
    subset = compliance[
        (compliance["corridor"] == rc.HALIFAX_HAMBURG)
        & (compliance["year"] == 2026)
        & (compliance["price_scenario"] == "medium")
    ]
    h2 = subset[subset["product"] == "hydrogen"]["maritime_cost_per_tonne"].iloc[0]
    nh3 = subset[subset["product"] == "ammonia"]["maritime_cost_per_tonne"].iloc[0]
    expected = vl.CARGO_TONNES["ammonia"] / vl.CARGO_TONNES["hydrogen"]
    assert h2 / nh3 == pytest.approx(expected, rel=0.01)


def test_uk_corridor_has_zero_compliance_cost_beyond_berth_in_2026():
    compliance = runner.run_compliance_matrix()
    uk_2026 = compliance[
        (compliance["corridor"] == rc.NINGBO_FELIXSTOWE) & (compliance["year"] == 2026)
    ]
    assert (uk_2026["cbam_cost_per_tonne"] == 0.0).all()
    assert (uk_2026["fueleu_cost_per_tonne"] == 0.0).all()
    assert (uk_2026["eu_ets_cost_per_tonne"] == 0.0).all()
    assert (uk_2026["uk_ets_cost_per_tonne"] > 0.0).all()


def test_fx_rate_is_resolved():
    assert not is_unresolved(rc.FX_EUR_PER_GBP)
    assert rc.FX_EUR_PER_GBP == pytest.approx(1.17209)
    assert 1000 * rc.FX_EUR_PER_GBP == pytest.approx(1172.09)


# ---------------------------------------------------------------------------
# Reproduction of Gayu's notebooks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,got,want",
    [(n, g, w) for n, g, w, _ in gayu_reproduction.check_gas_carrier()],
)
def test_reproduces_gayu_gas_carrier(name, got, want):
    assert got == pytest.approx(want, abs=0.51), (
        f"{name} diverges from Gayu's published figure"
    )


@pytest.mark.parametrize(
    "name,got,want",
    [(n, g, w) for n, g, w, _ in gayu_reproduction.check_container_ship()],
)
def test_reproduces_gayu_container_ship(name, got, want):
    assert got == pytest.approx(want, abs=0.51), (
        f"{name} diverges from Gayu's published figure"
    )


@pytest.mark.parametrize(
    "name,got,want",
    [(n, g, w) for n, g, w, _ in gayu_reproduction.check_cargo_capacity()],
)
def test_reproduces_gayu_cargo_capacity(name, got, want):
    assert got == pytest.approx(want, abs=0.06), (
        f"{name} diverges from Gayu's published figure"
    )


# ---------------------------------------------------------------------------
# Riya's delivered figures, pinned
# ---------------------------------------------------------------------------
# Added 4 August 2026. Nothing previously pinned the emissions or production
# cost values to what Riya actually sent, so an accidental edit to the table in
# data_io.py would have propagated into every result without failing anything.
# One of her figures had in fact been wrong for a week before the 4 August
# delivery exposed it (China coal ammonia carried the same paper's natural-gas
# row, 4.6, instead of its coal gasification row, 6.15).

RIYA_EMISSIONS_TCO2E_PER_TONNE = {
    (rc.HALIFAX_HAMBURG, "hydrogen", "green_electrolysis"): 1.23,
    (rc.HALIFAX_HAMBURG, "hydrogen", "grey_smr"): 10.07,
    (rc.HALIFAX_HAMBURG, "hydrogen", "blue_smr_ccs"): 2.02,
    (rc.HALIFAX_HAMBURG, "hydrogen", "cbam_default"): 10.82,
    (rc.NINGBO_FELIXSTOWE, "hydrogen", "green_electrolysis"): 2.34,
    # Grey and blue moved onto S0360319925010602 on 4 Aug 2026 (agreed with
    # Riya) so all three China hydrogen pathways share one study. Previously
    # 29.02 from S0360319921042737 and 7.91 from S0959652622021151.
    (rc.NINGBO_FELIXSTOWE, "hydrogen", "coal_gasification"): 20.09,
    (rc.NINGBO_FELIXSTOWE, "hydrogen", "blue_ccs"): 6.28,
    (rc.NINGBO_FELIXSTOWE, "hydrogen", "cbam_default"): 26.64,
    (rc.HALIFAX_HAMBURG, "ammonia", "grey_smr"): 2.18,
    (rc.HALIFAX_HAMBURG, "ammonia", "green_electrolysis"): 0.62,
    (rc.HALIFAX_HAMBURG, "ammonia", "cbam_default"): 1.98,
    (rc.NINGBO_FELIXSTOWE, "ammonia", "coal_gasification"): 6.15,
    (rc.NINGBO_FELIXSTOWE, "ammonia", "green_electrolysis"): 0.818,
    (rc.NINGBO_FELIXSTOWE, "ammonia", "cbam_default"): 4.36,
}

# From her "Production Costs - Literature" sheet, USD/t converted at the
# 23 July 2026 ECB reference rate, EXCEPT the three China hydrogen rows, which
# come from the emissions sheet's own cost column (S0360319925010602) so that
# China hydrogen cost and emissions share one study. Previously 1390.0 /
# 1590.0 / 4630.0 from S097308262400214X.
RIYA_PRODUCTION_COST_USD_PER_TONNE = {
    (rc.HALIFAX_HAMBURG, "hydrogen", "grey_smr"): 700.0,
    (rc.HALIFAX_HAMBURG, "hydrogen", "blue_smr_ccs"): 1200.0,
    (rc.HALIFAX_HAMBURG, "hydrogen", "green_electrolysis"): 4110.0,
    (rc.NINGBO_FELIXSTOWE, "hydrogen", "coal_gasification"): 1345.0,
    (rc.NINGBO_FELIXSTOWE, "hydrogen", "blue_ccs"): 1975.0,
    (rc.NINGBO_FELIXSTOWE, "hydrogen", "green_electrolysis"): 6170.0,
    (rc.HALIFAX_HAMBURG, "ammonia", "grey_smr"): 509.0,
    (rc.HALIFAX_HAMBURG, "ammonia", "green_electrolysis"): 1057.0,
    (rc.NINGBO_FELIXSTOWE, "ammonia", "coal_gasification"): 474.5,
    (rc.NINGBO_FELIXSTOWE, "ammonia", "green_electrolysis"): 822.6,
}


@pytest.mark.parametrize("key,expected", sorted(RIYA_EMISSIONS_TCO2E_PER_TONNE.items()))
def test_emissions_match_riyas_delivered_figures(key, expected):
    corridor, product, pathway = key
    emissions, _, _ = data_io.load_inputs()
    row = emissions[
        (emissions["corridor"] == corridor)
        & (emissions["product"] == product)
        & (emissions["pathway"] == pathway)
    ]
    assert len(row) == 1, f"expected exactly one row for {key}, got {len(row)}"
    assert row["embedded_emissions_tco2e_per_tonne"].iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize("key,usd", sorted(RIYA_PRODUCTION_COST_USD_PER_TONNE.items()))
def test_production_cost_matches_riyas_literature_sheet(key, usd):
    corridor, product, pathway = key
    _, _, commercial = data_io.load_inputs()
    row = commercial[
        (commercial["corridor"] == corridor)
        & (commercial["product"] == product)
        & (commercial["pathway"] == pathway)
    ]
    assert len(row) == 1
    assert row["production_cost_eur_per_tonne"].iloc[0] == pytest.approx(
        rc.usd_to_eur(usd), abs=0.05
    )


def test_china_coal_ammonia_is_not_the_natural_gas_figure():
    """Regression guard on the 4 August 2026 correction.

    4.6 (and its 4.4-4.8 range) is the Methane/Natural gas row of
    Sci. Total Environ. S0301479723016365, not its coal gasification row. The
    two were transposed for a week. Coal gasification is 6.14-6.16.
    """
    emissions, _, _ = data_io.load_inputs()
    value = emissions[
        (emissions["corridor"] == rc.NINGBO_FELIXSTOWE)
        & (emissions["product"] == "ammonia")
        & (emissions["pathway"] == "coal_gasification")
    ]["embedded_emissions_tco2e_per_tonne"].iloc[0]
    assert value == pytest.approx(6.15)
    assert value != pytest.approx(4.6), "the natural-gas figure has crept back in"


def test_usd_and_gbp_conversions_share_one_reference_date():
    """Every cross-currency rate in the model must be same-day, or the
    conversions are not mutually consistent."""
    assert rc.FX_EUR_PER_GBP == pytest.approx(1.17209)
    assert rc.FX_USD_PER_EUR_2026_07_23 == pytest.approx(1.1392)
    assert rc.usd_to_eur(1.1392) == pytest.approx(1.0, abs=1e-4)


def test_bunker_sweep_does_not_duplicate_the_uk_corridor():
    """FuelEU is EU-only, so sweeping bunker fuel must not double UK rows."""
    maritime = runner.run_maritime_matrix()
    uk = maritime[maritime["corridor"] == rc.NINGBO_FELIXSTOWE]
    assert set(uk["bunker_fuel"].unique()) == {"n/a"}
    eu = maritime[maritime["corridor"] == rc.HALIFAX_HAMBURG]
    assert set(eu["bunker_fuel"].unique()) == {"conventional", "green_rfnbo"}


def test_base_case_summaries_exclude_green_bunker_rows():
    """Guards the silent-averaging bug: the headline chart and summary must
    hold conventional bunkers, not average the two fuels together."""
    maritime = runner.run_maritime_matrix()
    summary = outputs.maritime_summary(maritime)
    eu = summary[summary["corridor"] == rc.HALIFAX_HAMBURG]
    # One row per vessel/year, not two.
    assert not eu.duplicated(subset=["corridor", "vessel_set", "year"]).any()


def test_green_bunker_removes_the_fueleu_penalty():
    profile = vl.corridor_profile(rc.HALIFAX_HAMBURG, "gas_carrier", "base")
    conventional = total_cost.maritime_cost_per_voyage(profile, 2030, "medium")
    green = total_cost.maritime_cost_per_voyage(
        profile, 2030, "medium", bunker_fuel="green_rfnbo"
    )
    assert conventional.fueleu_cost_eur > 0
    assert green.fueleu_cost_eur == 0.0
    # EU ETS is unchanged: the model holds actual voyage CO2 constant.
    assert green.eu_ets_cost_eur == pytest.approx(conventional.eu_ets_cost_eur)


def test_marginal_abatement_cost_excludes_regulatory_defaults():
    """cbam_default is an emissions figure, not a production route, and its
    production cost is only borrowed from the grey route, so it must never
    appear as a pathway or a reference in the abatement table."""
    emissions, _, commercial = data_io.load_inputs()
    mac = outputs.marginal_abatement_cost(emissions, commercial)
    assert len(mac) > 0
    assert "cbam_default" not in set(mac["pathway"])
    assert "cbam_default" not in set(mac["reference_pathway"])
    assert (mac["emissions_avoided_tco2e_per_tonne"] > 0).all()


# ---------------------------------------------------------------------------
# Reference case and the benchmark-mechanism gap
# ---------------------------------------------------------------------------


def test_reference_case_is_calibrated_against_the_paper():
    from cbam_model.validation import reference_case

    assert reference_case.CALIBRATED
    result = reference_case.run_reference_check()
    assert result["assumptions"]["all_inputs_sourced_from_paper"]


def test_benchmark_mechanism_reproduces_the_paper_and_our_formula_does_not():
    """The calibrated reference case's central finding.

    Ramsook et al. report a 22% burden. The benchmark-based free allocation
    adjustment lands within tolerance; this model's `embedded x CBAM_factor`
    does not, understating it by roughly 40%. If this test ever starts passing
    for `this_model_agrees`, the CBAM formula has been changed and the results
    chapter needs rewriting.
    """
    from cbam_model.validation import reference_case

    r = reference_case.run_reference_check()
    assert r["benchmark_model_agrees"], "benchmark mechanism no longer matches the paper"
    assert not r["this_model_agrees"], (
        "this model now agrees with the paper, which means the CBAM formula changed"
    )
    assert r["understatement_ratio"] > 1.3


def test_benchmark_mechanism_zeroes_cbam_for_below_benchmark_production():
    """The consequence that matters for this study's conclusions: under a
    benchmark mechanism, production cleaner than the benchmark owes nothing,
    where this model still charges a scaled amount."""
    from cbam_model.validation import reference_case

    rows = reference_case.benchmark_mechanism_gap(
        embedded_tco2e=1.23, benchmark=2.5, carbon_price=100.0, years=(2026, 2030)
    )
    assert all(r["benchmark_mechanism"] == 0.0 for r in rows)
    assert all(r["this_model"] > 0.0 for r in rows)


# ---------------------------------------------------------------------------
# Compliance-layer sensitivity
# ---------------------------------------------------------------------------


def test_compliance_sweep_ranks_cbam_inputs_above_voyage_inputs():
    """The reason the maritime-only sweep was replaced. By 2030 the emissions
    and carbon price inputs must outrank engine parameters, or the sweep is
    measuring the wrong layer."""
    from cbam_model.analysis import sensitivity

    sweep = sensitivity.sweep_compliance(
        rc.HALIFAX_HAMBURG, "hydrogen", "grey_smr", year=2030
    )
    ranked = sensitivity.rank_compliance_drivers(sweep)
    order = list(ranked.sort_values("rank")["parameter"])
    assert order.index("embedded_emissions_tco2e_per_tonne") < order.index(
        "main_engine_power_kw"
    )
    assert order.index("carbon_price") < order.index("service_speed_knots")


def test_compliance_sweep_price_effect_is_not_a_naive_output_scaling():
    """Canada's origin carbon price makes EU CBAM non-linear in the carbon
    price, so a +20% price move must not produce exactly +20% cost."""
    from cbam_model.analysis import sensitivity

    sweep = sensitivity.sweep_compliance(
        rc.HALIFAX_HAMBURG, "hydrogen", "grey_smr", year=2030
    )
    price_up = sweep[
        (sweep["parameter"] == "carbon_price") & (sweep["direction"] == "up")
    ]["pct_change"].iloc[0]
    assert price_up != pytest.approx(20.0, abs=0.5), (
        "carbon price effect looks like flat output scaling, which would be "
        "wrong once the origin carbon price is nonzero"
    )


def test_origin_carbon_price_has_no_leverage_on_the_china_corridor():
    """China prices neither product, so the parameter must register as zero
    leverage rather than being silently skipped."""
    from cbam_model.analysis import sensitivity

    sweep = sensitivity.sweep_compliance(
        rc.NINGBO_FELIXSTOWE, "hydrogen", "coal_gasification", year=2030
    )
    rows = sweep[sweep["parameter"] == "origin_carbon_price_eur_per_tco2e"]
    assert len(rows) == 2
    assert (rows["pct_change"] == 0.0).all()


# ---------------------------------------------------------------------------
# EU-UK ETS linkage scenario
# ---------------------------------------------------------------------------


def test_linkage_is_flagged_as_not_law():
    """Same treatment as the proposed UK ETS international extension. If this
    ever flips to True someone must have checked the legislation, not the
    market commentary."""
    assert rc.UK_ETS_LINKAGE_IS_LAW is False


def test_frozen_is_the_default_everywhere():
    """The linkage scenario must never leak into a baseline result."""
    assert rc.uk_ets_price(2030, "medium") == rc.UK_ETS_PRICE_SCENARIOS["medium"]
    maritime = runner.run_maritime_matrix()
    uk = maritime[maritime["corridor"] == rc.NINGBO_FELIXSTOWE]
    assert set(uk["uk_price_variant"].unique()) == {"frozen"}
    eu = maritime[maritime["corridor"] == rc.HALIFAX_HAMBURG]
    assert set(eu["uk_price_variant"].unique()) == {"n/a"}


def test_frozen_price_is_flat_across_every_year():
    prices = {rc.uk_ets_price(y, "medium", "frozen") for y in scenarios.YEARS}
    assert prices == {49.41}


def test_linked_price_converges_to_the_eu_price_by_alignment_year():
    """Full alignment from 2029 means the UK price equals the EU price once
    converted at the same reference rate."""
    for year in (2029, 2030):
        expected = rc.eu_ets_price(year, "medium") / rc.FX_EUR_PER_GBP
        assert rc.uk_ets_price(year, "medium", "linked") == pytest.approx(expected)


def test_linked_price_is_monotonic_and_starts_at_the_official_figure():
    """2026 stays on the sourced official determination; the discount then
    narrows rather than jumping."""
    path = [rc.uk_ets_price(y, "medium", "linked") for y in scenarios.YEARS]
    assert path[0] == pytest.approx(rc.UK_ETS_PRICE_2026_OFFICIAL)
    assert path == sorted(path), "convergence path must not go backwards"
    assert path[-1] > path[0] * 2, "2030 should more than double under linkage"


def test_linked_price_never_below_frozen_in_this_horizon():
    for year in scenarios.YEARS:
        for scenario in rc.PRICE_SCENARIOS:
            assert rc.uk_ets_price(year, scenario, "linked") >= rc.uk_ets_price(
                year, scenario, "frozen"
            ) - 1e-9


def test_unknown_uk_price_variant_raises():
    with pytest.raises(ValueError, match="variant"):
        rc.uk_ets_price(2030, "medium", "converged")


def test_linkage_roughly_doubles_uk_cbam_by_2030():
    """The headline consequence. Guards against the scenario silently
    becoming a no-op if the convergence path is ever edited."""
    frozen = runner.run_cbam_matrix(uk_price_variant="frozen")
    linked = runner.run_cbam_matrix(uk_price_variant="linked")

    def pick(df):
        m = (
            (df["corridor"] == rc.NINGBO_FELIXSTOWE)
            & (df["product"] == "ammonia")
            & (df["pathway"] == "cbam_default")
            & (df["year"] == 2030)
            & (df["price_scenario"] == "medium")
        )
        return df.loc[m, "uk_cbam_cost_gbp_per_tonne"].iloc[0]

    ratio = pick(linked) / pick(frozen)
    assert 2.0 < ratio < 2.4, f"expected roughly 2.2x, got {ratio:.2f}x"


def test_linkage_does_not_touch_the_eu_corridor():
    """Neither Canada nor China is party to the linkage, and the EU corridor's
    price series is unaffected regardless."""
    frozen = runner.run_cbam_matrix(uk_price_variant="frozen")
    linked = runner.run_cbam_matrix(uk_price_variant="linked")
    eu_f = frozen[frozen["corridor"] == rc.HALIFAX_HAMBURG][
        "eu_cbam_cost_eur_per_tonne"
    ].reset_index(drop=True)
    eu_l = linked[linked["corridor"] == rc.HALIFAX_HAMBURG][
        "eu_cbam_cost_eur_per_tonne"
    ].reset_index(drop=True)
    pd.testing.assert_series_equal(eu_f, eu_l)


def test_scenario_labels_travel_with_every_output_row():
    """A saved table must always say which scenario produced it. Dropping the
    label is how a policy-uncertain what-if gets quoted as a baseline."""
    compliance = runner.run_compliance_matrix(uk_price_variant="linked")
    assert "uk_price_variant" in compliance.columns
    assert "bunker_fuel" in compliance.columns
    uk = compliance[compliance["corridor"] == rc.NINGBO_FELIXSTOWE]
    assert set(uk["uk_price_variant"].unique()) == {"linked"}

    maritime = runner.run_maritime_matrix()
    effective = outputs.carbon_cost_per_tonne_co2(maritime)
    assert "uk_price_variant" in effective.columns


# ---------------------------------------------------------------------------
# UK CBAM carbon price relief
# ---------------------------------------------------------------------------


def test_uk_cbam_relief_is_a_no_op_for_every_current_case():
    """Added 4 Aug 2026. China prices neither product, so wiring the relief in
    must not move a single existing number."""
    emissions, _, _ = data_io.load_inputs()
    uk = emissions[emissions["corridor"] == rc.NINGBO_FELIXSTOWE]
    assert (uk["origin_carbon_price_eur_per_tco2e"] == 0.0).all()
    for year in (2027, 2030):
        with_relief = cbam.uk_cbam_cost(10.0, year, 50.0, None, 0.0)
        without = cbam.uk_cbam_cost(10.0, year, 50.0, None)
        assert with_relief == pytest.approx(without)


def test_uk_cbam_relief_scales_with_emissions_and_rate_not_flat():
    """Same unit trap as the EU side: the origin price is GBP/tCO2e, so it must
    enter on the same basis as the liability, not be subtracted from a total."""
    fraction = rc.uk_cbam_rate_fraction(2027)
    cost = cbam.uk_cbam_cost(10.0, 2027, 50.0, None, 20.0)
    assert cost == pytest.approx(10.0 * fraction * (50.0 - 20.0))
    assert cost > 0


def test_uk_cbam_relief_floors_at_zero():
    assert cbam.uk_cbam_cost(10.0, 2027, 50.0, None, 90.0) == 0.0


def test_uk_cbam_relief_converts_eur_to_gbp():
    """The emissions table holds EUR; the UK regime is GBP. Passing EUR
    straight through would overstate the relief by about 17%."""
    eur = 60.0
    via_dispatch = cbam.cbam_cost_for_corridor(
        rc.NINGBO_FELIXSTOWE, 10.0, 2027, 0.0,
        uk_carbon_price_gbp=80.0, origin_carbon_price_eur_per_tco2e=eur,
    )
    expected = cbam.uk_cbam_cost(10.0, 2027, 80.0, None, rc.eur_to_gbp(eur))
    assert via_dispatch == pytest.approx(expected)
    # And it must differ from the naive EUR-as-GBP version.
    naive = cbam.uk_cbam_cost(10.0, 2027, 80.0, None, eur)
    assert via_dispatch != pytest.approx(naive)


# ---------------------------------------------------------------------------
# EU ETS product benchmarks
# ---------------------------------------------------------------------------


def test_product_benchmarks_match_the_regulation():
    """IR (EU) 2021/447 Annex. The ammonia figure is independently corroborated
    by Ramsook et al. (2025), who quote it as 1.57."""
    b = rc.EU_ETS_PRODUCT_BENCHMARK_TCO2E_PER_TONNE
    assert b["ammonia"] == pytest.approx(1.570)
    assert b["hydrogen"] == pytest.approx(6.84)
    assert set(b) == set(rc.PRODUCTS)


def test_benchmarks_are_not_the_cbam_default_values():
    """Different regulations, different meanings. Conflating them would be a
    material error, so this pins that they are distinct numbers."""
    emissions, _, _ = data_io.load_inputs()
    defaults = emissions[emissions["pathway"] == "cbam_default"]
    for _, row in defaults.iterrows():
        bench = rc.EU_ETS_PRODUCT_BENCHMARK_TCO2E_PER_TONNE[row["product"]]
        assert row["embedded_emissions_tco2e_per_tonne"] != pytest.approx(bench)


def test_every_green_pathway_sits_below_its_benchmark():
    """Why the benchmark mechanism matters less than first feared: green is
    already far below benchmark, so it owes near-zero under either formula."""
    emissions, _, _ = data_io.load_inputs()
    green = emissions[emissions["pathway"] == "green_electrolysis"]
    assert len(green) == 2 * len(rc.CORRIDORS) / 2 * 2 or len(green) > 0
    for _, row in green.iterrows():
        bench = rc.EU_ETS_PRODUCT_BENCHMARK_TCO2E_PER_TONNE[row["product"]]
        assert row["embedded_emissions_tco2e_per_tonne"] < bench


# ---------------------------------------------------------------------------
# Source-consistency robustness. Added 4 August 2026.
#
# Two of the four corridor-product production-cost gaps are still subtractions
# across separate studies (Canada hydrogen spans three papers, China ammonia
# two). Riya confirmed no single Canadian study exists, so the mixed sourcing
# is permanent. These tests pin the thing that makes it reportable anyway:
# that the abatement verdicts do not depend on which sourcing is used.
# ---------------------------------------------------------------------------


def test_abatement_sign_is_stable_across_sourcings():
    """The headline claim of the robustness check.

    If a pathway is below the carbon price on literature costs and above it on
    IEA costs, the finding is an artefact of source selection and cannot be
    reported. This fails loudly if that ever becomes true.
    """
    emissions, _, commercial = data_io.load_inputs()
    for green_route in ("wind", "solar"):
        r = outputs.abatement_source_robustness(
            emissions, commercial, green_route=green_route
        )
        assert len(r), f"robustness check produced no rows for {green_route}"
        unstable = r[~r["sign_stable"]]
        assert unstable.empty, (
            f"abatement verdict flips sign under IEA {green_route} costs for:\n"
            f"{unstable[['corridor', 'product', 'pathway']].to_string(index=False)}"
        )


def test_china_ammonia_green_is_reported_as_marginal_not_justified():
    """A 1% margin must not read as a clean pass.

    At 2030 medium prices China ammonia green electrolysis lands at about
    EUR 57.3/tCO2 against a carbon price of about EUR 57.9. The bare boolean
    says True. It is inside the marginal band and has to be reported that way,
    which was an explicit decision on 4 August 2026, not an accident of
    rounding.
    """
    emissions, _, commercial = data_io.load_inputs()
    mac = outputs.marginal_abatement_cost(emissions, commercial)
    row = mac[
        (mac["corridor"] == rc.NINGBO_FELIXSTOWE)
        & (mac["product"] == "ammonia")
        & (mac["pathway"] == "green_electrolysis")
    ]
    assert len(row) == 1
    row = row.iloc[0]
    assert row["verdict"] == "marginal"
    assert abs(row["margin_vs_carbon_price_pct"]) <= outputs.MARGINAL_VERDICT_BAND_PCT


@pytest.mark.parametrize("margin,expected", [
    (50.0, "justified"),
    (10.0, "marginal"),
    (1.0, "marginal"),
    (0.0, "marginal"),
    (-10.0, "marginal"),
    (-50.0, "not justified"),
])
def test_abatement_verdict_bands(margin, expected):
    assert outputs._abatement_verdict(margin) == expected


def test_iea_costs_cover_every_modelled_production_pathway():
    """The robustness check is only meaningful if it is complete.

    A silently dropped pathway would make the comparison look clean by
    omitting the case that disagrees.
    """
    emissions, _, _ = data_io.load_inputs()
    iea = data_io.iea_production_costs(2030)
    modelled = emissions[emissions["pathway"] != "cbam_default"]
    expected = set(zip(modelled["corridor"], modelled["product"], modelled["pathway"]))
    got = set(zip(iea["corridor"], iea["product"], iea["pathway"]))
    assert expected == got, f"missing from IEA table: {expected - got}"


def test_iea_costs_reject_unpublished_years():
    """The IEA sheet has 2025 and 2030 only. Interpolating would invent data."""
    for bad_year in (2026, 2027, 2028, 2029, 2031):
        with pytest.raises(ValueError):
            data_io.iea_production_costs(bad_year)


def test_iea_ranges_are_low_then_high():
    """Riya's sheet writes one range backwards (771-768). It is corrected in
    the table rather than carried through, so this pins that none survive."""
    for (region, product, route), by_year in data_io._IEA_USD_PER_TONNE.items():
        for year, (low, high) in by_year.items():
            assert low <= high, f"{region}/{product}/{route} {year} is {low}-{high}"
