"""Cross-check against an external published result.

Ramsook, Boodlal and Maharaj (2025), "Navigating carbon border adjustments: A
case study of Trinidad and Tobago's ammonia exports", European Journal of
Energy Research 5(6). https://doi.org/10.24018/ejenergy.2025.5.6.177

STATUS: CALIBRATED 4 August 2026. Every input below is now read from the paper
itself rather than assumed. The earlier version of this module guessed the
ammonia price and emissions intensity and could not explain a factor-of-four
divergence.

WHAT THE CALIBRATION FOUND, and it is not a rounding problem
------------------------------------------------------------
The divergence was never about the inputs. It is that this project's
`eu_cbam_cost` and the paper's method compute the free allocation adjustment in
two structurally different ways:

    this model   chargeable = embedded x CBAM_factor
    the paper    chargeable = embedded - benchmark x (1 - CBAM_factor)

The two agree only in 2034, when the factor reaches 1.00 and free allocation is
gone. Before that they diverge sharply, and the gap is widest for producers
furthest from the benchmark.

The paper's version is the one that matches Regulation (EU) 2023/956 Article
31, which adjusts the certificate obligation to reflect the free allocation an
EU installation producing the same good would receive. Free allocation under
Article 10a of Directive 2003/87/EC is benchmark-based: an installation gets
allowances up to a product benchmark, not a percentage of whatever it happens
to emit. So the shielded quantity is the benchmark, not a share of the
importer's own emissions.

Consequences, which are the reason this matters well beyond this module:

  1. For a producer dirtier than the benchmark, this model understates CBAM
     cost in every year before 2034. On the T&T case it understates the
     nine-year average by 32%.
  2. For a producer cleaner than the benchmark, the paper's formula can go
     negative and floor at zero, meaning genuinely clean production owes
     nothing at all rather than owing a small scaled amount. This model has no
     such behaviour.
  3. Point 2 bears directly on this dissertation's headline result. Under a
     benchmark mechanism, green pathways well below benchmark would owe zero
     CBAM from 2026, while grey pathways would pay on their excess over
     benchmark immediately rather than ramping up slowly. That would make CBAM
     materially more effective at closing the green premium than this model
     currently shows.

This module therefore reports BOTH formulas and does not silently switch the
model over. Switching would change every CBAM number in the study and requires
the CN-code benchmarks for hydrogen and ammonia to be read out of IR 2025/2621
first, which has not been done. See `benchmark_mechanism_gap()` below and the
open item in README.md.
"""

from ..config import regulatory_constants as rc
from ..model.cbam import eu_cbam_cost

# ---------------------------------------------------------------------------
# Inputs, all read from Ramsook et al. (2025)
# ---------------------------------------------------------------------------

# Projected T&T ammonia sector emission factor for 2025-2034. The paper gives
# 2.43-2.45; the midpoint is used.
TT_EMISSIONS_TCO2E_PER_TONNE = 2.44

# The paper's stated EU CBAM benchmark for ammonia. Note this is the figure
# that drives the whole divergence documented above.
EU_AMMONIA_BENCHMARK_TCO2E_PER_TONNE = 1.57

# FOB unit values, held static across the horizon by the paper deliberately, to
# isolate the CBAM effect from commodity price movement.
TT_AMMONIA_PRICE_USD_PER_TONNE_EU = 535.0
TT_AMMONIA_PRICE_USD_PER_TONNE_ROW = 433.0

# Constant across 2026-2034 in the paper's central case.
ASSUMED_CARBON_PRICE_USD_PER_TCO2E = 70.0

# T&T has no domestic carbon price on ammonia production.
TT_ORIGIN_CARBON_PRICE = 0.0

# The published headline. Measured against EU-bound export revenue only, not
# total export revenue. That resolves the third of the three candidate
# explanations the earlier version of this module listed: it was the wrong one.
RAMSOOK_MEAN_CBAM_USD_PER_TONNE = 115.0
RAMSOOK_BURDEN_SHARE = 0.22
RAMSOOK_HORIZON = tuple(range(2026, 2035))

TOLERANCE_PCT_POINTS = 5.0
CALIBRATED = True

# Everything here is in USD. The paper works in USD and the comparison is
# internal to it, so no conversion is applied and none is needed.
CURRENCY = "USD"


def _benchmark_mechanism_cost(
    embedded_tco2e: float, year: int, carbon_price: float, benchmark: float
) -> float:
    """CBAM cost under the benchmark-based free allocation adjustment.

    chargeable = embedded - benchmark x (1 - CBAM_factor), floored at zero.

    The floor matters: a producer at or below the benchmark owes nothing while
    free allocation is still being phased out.
    """
    free_allocation_share = 1.0 - rc.cbam_factor(year)
    chargeable = embedded_tco2e - benchmark * free_allocation_share
    return max(0.0, chargeable) * carbon_price


def run_reference_check(
    carbon_price: float = ASSUMED_CARBON_PRICE_USD_PER_TCO2E,
    ammonia_price: float = TT_AMMONIA_PRICE_USD_PER_TONNE_EU,
    emissions_tco2e_per_tonne: float = TT_EMISSIONS_TCO2E_PER_TONNE,
    benchmark: float = EU_AMMONIA_BENCHMARK_TCO2E_PER_TONNE,
) -> dict:
    """Reproduce Ramsook et al.'s horizon-average CBAM burden, both ways.

    The paper reports an average across 2026-2034 rather than a single-year
    figure, so this averages too. The earlier version of this module compared a
    2034 point estimate against that average, which was not like for like and
    was a second, separate error.
    """
    this_model, benchmark_model = [], []
    for year in RAMSOOK_HORIZON:
        this_model.append(
            eu_cbam_cost(
                embedded_emissions_tco2e=emissions_tco2e_per_tonne,
                year=year,
                cert_price_eur=carbon_price,
                origin_carbon_price_eur_per_tco2e=TT_ORIGIN_CARBON_PRICE,
                using_default_values=False,
                # Pinned explicitly. This arm exists to reproduce the
                # factor-scaled form and the divergence it caused, so it must
                # not follow the model default, which moved to the benchmark
                # mechanism on 6 August 2026.
                mechanism="factor_scaled",
            )
        )
        benchmark_model.append(
            _benchmark_mechanism_cost(
                emissions_tco2e_per_tonne, year, carbon_price, benchmark
            )
        )

    mean_this = sum(this_model) / len(this_model)
    mean_bench = sum(benchmark_model) / len(benchmark_model)

    share_this = mean_this / ammonia_price
    share_bench = mean_bench / ammonia_price

    return {
        "calibrated": CALIBRATED,
        "currency": CURRENCY,
        "horizon": (RAMSOOK_HORIZON[0], RAMSOOK_HORIZON[-1]),
        "published_mean_cbam": RAMSOOK_MEAN_CBAM_USD_PER_TONNE,
        "published_burden_share": RAMSOOK_BURDEN_SHARE,
        "this_model_mean_cbam": mean_this,
        "this_model_burden_share": share_this,
        "benchmark_model_mean_cbam": mean_bench,
        "benchmark_model_burden_share": share_bench,
        "this_model_gap_pct_points": abs(share_this - RAMSOOK_BURDEN_SHARE) * 100,
        "benchmark_model_gap_pct_points": abs(share_bench - RAMSOOK_BURDEN_SHARE) * 100,
        "this_model_agrees": abs(share_this - RAMSOOK_BURDEN_SHARE) * 100
        <= TOLERANCE_PCT_POINTS,
        "benchmark_model_agrees": abs(share_bench - RAMSOOK_BURDEN_SHARE) * 100
        <= TOLERANCE_PCT_POINTS,
        "understatement_ratio": (mean_bench / mean_this) if mean_this else None,
        "assumptions": {
            "emissions_tco2e_per_tonne": emissions_tco2e_per_tonne,
            "eu_benchmark_tco2e_per_tonne": benchmark,
            "ammonia_price_usd_per_tonne": ammonia_price,
            "carbon_price_usd_per_tco2e": carbon_price,
            "all_inputs_sourced_from_paper": True,
            "burden_measured_against": "EU-bound export revenue only",
        },
    }


def benchmark_mechanism_gap(
    embedded_tco2e: float,
    benchmark: float,
    carbon_price: float = 100.0,
    years=RAMSOOK_HORIZON,
) -> list:
    """How far apart the two formulas sit, year by year, for any pathway.

    Use this to size the risk on this study's own corridors before deciding
    whether to switch the model over. Pass a hydrogen or ammonia benchmark from
    IR 2025/2621 once it has been read out.

    Returns a list of dicts, one per year.
    """
    out = []
    for year in years:
        theirs = _benchmark_mechanism_cost(
            embedded_tco2e, year, carbon_price, benchmark
        )
        # Pinned to the old form for the same reason as in run_reference_check:
        # this function exists to contrast the two mechanisms, so following the
        # model default would make both arms identical.
        ours = eu_cbam_cost(
            embedded_tco2e, year, carbon_price, 0.0, False, mechanism="factor_scaled"
        )
        out.append(
            {
                "year": year,
                "cbam_factor": rc.cbam_factor(year),
                "this_model": ours,
                "benchmark_mechanism": theirs,
                "difference": theirs - ours,
                "ratio": (theirs / ours) if ours else None,
            }
        )
    return out


def format_reference_check(result: dict) -> str:
    c = result["currency"]
    lo, hi = result["horizon"]
    return (
        f"Reference case, Ramsook et al. (2025), T&T ammonia {lo}-{hi} average\n"
        f"  STATUS: calibrated, all inputs read from the paper.\n"
        f"  Burden is measured against EU-bound export revenue only.\n"
        f"\n"
        f"  Published:                {c} {result['published_mean_cbam']:.1f}/t "
        f"({result['published_burden_share']:.1%} of export value)\n"
        f"\n"
        f"  This model:               {c} {result['this_model_mean_cbam']:.1f}/t "
        f"({result['this_model_burden_share']:.1%})  "
        f"gap {result['this_model_gap_pct_points']:.1f} pp  "
        f"{'AGREES' if result['this_model_agrees'] else 'DIVERGES'}\n"
        f"  Benchmark mechanism:      {c} {result['benchmark_model_mean_cbam']:.1f}/t "
        f"({result['benchmark_model_burden_share']:.1%})  "
        f"gap {result['benchmark_model_gap_pct_points']:.1f} pp  "
        f"{'AGREES' if result['benchmark_model_agrees'] else 'DIVERGES'}\n"
        f"\n"
        f"  This model understates the published figure by a factor of "
        f"{result['understatement_ratio']:.2f}.\n"
        f"\n"
        f"  The two differ structurally, not numerically:\n"
        f"    this model    chargeable = embedded x CBAM_factor\n"
        f"    the paper     chargeable = embedded - benchmark x (1 - CBAM_factor)\n"
        f"  Only the second matches Regulation (EU) 2023/956 Article 31, under\n"
        f"  which free allocation shields a product benchmark rather than a\n"
        f"  share of the importer's own emissions. See the module docstring.\n"
    )
