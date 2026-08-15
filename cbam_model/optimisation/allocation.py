"""Least-cost sourcing allocation within a single destination market.

THE PROBLEM
-----------
An importer serving ONE market needs D tonnes of a product in a given year.
Each production pathway available on that market's corridor has a cost per
tonne and an embedded emissions intensity. Supply from any one pathway is
capped. Total embedded emissions must sit under a ceiling. Minimise cost.

    minimise    sum_i  c_i x_i
    subject to  sum_i  x_i        =  D          demand is met exactly
                sum_i  e_i x_i    <= E          emissions ceiling
                       x_i        <= k_i        capacity of pathway i
                       x_i        >= 0

ONE MARKET AT A TIME, AND WHY THAT IS NOT A DETAIL
--------------------------------------------------
The first version of this module allocated a single pool of demand across BOTH
corridors. That was wrong, and badly so. Halifax-Hamburg lands in Germany,
Ningbo-Felixstowe lands in Britain. A buyer in Hamburg cannot take delivery at
Felixstowe, so the two are not substitutable supply options and an answer of
the form "60% Halifax, 15% Ningbo" describes a decision nobody faces.

It also silently broke a rule the study states on the front of its own
dashboard: EUR and GBP figures for the two corridors are never converted or
combined. The old `build_options` converted precisely so it could combine.

So `corridor` is now required, and each market is solved on its own. Compare
two solved markets side by side with `market_comparison`. Comparing two
independent optimisations is legitimate; merging them was not.

Note the one conversion that remains and why it is different: production cost
is only published in EUR, so a UK-market solve converts its GBP compliance cost
into EUR to have one currency in one objective function. That is a conversion
inside a single market, not a comparison across two.

WHY `cbam_default` IS NOT A DECISION VARIABLE
---------------------------------------------
It is excluded from the decision set, and this is not a preference.

`cbam_default` is the IR 2025/2621 regulatory default emissions value, applied
when a declarant does not supply verified data. It is not a production method.
The data shows it plainly: on every corridor and product its production cost is
identical to the fossil pathway's, because it IS the fossil pathway, declared
differently. Halifax ammonia grey and default are both EUR 446.80; Ningbo
ammonia coal and default are both EUR 416.50.

Allocating volume between "grey_smr" and "cbam_default" therefore splits one
physical supply between two accounting treatments and calls it a sourcing
decision. The earlier version did exactly that and reported it as a result.

A REAL FINDING CAME OUT OF THAT MISTAKE, and it belongs in the discussion
chapter rather than here: the default is *more favourable than verified
reality* on both corridors. Canadian ammonia declares 1.98 tCO2e by default
against an actual LCA figure of 2.18; Chinese ammonia declares 4.36 against
6.15. An exporter therefore has no incentive to verify its emissions, which is
a statement about how the regulation is designed, not about how to source.

HOW HARD IS THIS PROBLEM, HONESTLY
----------------------------------
Harder than a sort, easier than the word "optimisation" suggests, and the
write-up should say so rather than let a reader assume otherwise.

Greedy over *pathways* fails once the ceiling binds, and there is a test
proving it. But greedy over *substitutions*, ranking every possible swap by
cost per tonne of CO2e saved and buying them cheapest first, does find the
optimum. This is a fractional knapsack. An operational research reader will
notice within seconds, so claim only what is true.

What the LP formulation buys is generality and the dual: the greedy rule stops
working the moment a second coupling constraint is added, and the shadow price
falls out of the solve rather than needing to be derived.

With only two pathways on a corridor, as for ammonia once `cbam_default` is
excluded, demand and the ceiling together determine the answer outright and
there is no freedom left to optimise. Say so when reporting it. The useful
outputs there are the shadow price and the cross-market comparison, not the
mix. Hydrogen, with three pathways, has genuine choice.

SCOPE OF THE COST
-----------------
Production cost plus carbon compliance cost. Deliberately not delivered cost:
conversion and freight are PLACEHOLDER rows with no owner in
`commercial_inputs.csv`, and pulling them in would put unsourced numbers into
the objective function of an optimisation and let them decide the answer.

Solved with `scipy.optimize.linprog` (HiGHS). The formulation is standard and
ports to GLPK or PuLP unchanged if that is preferred.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from .. import data_io, runner
from ..config import regulatory_constants as rc


@dataclass(frozen=True)
class CapacityAssumptions:
    """Per-route supply limits, expressed as a multiple of total demand.

    THESE ARE NOT SOURCED. Nobody on the project has plant nameplate capacity,
    export terminal throughput or fleet availability, and no public figure was
    used. They are analyst-chosen scenario parameters, and any result computed
    from them is conditional on them.

    The default of 0.6 says no single corridor-pathway can supply more than
    60% of demand, which forces at least two routes into any feasible answer.
    That is the point: a capacity assumption that never binds produces a
    single-winner answer and makes the optimisation decorative, and one that
    binds everywhere makes the answer an artefact of the assumption rather
    than of the costs.

    Treat the sweep in `capacity_sensitivity` as the primary result rather
    than any single solve, for the same reason the study reports a carbon
    price bracket rather than one price.
    """

    per_route_share_of_demand: float = 0.6
    overrides: dict = field(default_factory=dict)

    def limit_for(self, route: str, demand: float) -> float:
        if route in self.overrides:
            return self.overrides[route] * demand
        return self.per_route_share_of_demand * demand


@dataclass(frozen=True)
class AllocationResult:
    """A solved allocation, with the duals that make it worth solving."""

    product: str
    year: int
    price_scenario: str
    demand_tonnes: float
    allocation: pd.Series
    total_cost_eur: float
    cost_per_tonne_eur: float
    total_emissions_tco2e: float
    emissions_cap_tco2e: float | None
    emissions_shadow_price_eur_per_tco2e: float | None
    routes_used: int
    binding_capacities: tuple

    def emissions_cap_binds(self) -> bool:
        if self.emissions_cap_tco2e is None:
            return False
        return self.total_emissions_tco2e >= self.emissions_cap_tco2e - 1e-6

    def shares(self) -> pd.Series:
        return (self.allocation / self.demand_tonnes).round(4)


# Excluded from every decision set. See the module docstring: this is a
# declaration treatment for an existing pathway, not a pathway of its own, and
# allocating volume to it splits one physical supply in two.
NON_PATHWAYS = ("cbam_default",)


def build_options(
    product: str,
    year: int,
    price_scenario: str,
    corridor: str,
    compliance: pd.DataFrame | None = None,
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """Cost and emissions per tonne for the pathways serving ONE market.

    `corridor` is required. Each corridor delivers into a different
    jurisdiction, so a single solve must never span both. See the module
    docstring for what went wrong when it did.

    A UK-market solve converts its GBP compliance cost to EUR at the same fixed
    ECB reference rate used elsewhere, because production cost is only
    published in EUR and one objective function needs one currency. That is a
    conversion within a market, not a comparison across two.

    `uk_price_variant` matters to the UK market's answer rather than merely
    colouring it. Under `frozen` the UK price is held at the 2026 determination
    while the EU price rises; under `linked` they converge. Report any finding
    against the variant that produced it, and since `linked` is not law,
    `frozen` stays the base case.
    """
    if corridor not in rc.CORRIDORS:
        raise ValueError(f"Unknown corridor {corridor!r}. Expected one of {list(rc.CORRIDORS)}.")

    if compliance is None:
        compliance = runner.run_compliance_matrix(uk_price_variant=uk_price_variant)

    rows = compliance[
        (compliance["product"] == product)
        & (compliance["year"] == year)
        & (compliance["price_scenario"] == price_scenario)
        & (compliance["corridor"] == corridor)
        & (~compliance["pathway"].isin(NON_PATHWAYS))
        & (compliance["uk_ets_variant"].isin(["current_scope", "n/a"]))
        & (compliance["uk_price_variant"].isin([uk_price_variant, "n/a"]))
    ].copy()

    if rows.empty:
        raise ValueError(
            f"No compliance rows for {product} on {corridor} in {year} at "
            f"{price_scenario}, once declaration-only pathways are excluded."
        )

    rows["compliance_eur_per_tonne"] = np.where(
        rows["currency"] == "GBP",
        rows["total_compliance_cost_per_tonne"] * rc.FX_EUR_PER_GBP,
        rows["total_compliance_cost_per_tonne"],
    )

    _, _, commercial = data_io.load_inputs()
    production = commercial.set_index(["corridor", "product", "pathway"])[
        "production_cost_eur_per_tonne"
    ]

    options = (
        rows.groupby(["corridor", "pathway"])
        .agg(
            compliance_eur_per_tonne=("compliance_eur_per_tonne", "mean"),
            emissions_tco2e_per_tonne=("embedded_emissions_tco2e_per_tonne", "first"),
        )
        .reset_index()
    )
    options["production_eur_per_tonne"] = [
        float(production.loc[(c, product, p)]) for c, p in zip(options.corridor, options.pathway, strict=True)
    ]
    options["cost_eur_per_tonne"] = (
        options["production_eur_per_tonne"] + options["compliance_eur_per_tonne"]
    )
    options["route"] = options["corridor"] + " / " + options["pathway"]
    return options.set_index("route").sort_values("cost_eur_per_tonne")


def solve_allocation(
    options: pd.DataFrame,
    demand_tonnes: float,
    capacities: CapacityAssumptions | None = None,
    emissions_cap_tco2e: float | None = None,
    product: str = "",
    year: int = 0,
    price_scenario: str = "",
) -> AllocationResult:
    """Solve the least-cost allocation and return the duals with it.

    An infeasible problem raises rather than returning an empty answer, since
    the usual cause is an emissions ceiling below what the cleanest available
    routes can achieve at the given capacities, and that is a statement about
    the assumptions that deserves to be read rather than silently absorbed.
    """
    capacities = capacities or CapacityAssumptions()

    cost = options["cost_eur_per_tonne"].to_numpy(dtype=float)
    emissions = options["emissions_tco2e_per_tonne"].to_numpy(dtype=float)
    upper = np.array([capacities.limit_for(r, demand_tonnes) for r in options.index])

    if upper.sum() < demand_tonnes - 1e-9:
        raise ValueError(
            f"Capacities total {upper.sum():,.0f} t against demand of "
            f"{demand_tonnes:,.0f} t, so no allocation can meet demand. Raise "
            "per_route_share_of_demand or lower demand."
        )

    a_ub = emissions.reshape(1, -1) if emissions_cap_tco2e is not None else None
    b_ub = np.array([emissions_cap_tco2e]) if emissions_cap_tco2e is not None else None

    solution = linprog(
        c=cost,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=np.ones((1, len(cost))),
        b_eq=np.array([demand_tonnes]),
        bounds=[(0.0, u) for u in upper],
        method="highs",
    )

    if not solution.success:
        raise ValueError(
            f"No feasible allocation: {solution.message}. The usual cause is an "
            "emissions ceiling below what the cleanest routes can deliver "
            "within their capacities."
        )

    allocation = pd.Series(solution.x, index=options.index, name="tonnes")
    shadow = None
    if emissions_cap_tco2e is not None:
        # HiGHS returns duals with the sign convention of a minimisation with
        # <= constraints, so the marginal is non-positive. Negated here so the
        # reported shadow price reads as a cost per tonne of CO2e, which is
        # the direction every other carbon price in the study runs.
        shadow = float(-solution.ineqlin.marginals[0])

    binding = tuple(
        route
        for route, taken, cap in zip(options.index, solution.x, upper, strict=True)
        if taken >= cap - 1e-6 and taken > 1e-9
    )

    return AllocationResult(
        product=product,
        year=year,
        price_scenario=price_scenario,
        demand_tonnes=demand_tonnes,
        allocation=allocation,
        total_cost_eur=float(solution.fun),
        cost_per_tonne_eur=float(solution.fun) / demand_tonnes,
        total_emissions_tco2e=float(emissions @ solution.x),
        emissions_cap_tco2e=emissions_cap_tco2e,
        emissions_shadow_price_eur_per_tco2e=shadow,
        routes_used=int((solution.x > 1e-6).sum()),
        binding_capacities=binding,
    )


def unconstrained_emissions(options: pd.DataFrame, demand_tonnes: float, capacities=None) -> float:
    """Emissions of the cheapest allocation when no ceiling is imposed.

    The reference point an emissions cap should be expressed against. A cap
    above this number cannot bind and the optimisation degenerates to a
    merit-order fill, which is worth knowing before quoting a result.
    """
    result = solve_allocation(options, demand_tonnes, capacities, emissions_cap_tco2e=None)
    return result.total_emissions_tco2e


def read_result(
    result: AllocationResult,
    options: pd.DataFrame,
    label=None,
) -> list[str]:
    """Turn a solved allocation into the sentences a reader needs.

    Exists because a table of numbers is not a finding. Every statement here is
    derived from the solution rather than written in advance, so it cannot
    drift from what the model actually returned, and each one is a claim
    somebody could disagree with rather than a description of the output.

    `label` maps a route key to display text. It is injected rather than
    hardcoded because this package must not know how the dashboard names
    things, and the raw keys are internal identifiers rather than copy:
    "ningbo_felixstowe / coal_gasification" is correct and unreadable.
    """
    label = label or (lambda route: route)
    shares = result.shares()
    used = shares[shares > 0].sort_values(ascending=False)
    lines = []

    mix = ", ".join(f"{share:.0%} {label(route)}" for route, share in used.items())
    lines.append(
        f"Cheapest way to source {result.demand_tonnes / 1_000:,.0f} kt is {mix}, "
        f"at EUR {result.cost_per_tonne_eur:,.2f} per tonne."
    )

    corridors = {route.split(" / ")[0] for route in used.index}
    if len(corridors) == 1:
        lines.append(
            "One corridor supplies everything, so on these assumptions the "
            "comparison has a clear winner rather than a split."
        )
    else:
        lines.append(
            "Both corridors appear in the answer, so the cheapest single option "
            "does not simply win: the capacity limits force a split, and the "
            "second and third choices are what the answer turns on."
        )

    if result.emissions_cap_tco2e is None:
        lines.append(
            "With no emissions ceiling this is a merit-order fill and a sort "
            "would produce the same answer. Add a ceiling to make it an "
            "optimisation."
        )
    elif result.emissions_cap_binds():
        shadow = result.emissions_shadow_price_eur_per_tco2e
        lines.append(
            f"The emissions ceiling is binding, and the last tonne of CO2e "
            f"removed cost EUR {shadow:,.2f}. That is the decision number: "
            f"buying allowances is worth it below EUR {shadow:,.2f} per tonne "
            f"and not above it."
        )
    else:
        lines.append(
            "The emissions ceiling is not binding. The cost-minimising mix "
            "already sits under it, so the target is not changing behaviour "
            "and its shadow price is zero."
        )

    if result.binding_capacities:
        named = ", ".join(label(r) for r in result.binding_capacities)
        lines.append(
            f"At their capacity limit: {named}. The answer is being set by the "
            "capacity assumption as much as by the costs, and those limits are "
            "analyst choices with no source."
        )

    dirtiest = options["emissions_tco2e_per_tonne"].idxmax()
    if dirtiest in used.index:
        lines.append(
            f"Note that {label(dirtiest)}, the most carbon-intensive route on the "
            f"menu at {options.loc[dirtiest, 'emissions_tco2e_per_tonne']:.2f} "
            "tCO2e per tonne, is still in the optimal mix. Cost is beating "
            "carbon intensity here."
        )

    return lines


def min_achievable_emissions(
    options: pd.DataFrame,
    demand_tonnes: float,
    capacities: CapacityAssumptions | None = None,
) -> float:
    """The cleanest allocation possible, ignoring cost entirely.

    The same program with emissions as the objective instead of the
    constraint. It is the floor on any emissions ceiling: ask for less than
    this and the problem is infeasible no matter how much money is available,
    because the clean routes cannot supply the volume.

    Worth reporting rather than letting the solver return a bare infeasibility.
    "You cannot cut more than 47%" is a finding about the supply base; "the
    problem is infeasible" is a complaint about the solver.
    """
    capacities = capacities or CapacityAssumptions()
    emissions = options["emissions_tco2e_per_tonne"].to_numpy(dtype=float)
    upper = np.array([capacities.limit_for(r, demand_tonnes) for r in options.index])

    solution = linprog(
        c=emissions,
        A_eq=np.ones((1, len(emissions))),
        b_eq=np.array([demand_tonnes]),
        bounds=[(0.0, u) for u in upper],
        method="highs",
    )
    if not solution.success:
        raise ValueError(
            f"Capacities total {upper.sum():,.0f} t against demand of "
            f"{demand_tonnes:,.0f} t, so no allocation can meet demand."
        )
    return float(solution.fun)


def max_feasible_cut(
    options: pd.DataFrame,
    demand_tonnes: float,
    capacities: CapacityAssumptions | None = None,
) -> float:
    """Deepest emissions cut achievable, as a fraction of the cost-optimal mix."""
    capacities = capacities or CapacityAssumptions()
    baseline = unconstrained_emissions(options, demand_tonnes, capacities)
    floor = min_achievable_emissions(options, demand_tonnes, capacities)
    return 1.0 - floor / baseline


def cap_sweep(
    options: pd.DataFrame,
    demand_tonnes: float,
    capacities: CapacityAssumptions | None = None,
    tightenings: tuple[float, ...] = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3),
) -> pd.DataFrame:
    """Cost and shadow price as the emissions ceiling tightens.

    Each row is the ceiling set to a fraction of the unconstrained optimum's
    emissions. The shadow price column is the marginal abatement cost implied
    by the sourcing problem at that level of ambition, which is a result the
    deterministic model cannot produce at all.
    """
    capacities = capacities or CapacityAssumptions()
    baseline = unconstrained_emissions(options, demand_tonnes, capacities)

    rows = []
    for fraction in tightenings:
        cap = baseline * fraction
        try:
            res = solve_allocation(options, demand_tonnes, capacities, emissions_cap_tco2e=cap)
        except ValueError:
            rows.append({"cap_fraction": fraction, "feasible": False})
            continue
        rows.append(
            {
                "cap_fraction": fraction,
                "feasible": True,
                "cap_tco2e": cap,
                "cost_per_tonne_eur": res.cost_per_tonne_eur,
                "shadow_price_eur_per_tco2e": res.emissions_shadow_price_eur_per_tco2e,
                "routes_used": res.routes_used,
                "binds": res.emissions_cap_binds(),
            }
        )
    return pd.DataFrame(rows)


def price_scenario_comparison(
    product: str,
    year: int,
    demand_tonnes: float,
    corridor: str,
    capacities: CapacityAssumptions | None = None,
    cap_fraction: float | None = 0.7,
    compliance: pd.DataFrame | None = None,
    cap_reference_scenario: str = "medium",
) -> pd.DataFrame:
    """Does the optimal mix change across the three sourced carbon price paths?

    Deliberately swept over the study's own low, medium and high anchors rather
    than a continuous carbon price. A continuous sweep would need prices that
    no source supports, and inventing them to produce a smooth switching curve
    would manufacture exactly the false precision the study avoids elsewhere.

    Three points cannot locate a threshold to the euro. They can answer the
    question that matters, which is whether the answer is stable across the
    range the evidence admits.

    THE EMISSIONS CEILING IS HELD CONSTANT IN ABSOLUTE TERMS, derived once from
    `cap_reference_scenario`. The first version of this function set the ceiling
    to a fraction of each scenario's own unconstrained optimum, which meant the
    ceiling moved with the price and the comparison changed two things at once.
    It produced a genuinely wrong answer: total cost came out lower at the
    medium price than at the low price, which cannot happen when only the carbon
    price rises. An importer faces one emissions target, not a target indexed to
    the carbon price, so a fixed absolute ceiling is also the realistic framing.
    """
    if compliance is None:
        compliance = runner.run_compliance_matrix()

    caps = capacities or CapacityAssumptions()

    cap = None
    if cap_fraction is not None:
        reference = build_options(
            product, year, cap_reference_scenario, corridor, compliance=compliance
        )
        cap = unconstrained_emissions(reference, demand_tonnes, caps) * cap_fraction

    rows = []
    for scenario in rc.PRICE_SCENARIOS:
        options = build_options(product, year, scenario, corridor, compliance=compliance)
        res = solve_allocation(
            options, demand_tonnes, caps, cap, product=product, year=year, price_scenario=scenario
        )
        row = {
            "price_scenario": scenario,
            "carbon_price_eur": rc.eu_ets_price(year, scenario),
            "cost_per_tonne_eur": round(res.cost_per_tonne_eur, 2),
            "routes_used": res.routes_used,
            "shadow_price_eur_per_tco2e": (
                round(res.emissions_shadow_price_eur_per_tco2e, 2)
                if res.emissions_shadow_price_eur_per_tco2e is not None
                else None
            ),
        }
        row.update({f"share::{r}": v for r, v in res.shares().items() if v > 0})
        rows.append(row)

    out = pd.DataFrame(rows).fillna(0.0)
    share_cols = [c for c in out.columns if c.startswith("share::")]
    out.attrs["mix_is_invariant"] = bool(out[share_cols].nunique().eq(1).all())
    return out


def cheapest_substitution(options: pd.DataFrame) -> dict:
    """The cheapest way to buy a tonne of CO2e reduction in this market.

    Ranks every ordered pair of pathways by the cost of switching a tonne of
    product from the dirtier to the cleaner one, divided by the CO2e that saves.
    The minimum is the marginal abatement cost, and it is what the LP's shadow
    price converges to once the ceiling starts to bind.

    Exists so that a comparison between markets can name the mechanism instead
    of asserting one. Abatement being cheap or dear depends on BOTH how much
    cleaner the alternative is and how much more it costs, and which of those
    dominates is not something to guess at: for ammonia the dirtier corridor
    has the cheaper abatement, for hydrogen it does not.
    """
    best = None
    for dirty in options.index:
        for clean in options.index:
            saved = (
                options.loc[dirty, "emissions_tco2e_per_tonne"]
                - options.loc[clean, "emissions_tco2e_per_tonne"]
            )
            if saved <= 0:
                continue
            extra = (
                options.loc[clean, "cost_eur_per_tonne"]
                - options.loc[dirty, "cost_eur_per_tonne"]
            )
            rate = extra / saved
            if best is None or rate < best["eur_per_tco2e"]:
                best = {
                    "from_route": dirty,
                    "to_route": clean,
                    "eur_per_tco2e": rate,
                    "tco2e_saved_per_tonne": saved,
                    "extra_cost_per_tonne": extra,
                }
    if best is None:
        raise ValueError("No pathway is cleaner than another, so no abatement is possible.")
    return best


def market_comparison(
    product: str,
    year: int,
    demand_tonnes: float,
    price_scenario: str = "medium",
    cut_fraction: float = 0.3,
    capacities: CapacityAssumptions | None = None,
    uk_price_variant: str = "frozen",
) -> pd.DataFrame:
    """Solve each destination market on its own, then set the answers side by side.

    This is the corridor comparison the study needs, done in the only way that
    is defensible. Each market gets its own demand, its own pathways and its own
    solve. Nothing is pooled and no volume is ever allocated from one corridor
    to the other, because a Hamburg buyer cannot take delivery at Felixstowe.

    The comparison is like for like: both markets are given the same volume to
    source and the same proportional emissions cut against their own
    cost-minimising baseline. That is what makes the shadow prices comparable.
    An identical absolute ceiling would not be, since the two baselines differ.

    The column worth reading is the shadow price. It is what one more tonne of
    CO2e headroom is worth to an importer in that market, so a gap between the
    two says the same decarbonisation target costs more on one corridor than
    the other, and by how much.
    """
    capacities = capacities or CapacityAssumptions()
    compliance = runner.run_compliance_matrix(uk_price_variant=uk_price_variant)

    by_corridor = {
        corridor: build_options(
            product, year, price_scenario, corridor,
            compliance=compliance, uk_price_variant=uk_price_variant,
        )
        for corridor in rc.CORRIDORS
    }

    # Both markets get the same proportional cut, and it has to be one that
    # both can actually achieve, or the comparison silently becomes a
    # comparison of two different targets. With few pathways and a capacity
    # limit, the deepest achievable cut is often well under what a user asks
    # for: two pathways capped at 60% cannot cut much at all.
    achievable = min(
        max_feasible_cut(options, demand_tonnes, capacities)
        for options in by_corridor.values()
    )
    applied_cut = min(cut_fraction, achievable)

    rows = []
    for corridor, options in by_corridor.items():
        baseline = unconstrained_emissions(options, demand_tonnes, capacities)
        result = solve_allocation(
            options, demand_tonnes, capacities,
            emissions_cap_tco2e=baseline * (1 - applied_cut),
            product=product, year=year, price_scenario=price_scenario,
        )
        swap = cheapest_substitution(options)
        shares = result.shares()
        green = float(
            sum(v for route, v in shares.items() if "green" in route or "ccs" in route)
        )
        rows.append(
            {
                "corridor": corridor,
                "regime": rc.CORRIDOR_REGIME[corridor],
                "pathways_available": len(options),
                "baseline_emissions_tco2e": round(baseline, 0),
                "cost_per_tonne_eur": round(result.cost_per_tonne_eur, 2),
                "shadow_price_eur_per_tco2e": (
                    round(result.emissions_shadow_price_eur_per_tco2e, 2)
                    if result.emissions_shadow_price_eur_per_tco2e is not None
                    else None
                ),
                "low_carbon_share": round(green, 4),
                "allocation_is_determined": len(options) <= 2,
                "cheapest_swap_from": swap["from_route"].split(" / ")[1],
                "cheapest_swap_to": swap["to_route"].split(" / ")[1],
                "swap_saves_tco2e_per_tonne": round(swap["tco2e_saved_per_tonne"], 2),
                "swap_costs_eur_per_tonne": round(swap["extra_cost_per_tonne"], 2),
            }
        )

    out = pd.DataFrame(rows)
    out.attrs["requested_cut"] = cut_fraction
    out.attrs["applied_cut"] = applied_cut
    out.attrs["cut_was_limited"] = applied_cut < cut_fraction - 1e-9
    # Flag rather than hide the case where the LP has no freedom left. With two
    # pathways, demand and the ceiling pin the answer exactly and the mix is
    # arithmetic rather than a choice.
    out.attrs["any_market_determined"] = bool(out["allocation_is_determined"].any())
    return out


def capacity_sensitivity(
    options: pd.DataFrame,
    demand_tonnes: float,
    shares: tuple[float, ...] = (0.4, 0.5, 0.6, 0.8, 1.0),
    cap_fraction: float = 0.7,
) -> pd.DataFrame:
    """How much of the answer is the capacity assumption rather than the costs.

    This is the primary robustness check on everything in this module, because
    the capacity numbers are the one input here with no provenance at all. If
    the reported allocation swings wildly across this sweep, the result is a
    statement about the assumption, not about the corridors.

    A share can be infeasible in two distinct ways and both are reported rather
    than raised, because each is a fact about the supply base worth reading.
    Too little total capacity cannot meet demand at all. And where the capacity
    limit exactly divides demand between the available pathways, the mix is
    pinned with no slack, so no emissions cut is possible at any price: with two
    pathways and a 50% limit, both must supply exactly half.
    """
    rows = []
    for share in shares:
        caps = CapacityAssumptions(per_route_share_of_demand=share)
        if share * len(options) < 1.0:
            rows.append(
                {"per_route_share": share, "feasible": False, "why": "capacity below demand"}
            )
            continue
        baseline = unconstrained_emissions(options, demand_tonnes, caps)
        try:
            res = solve_allocation(
                options, demand_tonnes, caps, emissions_cap_tco2e=baseline * cap_fraction
            )
        except ValueError:
            rows.append(
                {"per_route_share": share, "feasible": False, "why": "mix is pinned, no cut possible"}
            )
            continue
        row = {
            "per_route_share": share,
            "feasible": True,
            "why": "",
            "cost_per_tonne_eur": round(res.cost_per_tonne_eur, 2),
            "routes_used": res.routes_used,
            "shadow_price_eur_per_tco2e": round(res.emissions_shadow_price_eur_per_tco2e, 2),
        }
        row.update({f"share::{r}": v for r, v in res.shares().items() if v > 0})
        rows.append(row)
    return pd.DataFrame(rows).fillna(0.0)
