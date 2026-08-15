"""Tests for the per-market sourcing allocation LP.

Three groups matter here.

The first pins the two modelling errors this module was rebuilt to fix, so
neither can return: solving across corridors that serve different countries,
and treating a declaration treatment as a production pathway.

The second checks the solution is a solution.

The third guards the honesty of the claims. This formulation is a fractional
knapsack dressed as an LP, and with two pathways it has no freedom at all, so
there are tests asserting the module says so rather than letting a reader
assume more.
"""

import numpy as np
import pandas as pd
import pytest

from cbam_model.config import regulatory_constants as rc
from cbam_model.optimisation import allocation as al

DEMAND = 1_000_000.0
EU = rc.HALIFAX_HAMBURG
UK = rc.NINGBO_FELIXSTOWE


@pytest.fixture(scope="module")
def eu_ammonia():
    return al.build_options("ammonia", 2030, "medium", EU)


@pytest.fixture(scope="module")
def uk_ammonia():
    return al.build_options("ammonia", 2030, "medium", UK)


@pytest.fixture(scope="module")
def eu_hydrogen():
    return al.build_options("hydrogen", 2030, "medium", EU)


# ---------------------------------------------------------------------------
# The two errors this module was rebuilt to fix
# ---------------------------------------------------------------------------


def test_a_solve_never_spans_two_destination_markets(eu_ammonia, uk_ammonia):
    """The original error. Hamburg and Felixstowe are not substitutable.

    A single option set must contain exactly one corridor, because allocating
    demand between them describes a choice no buyer has.
    """
    for options in (eu_ammonia, uk_ammonia):
        corridors = {route.split(" / ")[0] for route in options.index}
        assert len(corridors) == 1


def test_corridor_is_required_and_validated():
    with pytest.raises(TypeError):
        al.build_options("ammonia", 2030, "medium")
    with pytest.raises(ValueError, match="Unknown corridor"):
        al.build_options("ammonia", 2030, "medium", "rotterdam_felixstowe")


def test_cbam_default_is_not_a_decision_variable(eu_ammonia, uk_ammonia, eu_hydrogen):
    """It is a declaration treatment, not a production method.

    Its production cost is identical to the fossil pathway's on every corridor,
    because it is the same physical supply declared without verified data.
    Allocating volume to it split one supplier in two and called it sourcing.
    """
    for options in (eu_ammonia, uk_ammonia, eu_hydrogen):
        pathways = {route.split(" / ")[1] for route in options.index}
        assert "cbam_default" not in pathways


def test_the_declaration_incentive_this_exclusion_exposed():
    """The default is more favourable than verified reality on both corridors.

    Pinned because it is a finding for the discussion chapter, and because it
    is the evidence that `cbam_default` is an accounting choice rather than a
    physical route: an exporter would rationally never verify.
    """
    full = al.runner.run_compliance_matrix()
    rows = full[(full["product"] == "ammonia") & (full["year"] == 2030)]
    for corridor, fossil in ((EU, "grey_smr"), (UK, "coal_gasification")):
        here = rows[rows["corridor"] == corridor]
        default_e = here[here["pathway"] == "cbam_default"]["embedded_emissions_tco2e_per_tonne"]
        actual_e = here[here["pathway"] == fossil]["embedded_emissions_tco2e_per_tonne"]
        assert default_e.iloc[0] < actual_e.iloc[0], corridor


# ---------------------------------------------------------------------------
# The solution is a solution
# ---------------------------------------------------------------------------


def test_demand_is_met_exactly(eu_ammonia):
    res = al.solve_allocation(eu_ammonia, DEMAND)
    assert res.allocation.sum() == pytest.approx(DEMAND)


def test_no_pathway_exceeds_its_capacity(eu_hydrogen):
    caps = al.CapacityAssumptions(per_route_share_of_demand=0.4)
    res = al.solve_allocation(eu_hydrogen, DEMAND, caps)
    assert (res.allocation <= 0.4 * DEMAND + 1e-6).all()


def test_allocation_is_non_negative(eu_ammonia):
    res = al.solve_allocation(eu_ammonia, DEMAND)
    assert (res.allocation >= -1e-9).all()


def test_emissions_ceiling_is_respected(eu_hydrogen):
    cap = al.unconstrained_emissions(eu_hydrogen, DEMAND) * 0.8
    res = al.solve_allocation(eu_hydrogen, DEMAND, emissions_cap_tco2e=cap)
    assert res.total_emissions_tco2e <= cap + 1e-6


def test_capacities_too_small_to_meet_demand_raise(eu_ammonia):
    caps = al.CapacityAssumptions(per_route_share_of_demand=0.01)
    with pytest.raises(ValueError, match="no allocation can meet demand"):
        al.solve_allocation(eu_ammonia, DEMAND, caps)


def test_impossible_emissions_ceiling_raises(eu_ammonia):
    with pytest.raises(ValueError, match="No feasible allocation"):
        al.solve_allocation(eu_ammonia, DEMAND, emissions_cap_tco2e=1.0)


# ---------------------------------------------------------------------------
# The shadow price, and what it really is
# ---------------------------------------------------------------------------


def test_shadow_price_equals_the_hand_calculated_abatement_cost(eu_ammonia):
    """With two pathways there is exactly one substitution available.

    The dual must therefore equal the cost of that swap divided by the CO2e it
    saves, computed independently here. Agreement is a check on the solver and
    a demonstration of the module's own caveat: where only one substitution
    exists, the "optimisation" is arithmetic and the shadow price is simply
    that swap's price.
    """
    grey, green = f"{EU} / grey_smr", f"{EU} / green_electrolysis"
    delta_cost = (
        eu_ammonia.loc[green, "cost_eur_per_tonne"] - eu_ammonia.loc[grey, "cost_eur_per_tonne"]
    )
    delta_emissions = (
        eu_ammonia.loc[grey, "emissions_tco2e_per_tonne"]
        - eu_ammonia.loc[green, "emissions_tco2e_per_tonne"]
    )
    analytical = delta_cost / delta_emissions

    cap = al.unconstrained_emissions(eu_ammonia, DEMAND) * 0.9
    res = al.solve_allocation(eu_ammonia, DEMAND, emissions_cap_tco2e=cap)
    assert res.emissions_shadow_price_eur_per_tco2e == pytest.approx(analytical, rel=1e-6)


def test_shadow_price_is_zero_when_the_ceiling_does_not_bind(eu_ammonia):
    slack = al.unconstrained_emissions(eu_ammonia, DEMAND) * 1.5
    res = al.solve_allocation(eu_ammonia, DEMAND, emissions_cap_tco2e=slack)
    assert res.emissions_shadow_price_eur_per_tco2e == pytest.approx(0.0, abs=1e-6)
    assert not res.emissions_cap_binds()


def test_shadow_price_is_reported_as_a_cost_not_a_negative_dual(eu_hydrogen):
    """A negative shadow price here would read as a subsidy for emitting."""
    cap = al.unconstrained_emissions(eu_hydrogen, DEMAND) * 0.8
    res = al.solve_allocation(eu_hydrogen, DEMAND, emissions_cap_tco2e=cap)
    assert res.emissions_shadow_price_eur_per_tco2e > 0


def test_tightening_the_ceiling_never_reduces_cost(eu_hydrogen):
    sweep = al.cap_sweep(eu_hydrogen, DEMAND)
    feasible = sweep[sweep["feasible"]].sort_values("cap_fraction", ascending=False)
    costs = feasible["cost_per_tonne_eur"].to_numpy()
    assert np.all(np.diff(costs) >= -1e-6)


# ---------------------------------------------------------------------------
# Comparing markets, which is the only defensible corridor comparison here
# ---------------------------------------------------------------------------


def test_market_comparison_solves_each_market_independently():
    table = al.market_comparison("ammonia", 2030, DEMAND)
    assert list(table["corridor"]) == list(rc.CORRIDORS)
    assert set(table["regime"]) == {"EU", "UK"}


def test_both_markets_receive_the_same_proportional_cut():
    """Otherwise the shadow prices are not comparable and the table lies."""
    table = al.market_comparison("ammonia", 2030, DEMAND, cut_fraction=0.3)
    assert table.attrs["cut_was_limited"]
    assert table.attrs["applied_cut"] < 0.3
    assert table.attrs["applied_cut"] > 0


def test_a_deep_cut_is_clamped_rather_than_failing():
    """Two pathways under a capacity limit cannot cut far, and that is a fact
    about the supply base worth surfacing rather than an error to raise."""
    table = al.market_comparison("ammonia", 2030, DEMAND, cut_fraction=0.9)
    assert table["shadow_price_eur_per_tco2e"].notna().all()


def test_abatement_is_far_cheaper_on_the_dirtier_corridor():
    """The headline finding of the rebuilt module.

    Chinese coal ammonia is so carbon-intensive that switching it to green
    saves 5.33 tCO2e per tonne against 1.56 on the Canadian route, so the same
    proportional cut costs an EU importer several times more per tonne of CO2.
    Counterintuitive only until you notice that a cleaner baseline leaves less
    to abate.
    """
    table = al.market_comparison("ammonia", 2030, DEMAND).set_index("corridor")
    eu = table.loc[EU, "shadow_price_eur_per_tco2e"]
    uk = table.loc[UK, "shadow_price_eur_per_tco2e"]
    assert eu > uk * 3


def test_ammonia_markets_are_flagged_as_having_no_freedom():
    """Two pathways means demand and the ceiling pin the answer exactly."""
    table = al.market_comparison("ammonia", 2030, DEMAND)
    assert table["allocation_is_determined"].all()
    assert table.attrs["any_market_determined"]


def test_hydrogen_markets_have_a_genuine_choice():
    table = al.market_comparison("hydrogen", 2030, DEMAND)
    assert not table["allocation_is_determined"].any()
    assert (table["pathways_available"] == 3).all()


# ---------------------------------------------------------------------------
# The confound that produced a wrong answer, pinned so it cannot return
# ---------------------------------------------------------------------------


def test_cost_rises_with_the_carbon_price(eu_ammonia):
    """Regression test on a bug found 13 August 2026.

    `price_scenario_comparison` originally set the emissions ceiling to a
    fraction of each scenario's own unconstrained optimum, so the ceiling moved
    with the price and the comparison changed two things at once. It reported
    cost falling as carbon got more expensive, which is impossible.
    """
    for product in ("ammonia", "hydrogen"):
        for corridor in rc.CORRIDORS:
            table = al.price_scenario_comparison(
                product, 2030, DEMAND, corridor, cap_fraction=0.85
            )
            values = table["cost_per_tonne_eur"].to_numpy()
            assert np.all(np.diff(values) > 0), f"{product} on {corridor}"


# ---------------------------------------------------------------------------
# Claims the module makes about itself
# ---------------------------------------------------------------------------


def test_without_a_ceiling_the_answer_is_just_a_merit_order_fill(eu_hydrogen):
    """Greedy over pathways solves it, which is why the ceiling is not optional."""
    caps = al.CapacityAssumptions()
    res = al.solve_allocation(eu_hydrogen, DEMAND, caps)

    remaining, greedy = DEMAND, {}
    for route in eu_hydrogen.sort_values("cost_eur_per_tonne").index:
        take = min(caps.limit_for(route, DEMAND), remaining)
        greedy[route] = take
        remaining -= take
        if remaining <= 1e-9:
            break

    expected = pd.Series(greedy).reindex(eu_hydrogen.index).fillna(0.0)
    assert res.allocation.round(3).equals(expected.round(3))


def test_a_binding_ceiling_beats_the_merit_order(eu_hydrogen):
    caps = al.CapacityAssumptions()
    unconstrained = al.solve_allocation(eu_hydrogen, DEMAND, caps)
    cap = unconstrained.total_emissions_tco2e * 0.8
    constrained = al.solve_allocation(eu_hydrogen, DEMAND, caps, emissions_cap_tco2e=cap)

    assert not constrained.allocation.round(3).equals(unconstrained.allocation.round(3))
    assert constrained.cost_per_tonne_eur > unconstrained.cost_per_tonne_eur


def test_costs_combine_production_and_compliance_only(eu_ammonia):
    """Conversion and freight are PLACEHOLDER and must stay out of the objective."""
    combined = (
        eu_ammonia["production_eur_per_tonne"] + eu_ammonia["compliance_eur_per_tonne"]
    )
    assert np.allclose(combined, eu_ammonia["cost_eur_per_tonne"])


def test_uk_market_is_solved_in_euros(uk_ammonia):
    """One market, one currency, because production cost is only published in EUR."""
    assert (uk_ammonia["cost_eur_per_tonne"] > 0).all()
    assert (uk_ammonia["compliance_eur_per_tonne"] > 0).all()


def test_capacity_assumption_changes_the_answer(eu_hydrogen):
    sweep = al.capacity_sensitivity(eu_hydrogen, DEMAND, cap_fraction=0.85)
    assert sweep["cost_per_tonne_eur"].nunique() > 1


def test_min_achievable_emissions_is_below_the_cost_optimum(eu_ammonia):
    floor = al.min_achievable_emissions(eu_ammonia, DEMAND)
    cheapest = al.unconstrained_emissions(eu_ammonia, DEMAND)
    assert 0 < floor < cheapest


def test_max_feasible_cut_is_the_boundary_of_feasibility(eu_ammonia):
    deepest = al.max_feasible_cut(eu_ammonia, DEMAND)
    assert 0 < deepest < 1
    baseline = al.unconstrained_emissions(eu_ammonia, DEMAND)
    al.solve_allocation(eu_ammonia, DEMAND, emissions_cap_tco2e=baseline * (1 - deepest * 0.99))
    with pytest.raises(ValueError, match="No feasible allocation"):
        al.solve_allocation(
            eu_ammonia, DEMAND, emissions_cap_tco2e=baseline * (1 - deepest * 1.01)
        )


# ---------------------------------------------------------------------------
# The verdict text
# ---------------------------------------------------------------------------


def test_read_result_states_the_decision_number_when_the_ceiling_binds(eu_hydrogen):
    cap = al.unconstrained_emissions(eu_hydrogen, DEMAND) * 0.8
    res = al.solve_allocation(eu_hydrogen, DEMAND, emissions_cap_tco2e=cap)
    lines = " ".join(al.read_result(res, eu_hydrogen))
    assert "binding" in lines
    assert f"{res.emissions_shadow_price_eur_per_tco2e:,.2f}" in lines


def test_read_result_says_so_when_the_ceiling_does_nothing(eu_ammonia):
    slack = al.unconstrained_emissions(eu_ammonia, DEMAND) * 1.5
    res = al.solve_allocation(eu_ammonia, DEMAND, emissions_cap_tco2e=slack)
    assert "not binding" in " ".join(al.read_result(res, eu_ammonia))


def test_read_result_admits_when_a_sort_would_do(eu_ammonia):
    res = al.solve_allocation(eu_ammonia, DEMAND)
    assert "sort would produce the same answer" in " ".join(al.read_result(res, eu_ammonia))


def test_read_result_uses_display_labels_when_given_one(eu_ammonia):
    res = al.solve_allocation(eu_ammonia, DEMAND)
    lines = " ".join(al.read_result(res, eu_ammonia, label=lambda r: "PRETTY"))
    assert "PRETTY" in lines
    assert "green_electrolysis" not in lines


def test_cheapest_substitution_matches_the_shadow_price(eu_ammonia):
    """The mechanism behind the comparison, checked against the dual."""
    swap = al.cheapest_substitution(eu_ammonia)
    cap = al.unconstrained_emissions(eu_ammonia, DEMAND) * 0.9
    res = al.solve_allocation(eu_ammonia, DEMAND, emissions_cap_tco2e=cap)
    assert swap["eur_per_tco2e"] == pytest.approx(
        res.emissions_shadow_price_eur_per_tco2e, rel=1e-6
    )


def test_which_market_is_cheaper_to_clean_is_not_a_fixed_story():
    """Guards against asserting a mechanism instead of computing one.

    A first version of the dashboard claimed abatement is always cheaper on the
    dirtier corridor. That holds for ammonia and is false for hydrogen at a
    shallow target, where the UK route's low-carbon alternative carries a large
    enough premium to outweigh the extra CO2e each switched tonne saves.
    """
    ammonia = al.market_comparison("ammonia", 2030, DEMAND, cut_fraction=0.15).set_index("regime")
    hydrogen = al.market_comparison("hydrogen", 2030, DEMAND, cut_fraction=0.15).set_index("regime")
    assert ammonia.loc["UK", "shadow_price_eur_per_tco2e"] < ammonia.loc["EU", "shadow_price_eur_per_tco2e"]
    assert hydrogen.loc["UK", "shadow_price_eur_per_tco2e"] > hydrogen.loc["EU", "shadow_price_eur_per_tco2e"]


def test_the_cheaper_market_to_decarbonise_depends_on_how_deep_the_cut_is():
    """A finding, and a warning against quoting one target as though general.

    For hydrogen at a 15% cut the EU corridor is far cheaper to clean, EUR 4.32
    against 20.95, because a cheap grey-to-blue swap is available. By 30% that
    swap is exhausted, both markets are pushed onto green, and the ranking
    reverses to 292.89 against 283.32.

    Quoting either number alone would be quoting an artefact of the ambition
    level chosen, so the write-up has to name the target it used.
    """
    shallow = al.market_comparison("hydrogen", 2030, DEMAND, cut_fraction=0.15).set_index("regime")
    deep = al.market_comparison("hydrogen", 2030, DEMAND, cut_fraction=0.30).set_index("regime")

    assert shallow.loc["EU", "shadow_price_eur_per_tco2e"] < shallow.loc["UK", "shadow_price_eur_per_tco2e"]
    assert deep.loc["EU", "shadow_price_eur_per_tco2e"] > deep.loc["UK", "shadow_price_eur_per_tco2e"]
    # And the deeper target is far more expensive on both sides.
    for regime in ("EU", "UK"):
        assert deep.loc[regime, "shadow_price_eur_per_tco2e"] > (
            10 * shallow.loc[regime, "shadow_price_eur_per_tco2e"]
        )


def test_capacity_sensitivity_reports_infeasibility_rather_than_raising(eu_ammonia):
    """Two pathways at a 50% limit are pinned exactly, so no cut is possible."""
    sweep = al.capacity_sensitivity(eu_ammonia, DEMAND, cap_fraction=0.85)
    assert not sweep["feasible"].all()
    assert (sweep.loc[~sweep["feasible"], "why"] != "").all()
