"""Tests for the corridor cost model.

Expected values are hand-calculated in the test body rather than copied from a
previous run, so a regression in the model cannot quietly update its own
expectations.
"""

import pandas as pd
import pytest

from cbam_model import data_io, runner
from cbam_model.analysis import outputs
from cbam_model.config import regulatory_constants as rc
from cbam_model.config import scenarios
from cbam_model.config import vessel_logistics as vl
from cbam_model.config.unresolved import UnresolvedConstantError, is_unresolved
from cbam_model.model import cbam, ets_maritime, fueleu, total_cost
from cbam_model.validation import gayu_reproduction, unit_checks

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
    """Hydrogen and other non-fertiliser goods ramp 10/20/30 and hold."""
    assert rc.default_value_markup(2026, "hydrogen") == 0.10
    assert rc.default_value_markup(2027, "hydrogen") == 0.20
    assert rc.default_value_markup(2028, "hydrogen") == 0.30
    assert rc.default_value_markup(2034, "hydrogen") == 0.30


def test_fertiliser_default_value_markup_is_one_percent_in_every_year():
    """Ammonia is a fertiliser good for CBAM and carries a flat 1%, not the
    10/20/30 ramp. Verified against the Commission's adopted default values
    workbook, which publishes base and marked-up values side by side:
    Canada anhydrous ammonia 1.98 becomes 1.9998 in every year, and China's
    4.36 becomes 4.4036.

    An earlier version applied the ramp to every good, which overstated
    ammonia's default emissions by 8.9% in 2026 rising to 28.7% from 2028, on
    the study's primary scenario."""
    for year in (2026, 2027, 2028, 2034):
        assert rc.default_value_markup(year, "ammonia") == pytest.approx(0.01)

    assert 1.98 * (1 + rc.default_value_markup(2028, "ammonia")) == pytest.approx(
        1.9998, abs=1e-4
    )
    assert 4.36 * (1 + rc.default_value_markup(2028, "ammonia")) == pytest.approx(
        4.4036, abs=1e-4
    )
    # And the hydrogen figures from the same workbook, as the contrast.
    assert 10.82 * (1 + rc.default_value_markup(2028, "hydrogen")) == pytest.approx(
        14.066, abs=1e-3
    )


def test_default_value_markup_requires_the_product():
    """Defaulting it would silently reinstate the uniform-ramp bug, which is
    invisible in the output: it produces a plausible number that is too big."""
    with pytest.raises(ValueError, match="requires product"):
        cbam.eu_cbam_cost(10.0, 2026, 80.0, using_default_values=True)


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
    """10 tCO2e at 2.5% and EUR 80/t, no markup, no origin price.

    `mechanism` is pinned explicitly here and in the three tests below. These
    are unit tests of the factor-scaled arithmetic itself, which stays a
    supported option, so they must not follow EU_CBAM_DEFAULT_MECHANISM around.
    They were implicit until 7 August 2026, when the default became
    "benchmark_shielded".
    """
    cost = cbam.eu_cbam_cost(
        10.0, 2026, 80.0, using_default_values=False, mechanism="factor_scaled"
    )
    assert cost == pytest.approx(10.0 * 0.025 * 80.0)  # 20.00
    assert cost == pytest.approx(20.0)


def test_eu_cbam_cost_with_default_value_markup():
    """The 2026 markup is 10%, so 10 tCO2e becomes 11 chargeable tonnes."""
    cost = cbam.eu_cbam_cost(
        10.0, 2026, 80.0, using_default_values=True, product="hydrogen",
        mechanism="factor_scaled",
    )
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
        10.0, 2026, 80.0, origin_carbon_price_eur_per_tco2e=30.0,
        mechanism="factor_scaled",
    )
    assert cost == pytest.approx(10.0 * 0.025 * (80.0 - 30.0))  # 12.50
    assert cost > 0


def test_origin_carbon_price_above_ets_price_floors_at_zero():
    """A higher carbon price at origin cannot generate a negative CBAM cost."""
    cost = cbam.eu_cbam_cost(
        10.0, 2026, 80.0, origin_carbon_price_eur_per_tco2e=100.0,
        mechanism="factor_scaled",
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
    assert set(maritime["vessel_set"].unique()) == set(vl.VESSEL_SETS)
    assert "VLGC/VLAC" in set(maritime["vessel_class"].unique())


def test_vessel_set_and_vessel_class_are_separate_columns():
    """Regression guard. `vessel_set` used to be filled from the profile's
    `vessel_class`, so the same column name meant the scenario dimension in
    sensitivity frames and the ship's display name in maritime and compliance
    frames. Filtering across the two matched nothing, silently."""
    maritime = runner.run_maritime_matrix()
    compliance = runner.run_compliance_matrix()
    from cbam_model.analysis import sensitivity

    sweep = sensitivity.sweep_corridor(rc.HALIFAX_HAMBURG)

    for frame, name in (
        (maritime, "maritime"),
        (compliance, "compliance"),
        (sweep, "sweep"),
    ):
        unexpected = set(frame["vessel_set"].unique()) - set(vl.VESSEL_SETS)
        assert not unexpected, f"{name} carries non-scenario vessel_set: {unexpected}"

    # And the class name is still available, just under its own column.
    for frame, name in ((maritime, "maritime"), (compliance, "compliance")):
        assert "VLGC/VLAC" in set(frame["vessel_class"].unique()), name


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
        & (maritime["vessel_set"] == "gas_carrier")
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
    # 9 Aug 2026: 6170.0 -> 7460.0. Riya's table gives this cell as USD
    # 5.72-9.20/kg; the 4 Aug transcription read 5.72-6.62. The raw delivery
    # was not retained so the discrepancy could not be resolved from this side,
    # and her table owns the figure. No verdict or ranking changes.
    (rc.NINGBO_FELIXSTOWE, "hydrogen", "green_electrolysis"): 7460.0,
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
# Canada origin carbon price, corrected and made year-varying 5 August 2026
# ---------------------------------------------------------------------------


def test_canada_origin_carbon_price_matches_the_revised_2026_path():
    """CAD 95/100/100/100/115 for 2026-2030, the path published 15 May 2026.

    Regression guard on the 5 August 2026 correction: the old CAD 110 flat
    figure was an extrapolation from the December 2020 plan that this path
    superseded, never checked against a primary source.
    """
    expected = {2026: 95.0, 2027: 100.0, 2028: 100.0, 2029: 100.0, 2030: 115.0}
    for year, cad in expected.items():
        assert rc.origin_carbon_price_canada_cad(year) == cad


def test_origin_carbon_price_eur_dispatches_by_corridor():
    """Canada varies by year; China stays zero regardless of year."""
    for year in range(2026, 2031):
        assert rc.origin_carbon_price_eur(rc.HALIFAX_HAMBURG, year) == pytest.approx(
            rc.origin_carbon_price_canada_eur(year)
        )
        assert rc.origin_carbon_price_eur(rc.NINGBO_FELIXSTOWE, year) == 0.0


def test_cbam_matrix_uses_the_year_varying_origin_price_not_the_flat_column():
    """The emissions table's origin_carbon_price_eur_per_tco2e column is a
    flat 2026 baseline (see data_io._placeholder_emissions), but
    run_cbam_matrix must use the year-varying schedule, not that column, or
    the 2027-2030 CBAM figures would silently apply the wrong year's origin
    price. Checked by recomputing 2030 by hand with the flat 2026 figure and
    confirming it does NOT match what the matrix actually produced."""
    emissions, _, _ = data_io.load_inputs()
    row = emissions[
        (emissions["corridor"] == rc.HALIFAX_HAMBURG)
        & (emissions["product"] == "hydrogen")
        & (emissions["pathway"] == "grey_smr")
    ].iloc[0]

    cbam = runner.run_cbam_matrix(emissions, years=(2030,), skip_unresolved=False)
    actual_2030 = cbam[
        (cbam["corridor"] == rc.HALIFAX_HAMBURG)
        & (cbam["product"] == "hydrogen")
        & (cbam["pathway"] == "grey_smr")
        & (cbam["price_scenario"] == "medium")
    ]["eu_cbam_cost_eur_per_tonne"].iloc[0]

    wrong_2030_with_flat_origin_price = total_cost.cbam_cost_per_tonne(
        corridor=rc.HALIFAX_HAMBURG, product="hydrogen", pathway="grey_smr",
        year=2030, price_scenario="medium",
        embedded_emissions_tco2e_per_tonne=row["embedded_emissions_tco2e_per_tonne"],
        origin_carbon_price_eur_per_tco2e=row["origin_carbon_price_eur_per_tco2e"],
    ).eu_cbam_cost_eur_per_tonne

    assert actual_2030 != pytest.approx(wrong_2030_with_flat_origin_price)
    # And it should be lower, since 2030's real origin price (EUR 71.75) is
    # higher than the flat 2026 baseline (EUR 59.27) the wrong version uses,
    # giving a bigger deduction.
    assert actual_2030 < wrong_2030_with_flat_origin_price


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
    """IR (EU) 2026/1412 Annex section 2, read off the adopted Official Journal
    text on 6 August 2026. Supersedes IR 2021/447 for the 2026-2030 period.

    The two products move in opposite directions and that is not a typo:
    ammonia falls 1.570 -> 1.522, hydrogen RISES 6.84 -> 7.98 because
    Delegated Regulation (EU) 2024/873 folded electrolytic hydrogen into the
    benchmark and section 2 benchmarks now count indirect emissions from
    electricity consumption. A future edit that "corrects" hydrogen downward
    to look consistent with ammonia would be wrong.
    """
    b = rc.EU_ETS_PRODUCT_BENCHMARK_TCO2E_PER_TONNE
    assert b["ammonia"] == pytest.approx(1.522)
    assert b["hydrogen"] == pytest.approx(7.98)
    assert set(b) == set(rc.PRODUCTS)
    assert rc.EU_ETS_PRODUCT_BENCHMARK_PERIOD == "2026-2030"
    assert rc.EU_ETS_PRODUCT_BENCHMARK_IS_CURRENT

    # The superseded set is retained for the Ramsook calibration only.
    old = rc.EU_ETS_PRODUCT_BENCHMARK_2021_2025
    assert old["ammonia"] == pytest.approx(1.570)
    assert old["hydrogen"] == pytest.approx(6.84)


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
    expected = set(zip(modelled["corridor"], modelled["product"], modelled["pathway"], strict=False))
    got = set(zip(iea["corridor"], iea["product"], iea["pathway"], strict=False))
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


def test_ayub_costs_cover_only_canada_hydrogen():
    """Ayub et al. (2024) is a Canada-only cross-check, unlike the IEA one.

    It should never silently claim coverage of China or ammonia, which it
    does not report figures for.
    """
    ayub = data_io.ayub_production_costs()
    assert set(ayub["corridor"]) == {rc.HALIFAX_HAMBURG}
    assert set(ayub["product"]) == {"hydrogen"}
    assert set(ayub["pathway"]) == {"grey_smr", "blue_smr_ccs", "green_electrolysis"}


def test_ayub_grey_hydrogen_matches_the_primary_figure():
    """Ayub's Canada natural-gas-reforming cost (USD 700/t) is the one figure
    in this cross-check that lands on the primary literature number exactly,
    rather than diverging from it. Worth pinning so a future edit to either
    source doesn't erase the agreement without anyone noticing."""
    primary = data_io._placeholder_commercial()
    primary_grey = primary[
        (primary["corridor"] == rc.HALIFAX_HAMBURG)
        & (primary["product"] == "hydrogen")
        & (primary["pathway"] == "grey_smr")
    ]["production_cost_eur_per_tonne"].iloc[0]
    ayub = data_io.ayub_production_costs()
    ayub_grey = ayub[ayub["pathway"] == "grey_smr"]["production_cost_eur_per_tonne"].iloc[0]
    assert primary_grey == pytest.approx(ayub_grey, abs=0.1)


# ---------------------------------------------------------------------------
# Choice and timing analyses, added 5 August 2026
# ---------------------------------------------------------------------------


def test_pathway_ranking_excludes_the_regulatory_default():
    """`cbam_default` is an emissions figure, not a production route a producer
    could pick, and its production cost is only borrowed from the grey pathway.
    Ranking it against real routes would compare a route to a bookkeeping
    convention. Same exclusion `marginal_abatement_cost` already makes."""
    emissions, _, commercial = data_io.load_inputs()
    ranking = outputs.pathway_cost_ranking(emissions, commercial)
    assert len(ranking)
    assert "cbam_default" not in set(ranking["pathway"])


def test_pathway_visible_cost_is_production_plus_cbam_hand_calculation():
    """Hand-calculated against Canada green hydrogen in 2030.

    Production cost EUR 3,607.8/t (Riya's literature sheet, USD 4,110 midpoint
    at the 23 July 2026 ECB rate). CBAM: 1.23 tCO2e/t embedded, no default-value
    mark-up because this is a literature pathway, 2030 CBAM factor 0.485, EU ETS
    medium price EUR 126, Canada origin price EUR 71.75 (CAD 115 x 0.62393).

    Under the "benchmark_shielded" default adopted on 7 August 2026, free
    allocation shields the hydrogen CBAM benchmark. Corrected on 8 August 2026
    from the EU ETS benchmark (7.98) to the CBAM benchmark from IR 2025/2620
    (5.089), with the CSCF term the same regulation requires:

        chargeable = max(0, 1.23 - 5.089 x (1 - 0.485) x 1.0)
                   = max(0, -1.391) = 0

    Still zero, but by a smaller margin than the ETS benchmark gave. The verdict
    is unchanged here; it is not unchanged everywhere, which is why the
    correction moved the corridor results.

    So green hydrogen owes NOTHING. That is the substantive consequence of the
    mechanism, not a rounding artefact: a producer this far below the benchmark
    is fully shielded until free allocation runs out in 2034. Under the previous
    "factor_scaled" default the same row read 1.23 x 0.485 x (126 - 71.75) =
    EUR 32.36/t, which is asserted below as the contrast so the two forms stay
    hand-checked side by side.
    """
    emissions, _, commercial = data_io.load_inputs()
    ranking = outputs.pathway_cost_ranking(emissions, commercial, year=2030)
    row = ranking[
        (ranking["corridor"] == rc.HALIFAX_HAMBURG)
        & (ranking["product"] == "hydrogen")
        & (ranking["pathway"] == "green_electrolysis")
    ].iloc[0]

    assert 1.23 < rc.cbam_benchmark("hydrogen") * (1 - rc.cbam_factor(2030)) * rc.cbam_cscf(2030)
    assert row["cbam_cost_eur_per_tonne"] == pytest.approx(0.0, abs=0.01)
    assert row["pathway_visible_cost_eur_per_tonne"] == pytest.approx(
        row["production_cost_eur_per_tonne"], abs=0.01
    )

    # The superseded factor-scaled figure, kept as an explicit cross-check.
    assert cbam.eu_cbam_cost(
        1.23, 2030, 126.0, 71.75, mechanism="factor_scaled"
    ) == pytest.approx(32.36, abs=0.01)


def test_uk_pathway_cost_is_converted_to_eur_not_left_in_gbp():
    """The UK corridor's CBAM liability comes back in GBP while production costs
    are EUR. Adding them unconverted would understate UK CBAM by about 17% and
    silently mix currencies inside a single column."""
    emissions, _, commercial = data_io.load_inputs()
    ranking = outputs.pathway_cost_ranking(emissions, commercial, year=2030)
    row = ranking[
        (ranking["corridor"] == rc.NINGBO_FELIXSTOWE)
        & (ranking["product"] == "hydrogen")
        & (ranking["pathway"] == "green_electrolysis")
    ].iloc[0]

    # 2.34 tCO2e/t x 2030 rate fraction x UK medium price, then GBP -> EUR.
    gbp = 2.34 * rc.uk_cbam_rate_fraction(2030) * rc.UK_ETS_PRICE_SCENARIOS["medium"]
    assert row["cbam_cost_eur_per_tonne"] == pytest.approx(
        rc.gbp_to_eur(gbp), abs=0.01
    )
    assert row["cbam_cost_eur_per_tonne"] > gbp  # converted, not left in GBP


def test_cheapest_pathway_is_the_minimum_of_the_ranking():
    emissions, _, commercial = data_io.load_inputs()
    ranking = outputs.pathway_cost_ranking(emissions, commercial)
    cheapest = outputs.cheapest_pathway(emissions, commercial)

    for (corridor, product), grp in ranking.groupby(["corridor", "product"]):
        want = grp.loc[grp["pathway_visible_cost_eur_per_tonne"].idxmin()]["pathway"]
        got = cheapest[
            (cheapest["corridor"] == corridor) & (cheapest["product"] == product)
        ]["pathway"].iloc[0]
        assert got == want


def test_carbon_pricing_does_not_flip_the_commercial_pathway_choice():
    """The headline finding of the choice analysis, pinned so a future input
    change that overturns it cannot pass unnoticed.

    At 2030 prices the dirtiest pathway is still the cheapest on every
    corridor and product, because the production cost gap between grey and
    green is an order of magnitude larger than the CBAM differential between
    them. If this ever fails it is a genuine result, not a broken test."""
    emissions, _, commercial = data_io.load_inputs()
    cheapest = outputs.cheapest_pathway(emissions, commercial, year=2030)
    assert set(cheapest["pathway"]) <= {"grey_smr", "coal_gasification"}


def test_pathway_choice_price_stability_holds_except_for_eu_hydrogen():
    """A robustness property that the 7 August 2026 mechanism switch COST US.

    Under "factor_scaled" every corridor-product pair picked the same cheapest
    pathway at low, medium and high carbon prices, so the recommendation did not
    restate the price assumption. Under "benchmark_shielded" that is no longer
    true for Halifax-Hamburg hydrogen in 2030: grey SMR wins at low and medium
    prices, blue SMR+CCS wins at high prices. The benchmark form charges the
    grey pathway on its full excess over the 7.98 benchmark from the start, so a
    high price is enough to overturn the production-cost gap that previously
    dominated.

    This is a real weakening of the findings and must be reported, not smoothed
    over: the EU hydrogen pathway recommendation is now price-contingent. The
    test pins the exact row so any FURTHER loss of stability still fails.
    """
    emissions, _, commercial = data_io.load_inputs()
    stability = outputs.pathway_choice_price_robustness(emissions, commercial)
    assert len(stability)

    unstable = stability[~stability["choice_stable"]]
    assert len(unstable) == 1, (
        "the set of price-unstable pathway choices has moved; under "
        "benchmark_shielded exactly one row (EU hydrogen 2030) is unstable"
    )
    row = unstable.iloc[0]
    assert row["corridor"] == rc.HALIFAX_HAMBURG
    assert row["product"] == "hydrogen"
    assert row["cheapest_pathway_low"] == "grey_smr"
    assert row["cheapest_pathway_medium"] == "grey_smr"
    assert row["cheapest_pathway_high"] == "blue_smr_ccs"

    # Everything else still holds, which is what makes the exception reportable.
    assert stability[stability["choice_stable"]]["distinct_choices"].eq(1).all()


def test_corridor_comparison_survives_a_csv_round_trip(tmp_path):
    """The EU corridor stores "n/a" in the UK-only scenario columns, and pandas
    reads that back from CSV as NaN. A base-case filter written as a plain
    isin() therefore drops every Halifax-Hamburg row when the frame came from
    disk, leaving a one-corridor "comparison" and no error to notice."""
    emissions, _, _ = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)

    path = tmp_path / "compliance.csv"
    compliance.to_csv(path, index=False)
    reloaded = pd.read_csv(path)

    assert reloaded["uk_ets_variant"].isna().any()  # the trap this guards
    from_disk = outputs.corridor_cost_comparison(reloaded)
    in_memory = outputs.corridor_cost_comparison(compliance)

    assert len(from_disk) == len(in_memory)
    assert from_disk["halifax_hamburg_gbp_equivalent"].notna().all()


def test_corridor_crossover_happens_when_uk_cbam_starts():
    """Ningbo-Felixstowe is cheaper in 2026 on both products, because UK CBAM
    does not exist yet. What happens after 2026 now differs by product.

    AMMONIA crosses to Halifax-Hamburg in 2027, when UK CBAM starts, and stays
    there for the rest of the horizon. That has held under every mechanism and
    every UK price path the model runs.

    HYDROGEN does not cross at all on the baseline UK price path. It stays on
    Ningbo-Felixstowe in every year. This changed on 8 August 2026, when the
    benchmark was corrected from the EU ETS product benchmark (7.98) to the CBAM
    benchmark required by IR 2025/2620 (5.089). The smaller shield raises EU
    hydrogen liability enough that Halifax-Hamburg never becomes the cheaper
    corridor. Before the correction the model showed hydrogen crossing to
    Halifax-Hamburg in 2027 and back again in 2028, and that reversal was an
    artefact of shielding hydrogen by 56.8% more than the law allows.
    """
    emissions, _, _ = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)
    crossover = outputs.corridor_crossover_year(compliance)

    assert len(crossover)
    by_product = {row["product"]: row for _, row in crossover.iterrows()}

    ammonia = by_product["ammonia"]
    assert ammonia["cheaper_corridor_first_year"] == rc.NINGBO_FELIXSTOWE
    assert ammonia["crossover_year"] == rc.UK_CBAM_START_YEAR
    assert ammonia["ordering_changes"]
    assert ammonia["cheaper_corridor_last_year"] == rc.HALIFAX_HAMBURG

    hydrogen = by_product["hydrogen"]
    assert hydrogen["cheaper_corridor_first_year"] == rc.NINGBO_FELIXSTOWE
    assert hydrogen["cheaper_corridor_last_year"] == rc.NINGBO_FELIXSTOWE
    assert not hydrogen["ordering_changes"]
    assert pd.isna(hydrogen["crossover_year"])


def test_breakeven_flags_the_frozen_uk_price_as_unable_to_cross():
    """A frozen carbon price cannot produce a crossing, so every UK row must
    carry `carbon_price_varies_by_year == False` and a note saying so. Without
    that flag a reader would take "no breakeven year" as evidence that
    switching never pays on the UK corridor, when it is an artefact of only the
    2026 UK price ever having been sourced."""
    emissions, _, commercial = data_io.load_inputs()
    breakeven = outputs.abatement_breakeven_year(emissions, commercial)

    uk = breakeven[breakeven["corridor"] == rc.NINGBO_FELIXSTOWE]
    eu = breakeven[breakeven["corridor"] == rc.HALIFAX_HAMBURG]
    assert len(uk) and len(eu)

    assert not uk["carbon_price_varies_by_year"].any()
    assert uk["note"].str.contains("frozen").all()
    assert (uk["verdict_first_year"] == uk["verdict_last_year"]).all()

    assert eu["carbon_price_varies_by_year"].all()
    assert (eu["note"] == "").all()


def test_breakeven_does_not_count_a_marginal_verdict_as_a_crossing():
    """China green ammonia sits inside the 10% marginal band, and the whole
    point of that band is that such a row is not distinguishable from the other
    side of the threshold. It must appear as `first_marginal_year`, never as
    `breakeven_year`."""
    emissions, _, commercial = data_io.load_inputs()
    breakeven = outputs.abatement_breakeven_year(emissions, commercial)

    row = breakeven[
        (breakeven["corridor"] == rc.NINGBO_FELIXSTOWE)
        & (breakeven["product"] == "ammonia")
        & (breakeven["pathway"] == "green_electrolysis")
    ].iloc[0]

    assert row["verdict_first_year"] == "marginal"
    assert row["breakeven_year"] is None or pd.isna(row["breakeven_year"])
    assert row["first_marginal_year"] == 2026


# ---------------------------------------------------------------------------
# Lock-in and corridor switching
# ---------------------------------------------------------------------------


def test_present_value_leaves_the_decision_year_undiscounted():
    """The commitment is made at the start of the decision year, so t=0 there.

    If this ever shifts to t=1 every threshold in `corridor_lock_in` becomes
    incomparable with a capital cost incurred at signature, which is exactly
    the kind of silent basis mismatch this project has been bitten by before.
    """
    from cbam_model.model import switching

    assert switching.present_value([100.0], 0.08) == pytest.approx(100.0)
    # 100 + 100/1.08 = 192.5926
    assert switching.present_value([100.0, 100.0], 0.08) == pytest.approx(
        192.59259, rel=1e-5
    )


def test_extend_to_tenor_truncates_by_default_and_holds_final_on_request():
    from cbam_model.model import switching

    modelled = [1.0, 2.0, 3.0]
    assert switching.extend_to_tenor(modelled, 5, "truncate") == [1.0, 2.0, 3.0]
    assert switching.extend_to_tenor(modelled, 5, "hold_final") == [
        1.0, 2.0, 3.0, 3.0, 3.0,
    ]
    # A tenor shorter than the modelled horizon clips under both methods.
    assert switching.extend_to_tenor(modelled, 2, "hold_final") == [1.0, 2.0]

    with pytest.raises(ValueError):
        switching.extend_to_tenor(modelled, 5, "linear_trend")


def test_breakeven_switching_cost_floors_at_zero():
    """If the alternative corridor is dearer over the tenor, no switching cost
    however small justifies the move. The floor must not be allowed to report a
    negative "saving"."""
    from cbam_model.model import switching

    dearer = switching.breakeven_switching_cost(
        incumbent_annual_costs=[10.0, 10.0],
        alternative_annual_costs=[50.0, 50.0],
        tenor_years=2,
    )
    assert dearer == 0.0

    cheaper = switching.breakeven_switching_cost(
        incumbent_annual_costs=[50.0, 50.0],
        alternative_annual_costs=[10.0, 10.0],
        tenor_years=2,
        discount_rate=0.08,
    )
    # 40 + 40/1.08 = 77.037
    assert cheaper == pytest.approx(77.03704, rel=1e-5)


def test_switch_verdict_bands_a_thin_margin_as_marginal():
    """Same guard as `_abatement_verdict`, and for the same documented reason:
    a bare boolean once reported "justified" on a 1% margin in this project."""
    from cbam_model.model import switching

    assert switching.switch_verdict(101.0, 100.0) == "marginal"
    assert switching.switch_verdict(99.0, 100.0) == "marginal"
    assert switching.switch_verdict(200.0, 100.0) == "justified"
    assert switching.switch_verdict(50.0, 100.0) == "locked_in"


def test_switch_verdict_separates_never_justified_from_locked_in():
    """`never_justified` means the alternative is not cheaper over the tenor at
    any price. `locked_in` means it is cheaper but not by enough. Collapsing
    the two would let the write-up claim a corridor is unreachable when it is
    merely expensive to reach."""
    from cbam_model.model import switching

    assert switching.switch_verdict(0.0, 100.0) == "never_justified"
    assert switching.switch_verdict(0.0, 0.0) == "never_justified"
    assert switching.switch_verdict(50.0, 100.0) == "locked_in"


def test_lock_in_is_an_ammonia_only_finding():
    """The headline lock-in finding, medium prices, 8% real, truncate.

    AMMONIA, decision year 2026, is the whole of it. Ningbo-Felixstowe is
    cheaper on the spot because UK CBAM has not started. Committing on that
    basis is wrong: the ordering flips in 2027 and stays flipped, so the tenor
    favours Halifax-Hamburg.
        PV HH 115.76, PV NF 154.48, breakeven 38.72, regret 33.45%

    HYDROGEN does not reverse in any year. Its spot-cheapest and tenor-cheapest
    corridors agree throughout, both Ningbo-Felixstowe, so every hydrogen row
    reads a zero breakeven and no reversal.

    This test has been rewritten twice and the history matters, because two
    superseded versions of this finding are quoted in earlier documents:

      1. Under "factor_scaled", both products reversed in 2026 toward
         Halifax-Hamburg (ammonia breakeven 91.60, hydrogen 491.95).
      2. Under "benchmark_shielded" with the EU ETS benchmark wrongly netted
         off, the two products gave OPPOSED advice: ammonia toward
         Halifax-Hamburg in 2026, hydrogen toward Ningbo-Felixstowe in 2027
         (breakeven 43.24). That opposition was the more interesting finding
         and it does not survive.

    Correcting the benchmark to the CBAM benchmark required by IR 2025/2620
    (hydrogen 5.089, not the ETS 7.98) removed hydrogen's reversal entirely.
    The opposed-advice claim must not be quoted from any document predating
    8 August 2026.
    """
    emissions, _, _ = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)
    lock_in = outputs.corridor_lock_in(compliance, beyond_horizon="truncate")
    assert len(lock_in)

    ammonia = lock_in[
        (lock_in["product"] == "ammonia") & (lock_in["decision_year"] == 2026)
    ].iloc[0]
    assert ammonia["myopic_choice"] == rc.NINGBO_FELIXSTOWE
    assert ammonia["committed_choice"] == rc.HALIFAX_HAMBURG
    assert ammonia["decision_reverses"]
    assert ammonia["pv_halifax_hamburg_gbp_per_tonne_annual_volume"] == pytest.approx(
        115.76, abs=0.05
    )
    assert ammonia["pv_ningbo_felixstowe_gbp_per_tonne_annual_volume"] == pytest.approx(
        154.48, abs=0.05
    )
    assert ammonia[
        "breakeven_switching_cost_gbp_per_tonne_annual_volume"
    ] == pytest.approx(38.72, abs=0.05)
    assert ammonia["lock_in_regret_pct"] == pytest.approx(33.45, abs=0.05)

    # Hydrogen never reverses. If this starts failing, the corridor story has
    # changed again and the discussion chapter needs rewriting.
    hydrogen = lock_in[lock_in["product"] == "hydrogen"]
    assert len(hydrogen)
    assert not hydrogen["decision_reverses"].any()
    assert (hydrogen["myopic_choice"] == rc.NINGBO_FELIXSTOWE).all()
    assert (hydrogen["committed_choice"] == rc.NINGBO_FELIXSTOWE).all()
    assert (
        hydrogen["breakeven_switching_cost_gbp_per_tonne_annual_volume"] == 0.0
    ).all()


def test_lock_in_reversal_survives_both_beyond_horizon_treatments():
    """The two beyond-horizon treatments err in opposite directions, so a
    finding that only holds under one of them is an artefact of the assumption
    rather than a result. Mirrors the robustness guard on
    `abatement_source_robustness`.

    The single ammonia reversal survives both treatments, in the same year and
    the same direction. Only the magnitude moves: breakeven 38.72 under truncate
    against 76.99 under hold_final, regret 33.45% against 26.91%.

    Hydrogen contributes no reversal under either treatment, so the set has
    exactly one member. Before the 8 August 2026 benchmark correction it had two
    and they pointed in opposite directions.
    """
    emissions, _, _ = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)

    expected = {("ammonia", 2026): rc.HALIFAX_HAMBURG}
    for method in ("truncate", "hold_final"):
        lock_in = outputs.corridor_lock_in(compliance, beyond_horizon=method)
        reversals = lock_in[lock_in["decision_reverses"]]
        got = {
            (r["product"], r["decision_year"]): r["committed_choice"]
            for _, r in reversals.iterrows()
        }
        assert got == expected, (
            f"under {method}, the set or direction of lock-in reversals moved"
        )


def test_lock_in_reports_no_switch_once_the_orderings_agree():
    """From 2027 the spot-cheapest and tenor-cheapest corridors are the same, so
    the breakeven must be exactly zero. A non-zero figure there would imply a
    switch is worth paying for when there is nothing to switch to."""
    emissions, _, _ = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)
    lock_in = outputs.corridor_lock_in(compliance)

    # Every row from 2027 on is settled, on both products. The hydrogen 2027
    # carve-out this test used to carry was removed on 8 August 2026 with the
    # benchmark correction, which eliminated hydrogen's reversal.
    settled = lock_in[lock_in["decision_year"] >= 2027]
    assert len(settled)
    assert not settled["decision_reverses"].any()
    assert (
        settled["breakeven_switching_cost_gbp_per_tonne_annual_volume"] == 0.0
    ).all()


def test_switching_cost_sensitivity_flips_the_verdict_around_the_breakeven():
    """Below the breakeven the switch is justified, well above it the firm is
    locked in, and rows where nothing is gained read `never_justified`."""
    emissions, _, _ = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)
    sweep = outputs.switching_cost_sensitivity(compliance)
    assert len(sweep)

    ammonia_2026 = sweep[
        (sweep["product"] == "ammonia") & (sweep["decision_year"] == 2026)
    ]
    breakeven = ammonia_2026[
        "breakeven_switching_cost_gbp_per_tonne_annual_volume"
    ].iloc[0]

    cheap = ammonia_2026[
        ammonia_2026["assumed_switching_cost_gbp_per_tonne_annual_volume"]
        < breakeven * 0.9
    ]
    dear = ammonia_2026[
        ammonia_2026["assumed_switching_cost_gbp_per_tonne_annual_volume"]
        > breakeven * 1.1
    ]
    assert len(cheap) and len(dear)
    assert (cheap["verdict"] == "justified").all()
    assert (dear["verdict"] == "locked_in").all()

    # Ammonia 2026 is the ONLY row with a live switching decision. Its breakeven
    # is 38.72, so 10 and 25 read justified and 50 upwards read locked_in. Every
    # other row in the sweep has nothing to switch to and reads never_justified.
    assert set(
        ammonia_2026[ammonia_2026["verdict"] == "justified"][
            "assumed_switching_cost_gbp_per_tonne_annual_volume"
        ]
    ) == {10.0, 25.0}

    # Hydrogen carried a second live decision at 2027 until 8 August 2026. The
    # benchmark correction removed it, so hydrogen must now be uniformly
    # never_justified.
    hydrogen = sweep[sweep["product"] == "hydrogen"]
    assert len(hydrogen)
    assert (hydrogen["verdict"] == "never_justified").all()

    # Every other post-2026 row has nothing to switch to.
    settled = sweep[
        (sweep["decision_year"] >= 2027)
        & ~((sweep["product"] == "hydrogen") & (sweep["decision_year"] == 2027))
    ]
    assert len(settled)
    assert (settled["verdict"] == "never_justified").all()


# ---------------------------------------------------------------------------
# EU CBAM free-allocation mechanism
# ---------------------------------------------------------------------------


def test_default_cbam_mechanism_is_the_benchmark_form():
    """Pins the default switched on 7 August 2026.

    This test previously pinned "factor_scaled" and was named
    `test_default_cbam_mechanism_is_unchanged`. The default moved because the
    2026-2030 benchmarks landed on 6 August 2026 and removed the only reason
    the factor-scaled form was the incumbent. The switch is Samir's call, taken
    without a supervisor ruling and settled on IR 2025/2620, so this test is the
    record of a defended choice. If it is ever reversed, flip
    EU_CBAM_DEFAULT_MECHANISM back and this test with it.

    See the long comment above the constant for the evidence on each side.
    """
    assert rc.EU_CBAM_DEFAULT_MECHANISM == "benchmark_shielded"
    # 2.18 tCO2e ammonia, 2026 factor 0.025 so free allocation share 0.975,
    # benchmark 1.522 => max(0, 2.18 - 1.522 * 0.975) = 0.69605, x 80 = 55.68
    assert cbam.eu_cbam_cost(
        2.18, 2026, 80.0, benchmark_tco2e_per_tonne=1.522
    ) == pytest.approx(55.68, abs=0.01)
    # The factor-scaled form stays available and unchanged.
    assert cbam.eu_cbam_cost(
        10.0, 2026, 80.0, mechanism="factor_scaled"
    ) == pytest.approx(20.0)


def test_default_path_without_a_benchmark_now_raises():
    """The switch must not be silent at a call site that never opted in.

    Before 7 August 2026 a bare `eu_cbam_cost(e, year, price)` returned the
    factor-scaled number. It now raises, because the benchmark form refuses to
    default its benchmark. That is the intended blast radius of the switch: an
    un-updated caller fails loudly instead of quietly changing meaning.
    """
    with pytest.raises(ValueError, match="benchmark_tco2e_per_tonne"):
        cbam.eu_cbam_cost(2.18, 2026, 80.0)


def test_benchmark_mechanism_hand_calculation():
    """chargeable = max(0, embedded - benchmark x (1 - CBAM_factor)).

    Ammonia 2026: factor 0.025, so free allocation share 0.975.
    chargeable = 2.18 - 1.570 * 0.975 = 2.18 - 1.53075 = 0.64925
    cost       = 0.64925 * 80 = 51.94
    """
    cost = cbam.eu_cbam_cost(
        2.18, 2026, 80.0, mechanism="benchmark_shielded",
        benchmark_tco2e_per_tonne=1.570,
    )
    assert cost == pytest.approx(51.94, abs=0.01)


def test_benchmark_mechanism_zeroes_a_producer_below_the_benchmark():
    """A producer at or below the benchmark owes nothing while free allocation
    is still phasing out. The factor-scaled form has no such behaviour and
    charges them a small amount, which is the substantive difference between
    the two mechanisms for green pathways."""
    green = cbam.eu_cbam_cost(
        0.62, 2026, 80.0, mechanism="benchmark_shielded",
        benchmark_tco2e_per_tonne=1.570,
    )
    assert green == 0.0
    assert cbam.eu_cbam_cost(0.62, 2026, 80.0, mechanism="factor_scaled") > 0.0


def test_the_two_mechanisms_converge_when_free_allocation_ends():
    """In 2034 the CBAM factor reaches 1.00 and free allocation is gone, so the
    benchmark shields nothing and the two forms must agree exactly. If this
    ever fails, one of them has drifted from the phase-in schedule."""
    assert rc.cbam_factor(2034) == pytest.approx(1.0)
    for embedded in (0.62, 2.18, 10.07):
        scaled = cbam.eu_cbam_cost(embedded, 2034, 80.0, mechanism="factor_scaled")
        shielded = cbam.eu_cbam_cost(
            embedded, 2034, 80.0, mechanism="benchmark_shielded",
            benchmark_tco2e_per_tonne=1.570,
        )
        assert scaled == pytest.approx(shielded)


def test_benchmark_mechanism_refuses_to_run_without_a_benchmark():
    """Defaulting the benchmark to zero would silently collapse the benchmark
    mechanism into the factor-scaled one and look like the two agreeing."""
    with pytest.raises(ValueError, match="benchmark_tco2e_per_tonne"):
        cbam.eu_cbam_cost(2.18, 2026, 80.0, mechanism="benchmark_shielded")


def test_unknown_cbam_mechanism_raises():
    with pytest.raises(ValueError, match="Unknown EU CBAM mechanism"):
        cbam.eu_cbam_cost(2.18, 2026, 80.0, mechanism="benchmark")


def test_cbam_benchmark_raises_on_unknown_product():
    """A zero benchmark would be indistinguishable from agreement between the
    mechanisms, so an unknown product must fail rather than default.

    The values are the CBAM benchmarks from IR 2025/2620 Annex point 5.3, NOT
    the EU ETS product benchmarks. Ammonia is 1.522 under both, which is a
    coincidence. Hydrogen is 5.089 here against 7.98 in the ETS set, and using
    the ETS figure was the bug corrected on 8 August 2026.
    """
    assert rc.cbam_benchmark("ammonia") == pytest.approx(1.522)
    assert rc.cbam_benchmark("hydrogen") == pytest.approx(5.089)
    with pytest.raises(KeyError):
        rc.cbam_benchmark("methanol")

    # The divergence from the ETS set is the whole point of the correction.
    assert rc.cbam_benchmark("hydrogen") != rc.EU_ETS_PRODUCT_BENCHMARK_TCO2E_PER_TONNE[
        "hydrogen"
    ]
    assert not hasattr(rc, "eu_product_benchmark"), (
        "eu_product_benchmark was removed deliberately: it returned an ETS "
        "benchmark that callers were netting off the CBAM obligation."
    )


def test_cbam_cost_per_tonne_pairs_each_product_with_its_own_benchmark():
    """The lookup is by product inside `cbam_cost_per_tonne`, so a caller cannot
    pair a hydrogen row with the ammonia benchmark."""
    ammonia = total_cost.cbam_cost_per_tonne(
        corridor=rc.HALIFAX_HAMBURG, product="ammonia", pathway="grey_smr",
        year=2026, price_scenario="medium",
        embedded_emissions_tco2e_per_tonne=2.18,
        cbam_mechanism="benchmark_shielded",
    ).eu_cbam_cost_eur_per_tonne
    hydrogen = total_cost.cbam_cost_per_tonne(
        corridor=rc.HALIFAX_HAMBURG, product="hydrogen", pathway="grey_smr",
        year=2026, price_scenario="medium",
        embedded_emissions_tco2e_per_tonne=2.18,
        cbam_mechanism="benchmark_shielded",
    ).eu_cbam_cost_eur_per_tonne
    # Same emissions, different CBAM benchmark (1.522 vs 5.089), so hydrogen's
    # larger benchmark shields it entirely while ammonia still owes something.
    assert ammonia > 0.0
    assert hydrogen == 0.0


def test_mechanism_comparison_carries_the_benchmark_provenance():
    """Every benchmark-based figure must carry the instrument that produced it,
    so a stale rerun cannot masquerade as a current one.

    The provenance columns changed on 8 August 2026. They used to name the EU
    ETS benchmark period, which was itself the bug: the figures were being
    sourced from the wrong instrument. They now name IR 2025/2620 and carry the
    CSCF alongside, including whether it is sourced or assumed.
    """
    emissions, _, _ = data_io.load_inputs()
    comparison = outputs.cbam_mechanism_comparison(emissions)
    assert len(comparison)

    assert (comparison["benchmark_source"] == rc.CBAM_BENCHMARK_SOURCE).all()
    assert "2025/2620" in rc.CBAM_BENCHMARK_SOURCE
    # The CSCF is an assumption, and the output must say so rather than let a
    # reader take 1.0 for a sourced regulatory value.
    assert (comparison["cscf"] == 1.0).all()
    assert not comparison["cscf_is_sourced"].any()
    # EU corridor only: the UK rate fraction nets free allocation off already.
    assert set(comparison["corridor"]) == {rc.HALIFAX_HAMBURG}


def test_mechanism_switch_moves_clean_and_dirty_pathways_in_opposite_directions():
    """The headline of the mechanism gap, and the reason it matters for this
    dissertation: under the benchmark form green pathways owe nothing at all,
    while pathways above the benchmark owe substantially more. The current
    model therefore understates how far CBAM closes the green premium."""
    emissions, _, _ = data_io.load_inputs()
    comparison = outputs.cbam_mechanism_comparison(emissions)

    clean = comparison[comparison["cleaner_than_benchmark"]]
    dirty = comparison[~comparison["cleaner_than_benchmark"]]
    assert len(clean) and len(dirty)

    assert (clean["benchmark_shielded_eur_per_tonne"] == 0.0).all()
    assert (clean["difference_eur_per_tonne"] <= 0).all()
    assert (dirty["difference_eur_per_tonne"] > 0).all()


def test_the_mechanism_choice_inverts_the_corridor_finding():
    """A guard on the open methodological decision, not on a settled result.

    Switching `EU_CBAM_DEFAULT_MECHANISM` does not merely rescale the corridor
    comparison, it reverses which corridor is cheaper across most of the
    horizon, because the EU corridor's liability rises steeply under the
    benchmark form while the UK corridor is untouched (the UK scheme nets free
    allocation off inside its own rate fraction).

    This test exists so that a future change to the default cannot pass
    silently. If it fails, the corridor findings in the README and the results
    chapter need rewriting, not just regenerating.
    """
    emissions, _, _ = data_io.load_inputs()

    orderings = {}
    for mechanism in rc.EU_CBAM_MECHANISMS:
        compliance = runner.run_compliance_matrix(
            emissions, cbam_mechanism=mechanism
        )
        comparison = outputs.corridor_cost_comparison(compliance)
        for product in ("ammonia", "hydrogen"):
            rows = comparison[comparison["product"] == product]
            orderings[(mechanism, product)] = list(
                rows.sort_values("year")["cheaper_corridor"]
            )

    hh, nf = rc.HALIFAX_HAMBURG, rc.NINGBO_FELIXSTOWE

    # Ammonia agrees under both mechanisms. It did NOT before the fertiliser
    # mark-up fix of 7 August 2026: dropping ammonia's mark-up from 30% to the
    # legislated 1% lowered EU liability enough that the benchmark shield no
    # longer flips the ordering. So the open mechanism decision no longer
    # touches ammonia at all.
    assert orderings[("factor_scaled", "ammonia")] == [nf, hh, hh, hh, hh]
    assert orderings[("benchmark_shielded", "ammonia")] == [nf, hh, hh, hh, hh]

    # Hydrogen still diverges, so the decision still has to be taken, but the
    # shape of the divergence changed on 8 August 2026 with the benchmark
    # correction. It used to read [nf, hh, nf, nf, nf] under the benchmark form,
    # a flip out and back. With the CBAM benchmark (5.089, not the ETS 7.98) the
    # smaller shield keeps the UK corridor cheaper throughout, so the choice is
    # now between "EU corridor from 2027" and "UK corridor always".
    assert orderings[("factor_scaled", "hydrogen")] == [nf, hh, hh, hh, hh]
    assert orderings[("benchmark_shielded", "hydrogen")] == [nf, nf, nf, nf, nf]

    assert (
        orderings[("factor_scaled", "hydrogen")]
        != orderings[("benchmark_shielded", "hydrogen")]
    ), (
        "the two mechanisms now agree on hydrogen too; the open decision "
        "recorded in regulatory_constants.EU_CBAM_DEFAULT_MECHANISM may be "
        "fully resolvable"
    )


# ---------------------------------------------------------------------------
# Competitiveness burden
# ---------------------------------------------------------------------------


def test_competitiveness_burden_hand_calculation():
    """Ammonia, Halifax-Hamburg, 2026, medium, cbam_default.

    Re-derived for the "benchmark_shielded" default adopted 7 August 2026.

        embedded 1.98, fertiliser default-value mark-up 1%  -> 1.9998
        chargeable = max(0, 1.9998 - 1.522 x (1 - 0.025))   -> 0.51585
        CBAM       = 0.51585 x (80.00 - 59.27 Canada origin) -> EUR 10.69/t
        maritime (EU ETS 0.78 + FuelEU 0.24)                 -> EUR  1.02/t
        total EUR 11.71/t over EUR 446.80/t                  -> 2.62%

    Under the previous "factor_scaled" default this row read EUR 2.05/t and
    0.46%. The jump is the mechanism, not an input change: a producer above the
    benchmark pays on its full excess immediately instead of on 2.5% of its
    emissions. The EU corridor needs no currency conversion, so this arm also
    pins that the EUR side is passed through untouched.
    """
    emissions, _, commercial = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)
    burden = outputs.competitiveness_burden(compliance, commercial)
    assert len(burden)

    row = burden[
        (burden["corridor"] == rc.HALIFAX_HAMBURG)
        & (burden["product"] == "ammonia")
        & (burden["year"] == 2026)
    ].iloc[0]
    assert row["production_cost_eur_per_tonne"] == pytest.approx(446.8)
    assert row["compliance_cost_eur_per_tonne"] == pytest.approx(11.71, abs=0.01)
    assert row["burden_share_pct"] == pytest.approx(2.62, abs=0.01)
    assert not row["currency_converted"]


def test_competitiveness_burden_converts_only_the_uk_side():
    """The production cost table is EUR throughout, so the GBP compliance
    figure is the one that moves. Converting the denominator instead would
    change the EU corridor's burden, which must stay untouched."""
    emissions, _, commercial = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)
    burden = outputs.competitiveness_burden(compliance, commercial)

    eu = burden[burden["corridor"] == rc.HALIFAX_HAMBURG]
    uk = burden[burden["corridor"] == rc.NINGBO_FELIXSTOWE]
    assert len(eu) and len(uk)
    assert not eu["currency_converted"].any()
    assert uk["currency_converted"].all()

    # UK 2030 ammonia: GBP 71.07 -> EUR at the 23 July 2026 ECB rate.
    uk_2030 = uk[(uk["product"] == "ammonia") & (uk["year"] == 2030)].iloc[0]
    assert uk_2030["compliance_cost_eur_per_tonne"] == pytest.approx(
        rc.gbp_to_eur(71.07), abs=0.05
    )


def test_competitiveness_excludes_placeholder_cost_terms():
    """Conversion and freight are still placeholders and a declared scope
    boundary, so the denominator must be production cost alone. If they ever
    leak in, ammonia's denominator moves off 446.80 and this fails."""
    emissions, _, commercial = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)
    burden = outputs.competitiveness_burden(compliance, commercial)

    assert (burden["value_basis"] == "production_cost").all()
    eu_ammonia = burden[
        (burden["corridor"] == rc.HALIFAX_HAMBURG) & (burden["product"] == "ammonia")
    ]
    assert set(eu_ammonia["production_cost_eur_per_tonne"].round(2)) == {446.8}


def test_burden_ranking_no_longer_diverges_from_the_absolute_cost_ranking():
    """A finding the 8 August 2026 benchmark correction DESTROYED, kept as a
    guard so it cannot be requoted and so its return would be caught.

    The output exists to expose cases where the cheaper corridor per tonne is
    also the MORE exposed one relative to what the product costs to make.
    Reporting only absolute cost would then state the asymmetry backwards. That
    divergence has been claimed at two different places in this project:

      1. Under "factor_scaled", at hydrogen 2030 (63.45% against 43.12%).
      2. Under "benchmark_shielded" with the ETS benchmark wrongly netted off,
         at hydrogen 2027 (27.37% against 20.52%).

    Neither survives. With the CBAM benchmark from IR 2025/2620, Ningbo-
    Felixstowe is both the cheaper corridor and the less exposed one in every
    product-year, so the two rankings agree everywhere and there is no
    divergence to report. The README section claiming otherwise is superseded.

    This is a real loss to the discussion chapter, so it is asserted explicitly
    rather than left to a deleted test.
    """
    emissions, _, commercial = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)

    comparison = outputs.corridor_cost_comparison(compliance)
    asymmetry = outputs.competitiveness_asymmetry(compliance, commercial)
    merged = asymmetry.merge(
        comparison[["product", "year", "cheaper_corridor"]], on=["product", "year"]
    )
    assert len(merged)

    diverging = merged[merged["cheaper_corridor"] == merged["more_exposed_corridor"]]
    assert diverging.empty, (
        "the burden and absolute rankings have diverged again at "
        f"{diverging[['product', 'year']].values.tolist()}; the competitiveness "
        "section of the README needs rewriting to report it"
    )

    # Hydrogen 2027, the row the superseded finding rested on. Ningbo-Felixstowe
    # is now cheaper in absolute terms AND less exposed, so it points one way.
    h27 = merged[(merged["product"] == "hydrogen") & (merged["year"] == 2027)].iloc[0]
    assert h27["cheaper_corridor"] == rc.NINGBO_FELIXSTOWE
    assert h27["more_exposed_corridor"] == rc.HALIFAX_HAMBURG
    assert h27["halifax_hamburg_burden_pct"] == pytest.approx(40.38, abs=0.05)
    assert h27["ningbo_felixstowe_burden_pct"] == pytest.approx(20.52, abs=0.05)


def test_the_marginal_burden_band_still_works_but_no_longer_fires():
    """A finding the 7 August 2026 mechanism switch DESTROYED, kept as a guard.

    Under "factor_scaled" hydrogen 2029 split the two corridors by 0.04
    percentage points on a base of about 29%, and the marginal band was what
    stopped that reading as a direction. Under "benchmark_shielded" that row is
    a 39.96 point gap, and no row anywhere in the matrix now lands inside the
    10% relative band. The near-tie result is gone and must not be quoted from
    the old outputs.

    The band itself still has to work, because the failure mode it guards
    against (reporting a coin-flip as a direction) is documented in this
    project for green ammonia. So this test now checks the mechanism directly
    and pins that nothing currently trips it, with the closest row named. If a
    future input change produces a near-tie again, `closest` moves and this
    fails, which is the prompt to re-examine it.
    """
    emissions, _, commercial = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)
    asymmetry = outputs.competitiveness_asymmetry(compliance, commercial)
    assert len(asymmetry)

    # The band is still applied to every row, and nothing trips it.
    assert set(asymmetry["asymmetry_verdict"]) == {"clear"}
    assert (asymmetry["relative_margin_pct"] > outputs.MARGINAL_VERDICT_BAND_PCT).all()

    # The nearest thing to a tie is ammonia 2026 at 2.61 points, which is a
    # 198% relative margin and nowhere near marginal.
    closest = asymmetry.loc[asymmetry["gap_percentage_points"].abs().idxmin()]
    assert closest["product"] == "ammonia"
    assert closest["year"] == 2026
    assert abs(closest["gap_percentage_points"]) == pytest.approx(2.61, abs=0.05)

    # The superseded row, asserted so the old 0.04 figure cannot be requoted.
    # It read 39.96 between 7 and 8 August 2026 and 58.96 after the benchmark
    # correction; neither is a near-tie, which is the point.
    stale = asymmetry[
        (asymmetry["product"] == "hydrogen") & (asymmetry["year"] == 2029)
    ].iloc[0]
    assert abs(stale["gap_percentage_points"]) == pytest.approx(58.96, abs=0.05)


# ---------------------------------------------------------------------------
# DESNZ UK price path
# ---------------------------------------------------------------------------


def test_desnz_price_series_matches_the_published_table():
    """DESNZ, Traded carbon values used for modelling purposes, 2025,
    published 3 February 2026. GBP/tCO2e in real 2025 prices."""
    expected = {
        2026: (22.0, 38.0, 47.0),
        2027: (23.0, 41.0, 52.0),
        2028: (23.0, 40.0, 54.0),
        2029: (22.0, 43.0, 58.0),
        2030: (25.0, 50.0, 66.0),
    }
    for year, (low, medium, high) in expected.items():
        assert rc.uk_ets_price(year, "low", "desnz") == pytest.approx(low)
        assert rc.uk_ets_price(year, "medium", "desnz") == pytest.approx(medium)
        assert rc.uk_ets_price(year, "high", "desnz") == pytest.approx(high)


def test_desnz_metadata_flags_travel_with_the_series():
    """The series is in real 2025 prices while every other price in the module
    is nominal, it is not a forecast, and it excludes EU linking. Any of those
    silently dropped would let a figure be quoted on the wrong basis."""
    assert rc.UK_ETS_PRICE_DESNZ_PRICE_BASE_YEAR == 2025
    assert rc.UK_ETS_PRICE_DESNZ_IS_FORECAST is False
    assert rc.UK_ETS_PRICE_DESNZ_INCLUDES_EU_LINKING is False
    assert "desnz" in rc.UK_ETS_PRICE_VARIANTS


def test_desnz_clamps_rather_than_extrapolating_outside_the_published_range():
    """Only 2026-2030 has been read out of the publication. A year beyond that
    must reuse the endpoint, not invent a trend."""
    assert rc.uk_ets_price(2031, "medium", "desnz") == pytest.approx(
        rc.uk_ets_price(2030, "medium", "desnz")
    )
    assert rc.uk_ets_price(2025, "medium", "desnz") == pytest.approx(
        rc.uk_ets_price(2026, "medium", "desnz")
    )


def test_desnz_2026_sits_below_the_official_determination():
    """GBP 38 against GBP 49.41. Not rival estimates of one quantity: 49.41 is
    a backward-looking average of actual UKA futures settlements, 38 is a
    forward policy-appraisal scenario in real terms. The gap is the point, and
    it brackets how far the UK price assumption can move the comparison."""
    assert rc.uk_ets_price(2026, "medium", "desnz") < rc.UK_ETS_PRICE_2026_OFFICIAL


def test_analysis_reads_every_uk_price_variant_not_just_frozen():
    """Regression guard. The base-case filter used to hard-pin "frozen", so a
    compliance frame built on any other path came back empty, which reads as
    "no data" rather than as a filter bug.

    Covers every function whose base-case filter reads `uk_price_variant`, not
    just `corridor_cost_comparison`. Checking only that one is what let
    `competitiveness_asymmetry` ship with no `uk_price_variant` parameter at
    all: it dropped every UK row on a non-frozen frame and then raised
    `KeyError: 'product'` out of its own sort, which is a worse failure than
    the empty frame this test was written to catch.
    """
    emissions, _, commercial = data_io.load_inputs()
    for variant in rc.UK_ETS_PRICE_VARIANTS:
        compliance = runner.run_compliance_matrix(
            emissions, uk_price_variant=variant
        )
        for name, frame in (
            (
                "corridor_cost_comparison",
                outputs.corridor_cost_comparison(compliance, uk_price_variant=variant),
            ),
            (
                "corridor_crossover_year",
                outputs.corridor_crossover_year(compliance, uk_price_variant=variant),
            ),
            (
                "corridor_lock_in",
                outputs.corridor_lock_in(compliance, uk_price_variant=variant),
            ),
            (
                "switching_cost_sensitivity",
                outputs.switching_cost_sensitivity(
                    compliance, uk_price_variant=variant
                ),
            ),
            (
                "competitiveness_burden",
                outputs.competitiveness_burden(
                    compliance, commercial, uk_price_variant=variant
                ),
            ),
            (
                "competitiveness_asymmetry",
                outputs.competitiveness_asymmetry(
                    compliance, commercial, uk_price_variant=variant
                ),
            ),
        ):
            assert len(frame), f"{name} came back empty on the {variant} path"


def test_competitiveness_asymmetry_covers_both_corridors_on_every_price_path():
    """The specific failure above: only the EU corridor survived the filter.

    The EU rows pass `_base_case_mask` on its "n/a" arm whatever the variant,
    so a mismatched filter drops the UK side alone. That leaves a frame that
    looks populated on the burden side but has no corridor pair to compare, so
    the asymmetry is not merely wrong, it cannot be computed at all.
    """
    emissions, _, commercial = data_io.load_inputs()
    for variant in rc.UK_ETS_PRICE_VARIANTS:
        compliance = runner.run_compliance_matrix(
            emissions, uk_price_variant=variant
        )
        burden = outputs.competitiveness_burden(
            compliance, commercial, uk_price_variant=variant
        )
        assert set(burden["corridor"].unique()) == set(rc.CORRIDORS), variant

        asymmetry = outputs.competitiveness_asymmetry(
            compliance, commercial, uk_price_variant=variant
        )
        assert set(asymmetry["product"].unique()) == set(rc.PRODUCTS), variant


def test_analysis_returns_an_empty_frame_rather_than_raising():
    """A filter that matches nothing must return an empty frame, not blow up.

    Every reporting function in `analysis.outputs` is called behind a
    `if len(...)` guard in `write_all` and behind `.empty` checks in the
    dashboard, so returning an empty frame is the contract. Raising instead
    takes down the whole output run over one unmatched filter.
    """
    emissions, _, commercial = data_io.load_inputs()
    compliance = runner.run_compliance_matrix(emissions)
    # A pathway that exists on neither corridor: matches no rows anywhere.
    for name, frame in (
        (
            "corridor_cost_comparison",
            outputs.corridor_cost_comparison(compliance, pathway="does_not_exist"),
        ),
        (
            "competitiveness_burden",
            outputs.competitiveness_burden(
                compliance, commercial, pathway="does_not_exist"
            ),
        ),
        (
            "competitiveness_asymmetry",
            outputs.competitiveness_asymmetry(
                compliance, commercial, pathway="does_not_exist"
            ),
        ),
        (
            "corridor_lock_in",
            outputs.corridor_lock_in(compliance, pathway="does_not_exist"),
        ),
    ):
        assert isinstance(frame, pd.DataFrame), name
        assert frame.empty, name


def test_every_corridor_ordering_starts_with_the_uk_cbam_gap():
    """The one part of the corridor finding that no assumption moves.

    Ningbo-Felixstowe is cheaper in 2026 on every product and every UK price
    path, because UK CBAM does not exist that year. That much is regulatory
    timing and holds unconditionally.

    What happens in 2027 is NOT unconditional, and this test used to assert that
    it was. Until the 8 August 2026 benchmark correction every product and path
    handed the lead to Halifax-Hamburg in 2027. With the CBAM benchmark from
    IR 2025/2620, hydrogen keeps Ningbo-Felixstowe in 2027 on the frozen and
    DESNZ paths, so only ammonia still turns over when UK CBAM starts.
    """
    emissions, _, _ = data_io.load_inputs()
    for variant in rc.UK_ETS_PRICE_VARIANTS:
        compliance = runner.run_compliance_matrix(
            emissions, uk_price_variant=variant
        )
        comparison = outputs.corridor_cost_comparison(
            compliance, uk_price_variant=variant
        )
        for product in rc.PRODUCTS:
            rows = comparison[comparison["product"] == product].sort_values("year")
            ordering = dict(zip(rows["year"], rows["cheaper_corridor"], strict=False))
            assert ordering[2026] == rc.NINGBO_FELIXSTOWE, f"{variant}/{product}"

        ammonia = comparison[comparison["product"] == "ammonia"].sort_values("year")
        assert (
            dict(zip(ammonia["year"], ammonia["cheaper_corridor"], strict=False))[2027]
            == rc.HALIFAX_HAMBURG
        ), variant


def test_only_ammonias_corridor_ordering_survives_all_three_uk_price_paths():
    """After 2027 the two products stop behaving the same way.

    This test has been rewritten twice, and both superseded versions are quoted
    in documents written before 8 August 2026:

      1. Originally: Halifax-Hamburg cheaper from 2027 on both products and all
         three paths, quoted in the README as a robustness result.
      2. After the 7 August mechanism switch: hydrogen read NF, HH, NF, NF, NF
         on frozen and DESNZ, described as a flip out and back.

    Correcting the benchmark to the CBAM benchmark required by IR 2025/2620
    (hydrogen 5.089, not the EU ETS 7.98) gives the current picture:

      ammonia   NF, HH, HH, HH, HH   on all three paths
      hydrogen  NF, NF, NF, NF, NF   on frozen and desnz
                NF, HH, HH, HH, HH   on linked

    The smaller shield raises EU hydrogen liability enough that Halifax-Hamburg
    never takes the lead at all, unless the UK price is itself rising, which is
    what the linkage path does. There is no longer a flip out and back; there is
    simply no crossover on the baseline path.

    So ammonia's ordering is robust to the price assumption and hydrogen's is
    not. Any hydrogen corridor claim must name the price path it is on, and note
    that the linkage path is explicitly not law.
    """
    emissions, _, _ = data_io.load_inputs()
    hh, nf = rc.HALIFAX_HAMBURG, rc.NINGBO_FELIXSTOWE

    expected = {
        ("frozen", "ammonia"): [nf, hh, hh, hh, hh],
        ("linked", "ammonia"): [nf, hh, hh, hh, hh],
        ("desnz", "ammonia"): [nf, hh, hh, hh, hh],
        ("frozen", "hydrogen"): [nf, nf, nf, nf, nf],
        ("linked", "hydrogen"): [nf, hh, hh, hh, hh],
        ("desnz", "hydrogen"): [nf, nf, nf, nf, nf],
    }

    for variant in rc.UK_ETS_PRICE_VARIANTS:
        compliance = runner.run_compliance_matrix(
            emissions, uk_price_variant=variant
        )
        comparison = outputs.corridor_cost_comparison(
            compliance, uk_price_variant=variant
        )
        for product in rc.PRODUCTS:
            rows = comparison[comparison["product"] == product].sort_values("year")
            got = list(rows["cheaper_corridor"])
            assert got == expected[(variant, product)], f"{variant}/{product}"

    # And the claim the README now makes, stated directly rather than inferred:
    # ammonia agrees across every path, hydrogen does not.
    ammonia_orderings = {
        tuple(expected[(v, "ammonia")]) for v in rc.UK_ETS_PRICE_VARIANTS
    }
    hydrogen_orderings = {
        tuple(expected[(v, "hydrogen")]) for v in rc.UK_ETS_PRICE_VARIANTS
    }
    assert len(ammonia_orderings) == 1, "ammonia should be price-path robust"
    assert len(hydrogen_orderings) > 1, "hydrogen should not be price-path robust"


# ---------------------------------------------------------------------------
# Policy events table
# ---------------------------------------------------------------------------


def test_policy_events_table_loads_and_validates_its_vocabularies():
    """Unknown instrument types or statuses must fail loudly. The whole point
    of classifying by instrument is that "act of parliament" and "consultation
    that closed with no decision" carry very different weight, and a typo that
    silently created a new category would erase that distinction."""
    events = data_io.load_policy_events()
    assert len(events) >= 40
    assert set(events["jurisdiction"]) == {"canada", "uk", "eu", "china"}
    assert set(events["instrument_type"]) <= set(
        data_io.POLICY_EVENT_INSTRUMENT_TYPES
    )
    assert set(events["status"]) <= set(data_io.POLICY_EVENT_STATUSES)
    assert set(events["affects_model"]) <= set(data_io.POLICY_EVENT_AFFECTS_MODEL)


def test_every_policy_event_names_a_parameter_that_actually_exists():
    """The timeline is only useful if its `model_parameter` column points at
    something real. A stale name here means the event silently stops being
    traceable into the model, which is exactly the drift this column exists to
    prevent."""
    from cbam_model.config import regulatory_constants as rc

    events = data_io.load_policy_events()
    # Two values name input-table columns rather than module constants.
    data_columns = {"cbam_default", "production_cost_eur_per_tonne"}

    unresolved = [
        p
        for p in sorted(set(events["model_parameter"]) - {""})
        if p not in data_columns and not hasattr(rc, p)
    ]
    assert not unresolved, f"policy_events.csv names missing constants: {unresolved}"


def test_policy_timeline_agrees_with_the_model_on_the_quantified_events():
    """Cross-check the numbers Alex's timeline states against what the model
    actually implements. These are the rows where the timeline and the code
    make the same claim, so a disagreement means one of them is wrong."""
    from cbam_model.config import regulatory_constants as rc

    events = data_io.load_policy_events().set_index("event_id")

    # CA-08: revised Canadian industrial price path.
    assert "CAD 95 (2026)" in events.loc["CA-08", "quantified_effect"]
    assert rc.origin_carbon_price_canada_cad(2026) == pytest.approx(95.0)
    assert rc.origin_carbon_price_canada_cad(2030) == pytest.approx(115.0)

    # EU-10 / EU-14 / EU-15: the CBAM factor ramp.
    assert rc.cbam_factor(2026) == pytest.approx(0.025)
    assert rc.cbam_factor(2030) == pytest.approx(0.485)
    assert rc.cbam_factor(2034) == pytest.approx(1.0)

    # EU-13: the benchmarks sourced from IR 2026/1412.
    assert rc.EU_ETS_PRODUCT_BENCHMARK_TCO2E_PER_TONNE["ammonia"] == pytest.approx(1.522)
    assert rc.EU_ETS_PRODUCT_BENCHMARK_TCO2E_PER_TONNE["hydrogen"] == pytest.approx(7.98)

    # UK-15: the international ocean leg is not covered by UK ETS.
    assert rc.UK_ETS_INTL_VOYAGE_COVERAGE == pytest.approx(0.0)

    # UK-12 / UK-14: the proposed expansion, still not law.
    assert rc.UK_ETS_INTL_EXPANSION_PROPOSED == pytest.approx(0.50)
    assert rc.UK_ETS_INTL_EXPANSION_EARLIEST_YEAR == 2028
    assert rc.UK_ETS_INTL_EXPANSION_IS_LAW is False

    # UK-16: UK CBAM starts in 2027.
    assert rc.UK_CBAM_START_YEAR == 2027


def test_superseded_policies_are_not_the_ones_driving_the_model():
    """The Canadian 170-by-2030 plan is superseded and must never be the live
    input. It stays in the table because it is a legitimate upper bound for an
    accelerated scenario, which is a different thing from being the baseline."""
    from cbam_model.config import regulatory_constants as rc

    events = data_io.load_policy_events().set_index("event_id")
    assert events.loc["CA-03", "status"] == "superseded"
    assert events.loc["CA-03", "affects_model"] == "sensitivity_only"
    assert events.loc["CA-08", "status"] == "in_force"

    # The live path tops out at 115 in 2030, not 170.
    assert rc.origin_carbon_price_canada_cad(2030) < 170.0


def test_uk_cbam_indirect_emissions_gap_is_recorded_as_unimplemented():
    """UK CBAM charges direct emissions only until 2029 at the earliest, and
    the model does not represent that: it applies the full embedded figure on
    the UK corridor in 2027 and 2028, overstating liability in exactly the two
    years the lock-in reversal turns on.

    The direct-only limitation is policy delivered through secondary
    legislation, not a restriction in the Finance Act 2026, whose s.148 defines
    embodied emissions broadly and lets the Treasury narrow it by regulation.
    Do not cite the Act for it. See docs/policy_timeline_gaps.md.

    This test does not assert the model is right. It asserts the gap is written
    down, so it cannot be forgotten before submission."""
    events = data_io.load_policy_events().set_index("event_id")
    row = events.loc["UK-16"]
    assert "Direct emissions only" in row["quantified_effect"]
    assert "NOT YET IMPLEMENTED" in row["why_it_matters"]


# ---------------------------------------------------------------------------
# Scenario labelling
# ---------------------------------------------------------------------------
# Added 7 August 2026. Every other test here checks that a number is right.
# These check that the number is presented under the right name, which this
# project treats as the same class of error: two of the three UK price paths
# and one of the two UK ETS scope variants are explicitly not law, so a
# mislabelled figure is a policy-uncertain what-if quoted as a legislated
# result.


def test_every_uk_price_variant_has_its_own_label():
    """Regression test for a real mislabelling bug, fixed 7 August 2026.

    The dashboard built its UK carbon price selector by branching
    `if v == "frozen" ... else <linkage label>`. That was correct while there
    were two variants. When "desnz" was added on 6 August 2026 it fell into the
    else arm, so the selector showed DESNZ prices captioned as the EU-UK
    linkage scenario, and the caption underneath claimed the price was frozen
    at the 2026 determination when it was not.

    Nothing failed. The numbers were the right DESNZ numbers, carrying the
    wrong scenario's name, which is the hardest kind of error to catch by
    reading the screen. This test fails the moment a fourth variant is added
    without a label of its own.
    """
    labels = scenarios.UK_PRICE_VARIANT_LABELS

    assert set(labels) == set(rc.UK_ETS_PRICE_VARIANTS), (
        "every UK price variant needs its own label; missing "
        f"{sorted(set(rc.UK_ETS_PRICE_VARIANTS) - set(labels))}"
    )

    # Distinctness is the actual invariant. A dict can cover every variant and
    # still be wrong if two of them share a label, which is exactly what the
    # if/else did.
    assert len(set(labels.values())) == len(labels), (
        f"two UK price variants share a label: {sorted(labels.values())}"
    )

    # The linkage path is not law, and its label is the only place a reader of
    # the dashboard is told so.
    assert not rc.UK_ETS_LINKAGE_IS_LAW
    assert "NOT law" in labels["linked"], (
        "the linked label must say it is not law: UK_ETS_LINKAGE_IS_LAW is "
        "False, the agreement was never confirmed, and a linkage figure shown "
        "without that caveat reads as a legislated price path"
    )

    # DESNZ is official but in real 2025 prices while every other price in the
    # model is nominal, so its label has to carry that or the two read as
    # directly comparable when they are not.
    assert rc.UK_ETS_PRICE_DESNZ_PRICE_BASE_YEAR == 2025
    assert "real" in labels["desnz"].lower(), (
        "the desnz label must say the series is in real 2025 prices; every "
        "other price in the model is nominal, so without it the DESNZ path "
        "looks like a like-for-like alternative to the frozen baseline"
    )


def test_every_uk_ets_scope_variant_has_its_own_label():
    """Same invariant on the other variant axis, which has the same exposure.

    `proposed_expansion` is the UK ETS extension to international voyages. The
    consultation closed in January 2026 with no legislative decision, so it may
    only ever appear captioned as policy-uncertain.
    """
    labels = scenarios.VARIANT_LABELS

    assert set(labels) == set(scenarios.UK_ETS_VARIANTS), (
        "every UK ETS scope variant needs its own label; missing "
        f"{sorted(set(scenarios.UK_ETS_VARIANTS) - set(labels))}"
    )
    assert len(set(labels.values())) == len(labels), (
        f"two UK ETS scope variants share a label: {sorted(labels.values())}"
    )

    assert not rc.UK_ETS_INTL_EXPANSION_IS_LAW
    assert "NOT LAW" in labels["proposed_expansion"], (
        "the proposed-expansion label must say it is not law: the consultation "
        "closed in January 2026 with no legislative decision, and this variant "
        "roughly doubles the UK corridor's maritime cost where it applies"
    )
