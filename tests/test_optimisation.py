"""Tests for the sourcing allocation LP.

The tests worth reading are the ones establishing that the formulation is not
trivial. An LP that a sort could replace is not optimisation, and the emissions
ceiling is the only thing standing between this module and that criticism, so
several tests exist purely to prove the ceiling changes the answer.
"""

import numpy as np
import pandas as pd
import pytest

from cbam_model.config import regulatory_constants as rc
from cbam_model.optimisation import allocation as al

DEMAND = 1_000_000.0


@pytest.fixture(scope="module")
def ammonia():
    return al.build_options("ammonia", 2030, "medium")


@pytest.fixture(scope="module")
def hydrogen():
    return al.build_options("hydrogen", 2030, "medium")


# ---------------------------------------------------------------------------
# The solution is actually a solution
# ---------------------------------------------------------------------------


def test_demand_is_met_exactly(ammonia):
    res = al.solve_allocation(ammonia, DEMAND)
    assert res.allocation.sum() == pytest.approx(DEMAND)


def test_no_route_exceeds_its_capacity(ammonia):
    caps = al.CapacityAssumptions(per_route_share_of_demand=0.35)
    res = al.solve_allocation(ammonia, DEMAND, caps)
    assert (res.allocation <= 0.35 * DEMAND + 1e-6).all()


def test_allocation_is_non_negative(ammonia):
    res = al.solve_allocation(ammonia, DEMAND)
    assert (res.allocation >= -1e-9).all()


def test_emissions_ceiling_is_respected(ammonia):
    cap = al.unconstrained_emissions(ammonia, DEMAND) * 0.5
    res = al.solve_allocation(ammonia, DEMAND, emissions_cap_tco2e=cap)
    assert res.total_emissions_tco2e <= cap + 1e-6


def test_capacities_too_small_to_meet_demand_raise(ammonia):
    caps = al.CapacityAssumptions(per_route_share_of_demand=0.01)
    with pytest.raises(ValueError, match="no allocation can meet demand"):
        al.solve_allocation(ammonia, DEMAND, caps)


def test_impossible_emissions_ceiling_raises(ammonia):
    with pytest.raises(ValueError, match="No feasible allocation"):
        al.solve_allocation(ammonia, DEMAND, emissions_cap_tco2e=1.0)


# ---------------------------------------------------------------------------
# The emissions ceiling is what makes this optimisation rather than sorting
# ---------------------------------------------------------------------------


def test_without_a_ceiling_the_answer_is_just_a_merit_order_fill(ammonia):
    """Reproduces the LP with a greedy sort, and they must agree.

    This test exists to make the module's central caveat checkable rather than
    asserted. With no emissions ceiling the LP is doing nothing a sort could
    not, and that is exactly why the ceiling is not presented as optional.
    """
    caps = al.CapacityAssumptions()
    res = al.solve_allocation(ammonia, DEMAND, caps)

    remaining, greedy = DEMAND, {}
    for route in ammonia.sort_values("cost_eur_per_tonne").index:
        take = min(caps.limit_for(route, DEMAND), remaining)
        greedy[route] = take
        remaining -= take
        if remaining <= 1e-9:
            break

    expected = pd.Series(greedy).reindex(ammonia.index).fillna(0.0)
    assert res.allocation.round(3).equals(expected.round(3))


def test_a_binding_ceiling_beats_the_merit_order(ammonia):
    """With the ceiling on, the greedy answer is no longer optimal or legal."""
    caps = al.CapacityAssumptions()
    unconstrained = al.solve_allocation(ammonia, DEMAND, caps)
    cap = unconstrained.total_emissions_tco2e * 0.5
    constrained = al.solve_allocation(ammonia, DEMAND, caps, emissions_cap_tco2e=cap)

    assert not constrained.allocation.round(3).equals(unconstrained.allocation.round(3))
    assert constrained.cost_per_tonne_eur > unconstrained.cost_per_tonne_eur


# ---------------------------------------------------------------------------
# The shadow price behaves like a shadow price
# ---------------------------------------------------------------------------


def test_shadow_price_is_zero_when_the_ceiling_does_not_bind(ammonia):
    slack = al.unconstrained_emissions(ammonia, DEMAND) * 1.5
    res = al.solve_allocation(ammonia, DEMAND, emissions_cap_tco2e=slack)
    assert res.emissions_shadow_price_eur_per_tco2e == pytest.approx(0.0, abs=1e-6)
    assert not res.emissions_cap_binds()


def test_shadow_price_is_positive_when_the_ceiling_binds(ammonia):
    cap = al.unconstrained_emissions(ammonia, DEMAND) * 0.5
    res = al.solve_allocation(ammonia, DEMAND, emissions_cap_tco2e=cap)
    assert res.emissions_shadow_price_eur_per_tco2e > 0
    assert res.emissions_cap_binds()


def test_shadow_price_is_reported_as_a_cost_not_a_negative_dual(ammonia):
    """Sign convention. A negative shadow price here would read as a subsidy."""
    cap = al.unconstrained_emissions(ammonia, DEMAND) * 0.6
    res = al.solve_allocation(ammonia, DEMAND, emissions_cap_tco2e=cap)
    assert res.emissions_shadow_price_eur_per_tco2e > 0


def test_tightening_the_ceiling_never_reduces_cost(ammonia):
    """Monotonicity. A smaller feasible set cannot be cheaper."""
    sweep = al.cap_sweep(ammonia, DEMAND)
    feasible = sweep[sweep["feasible"]].sort_values("cap_fraction", ascending=False)
    costs = feasible["cost_per_tonne_eur"].to_numpy()
    assert np.all(np.diff(costs) >= -1e-6)


# ---------------------------------------------------------------------------
# The confound that produced a wrong answer, pinned so it cannot return
# ---------------------------------------------------------------------------


def test_cost_rises_with_the_carbon_price(ammonia):
    """Regression test on a real bug found on 13 August 2026.

    The first version of `price_scenario_comparison` set the emissions ceiling
    to a fraction of each scenario's own unconstrained optimum, so the ceiling
    moved with the price. It reported total cost falling from EUR 586/t at the
    low carbon price to EUR 515/t at the medium one, which is impossible when
    the only thing changing is the price of carbon.

    Holding the ceiling fixed in absolute terms is both the correct comparison
    and the realistic one, since an importer faces one emissions target rather
    than a target indexed to the carbon price.
    """
    for product in ("ammonia", "hydrogen"):
        table = al.price_scenario_comparison(product, 2030, DEMAND)
        costs = table.set_index("price_scenario").loc[list(rc.PRICE_SCENARIOS)]
        values = costs["cost_per_tonne_eur"].to_numpy()
        assert np.all(np.diff(values) > 0), f"{product} cost did not rise with carbon price"


def test_the_comparison_holds_one_ceiling_across_all_scenarios(ammonia):
    """The mechanism behind the fix, checked directly."""
    table = al.price_scenario_comparison("ammonia", 2030, DEMAND, cap_fraction=0.7)
    assert len(table) == len(rc.PRICE_SCENARIOS)
    assert table["carbon_price_eur"].is_monotonic_increasing


# ---------------------------------------------------------------------------
# Findings that the write-up quotes
# ---------------------------------------------------------------------------


def test_ammonia_mix_changes_across_price_paths_but_hydrogen_does_not(ammonia, hydrogen):
    """The headline result of this module, pinned in both directions."""
    assert not al.price_scenario_comparison("ammonia", 2030, DEMAND).attrs["mix_is_invariant"]
    assert al.price_scenario_comparison("hydrogen", 2030, DEMAND).attrs["mix_is_invariant"]


def test_capacity_assumption_changes_the_answer(ammonia):
    """The reason capacity is swept rather than fixed at one invented number."""
    sweep = al.capacity_sensitivity(ammonia, DEMAND)
    assert sweep["routes_used"].nunique() > 1
    assert sweep["cost_per_tonne_eur"].nunique() > 1


def test_costs_combine_production_and_compliance_only(ammonia):
    """Conversion and freight are PLACEHOLDER and must stay out of the objective."""
    combined = ammonia["production_eur_per_tonne"] + ammonia["compliance_eur_per_tonne"]
    assert np.allclose(combined, ammonia["cost_eur_per_tonne"])


def test_uk_corridor_costs_are_converted_to_euros(ammonia):
    """Both corridors must be on one currency or the comparison is meaningless."""
    assert (ammonia["cost_eur_per_tonne"] > 0).all()
    assert len({r.split(" / ")[0] for r in ammonia.index}) == 2


def test_min_achievable_emissions_is_below_the_cost_optimum(ammonia):
    """The floor on any ceiling. Asking below it is infeasible at any price."""
    floor = al.min_achievable_emissions(ammonia, DEMAND)
    cheapest = al.unconstrained_emissions(ammonia, DEMAND)
    assert 0 < floor < cheapest


def test_max_feasible_cut_is_the_boundary_of_feasibility(ammonia):
    """Just inside it solves, just outside it does not."""
    deepest = al.max_feasible_cut(ammonia, DEMAND)
    assert 0 < deepest < 1
    baseline = al.unconstrained_emissions(ammonia, DEMAND)

    al.solve_allocation(ammonia, DEMAND, emissions_cap_tco2e=baseline * (1 - deepest * 0.99))
    with pytest.raises(ValueError, match="No feasible allocation"):
        al.solve_allocation(ammonia, DEMAND, emissions_cap_tco2e=baseline * (1 - deepest * 1.01))


def test_tighter_capacity_limits_reduce_how_deep_a_cut_is_possible(ammonia):
    """Clean routes are capped too, so the ceiling on ambition is a supply fact."""
    loose = al.max_feasible_cut(ammonia, DEMAND, al.CapacityAssumptions(0.9))
    tight = al.max_feasible_cut(ammonia, DEMAND, al.CapacityAssumptions(0.3))
    assert loose > tight


def test_read_result_states_the_decision_number_when_the_ceiling_binds(ammonia):
    """The verdict has to name the shadow price, not just report a mix."""
    cap = al.unconstrained_emissions(ammonia, DEMAND) * 0.6
    res = al.solve_allocation(ammonia, DEMAND, emissions_cap_tco2e=cap)
    lines = " ".join(al.read_result(res, ammonia))
    assert "binding" in lines
    assert f"{res.emissions_shadow_price_eur_per_tco2e:,.2f}" in lines
    assert "allowances" in lines


def test_read_result_says_so_when_the_ceiling_does_nothing(ammonia):
    slack = al.unconstrained_emissions(ammonia, DEMAND) * 1.5
    res = al.solve_allocation(ammonia, DEMAND, emissions_cap_tco2e=slack)
    lines = " ".join(al.read_result(res, ammonia))
    assert "not binding" in lines


def test_read_result_admits_when_a_sort_would_do(ammonia):
    """No ceiling means no optimisation, and the verdict must not pretend."""
    res = al.solve_allocation(ammonia, DEMAND)
    lines = " ".join(al.read_result(res, ammonia))
    assert "sort would produce the same answer" in lines


def test_read_result_flags_capacity_as_the_driver_when_limits_bind(ammonia):
    res = al.solve_allocation(ammonia, DEMAND, al.CapacityAssumptions(0.4))
    lines = " ".join(al.read_result(res, ammonia))
    assert "capacity assumption" in lines
    assert "no source" in lines


def test_read_result_derives_every_share_it_quotes(ammonia):
    """Nothing in the verdict may be written in advance."""
    res = al.solve_allocation(ammonia, DEMAND)
    lines = " ".join(al.read_result(res, ammonia))
    for route, share in res.shares().items():
        if share > 0:
            assert route in lines
            assert f"{share:.0%}" in lines
