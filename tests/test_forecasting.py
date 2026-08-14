"""Tests for the carbon price forecasting module.

The tests that matter here are not the ones checking arithmetic. They are the
ones pinning the study's conclusion: that neither fitted model beats a random
walk, and that the resulting intervals are far wider than the institutional
consensus. If a future change makes a model appear to win, that is far more
likely to be a leak of future information into the training window than a
genuine discovery, and a failing test is the right way to find out.
"""

import numpy as np
import pandas as pd
import pytest

from cbam_model.forecasting import price_model as pm
from cbam_model.market_data import eua_prices as ep


@pytest.fixture(scope="module")
def monthly():
    return ep.to_monthly(ep.load_eua_daily())["price_mean"]


@pytest.fixture(scope="module")
def validations(monthly):
    return {name: pm.walk_forward(monthly, fn) for name, fn in pm.MODELS.items()}


# ---------------------------------------------------------------------------
# The models behave the way their docstrings claim
# ---------------------------------------------------------------------------


def test_random_walk_returns_the_last_observation():
    s = pd.Series([1.0, 2.0, 3.0, 42.0])
    assert pm.random_walk(s, horizon=48) == 42.0


def test_random_walk_ignores_the_horizon():
    """It has no time dependence, which is what makes it the baseline."""
    s = pd.Series([10.0, 20.0, 30.0])
    assert pm.random_walk(s, 1) == pm.random_walk(s, 480)


def test_drift_extrapolates_a_constant_growth_rate():
    """On a perfectly exponential series, drift should recover it exactly."""
    s = pd.Series(np.exp(np.arange(50) * 0.01))
    assert pm.drift(s, horizon=10) == pytest.approx(float(s.iloc[-1]) * np.exp(0.10))


def test_ar1_recovers_the_mean_of_a_stationary_series():
    """A series oscillating about a level should forecast to that level."""
    rng = np.random.default_rng(0)
    level = np.log(50.0)
    y = [level]
    for _ in range(500):
        y.append(level + 0.5 * (y[-1] - level) + rng.normal(0, 0.05))
    s = pd.Series(np.exp(y))
    assert pm.ar1_log(s, horizon=48) == pytest.approx(50.0, rel=0.10)


def test_ar1_degenerates_to_random_walk_on_a_true_random_walk():
    """With phi at 1 there is nothing to revert to, and it should say so."""
    rng = np.random.default_rng(1)
    s = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.05, 800)) + np.log(80)))
    assert pm.ar1_log(s, horizon=48) == pytest.approx(float(s.iloc[-1]), rel=0.30)


# ---------------------------------------------------------------------------
# Validation does not leak the future
# ---------------------------------------------------------------------------


def test_walk_forward_never_trains_on_data_after_the_origin(monthly):
    """The failure this guards against reports accuracy nobody can achieve."""
    seen = {}

    def spy(train, horizon):
        seen[len(train)] = train.index[-1]
        return float(train.iloc[-1])

    results = pm.walk_forward(monthly, spy)
    for _, row in results.iterrows():
        assert row["origin"] < row["target"]
    assert max(seen.values()) < monthly.index[-1]


def test_every_fold_targets_exactly_the_horizon_ahead(monthly, validations):
    r = validations["random_walk"]
    months = (r["target"].dt.to_period("M") - r["origin"].dt.to_period("M")).apply(lambda x: x.n)
    assert (months == pm.HORIZON_MONTHS).all()


def test_effective_sample_size_is_reported_and_small(monthly, validations):
    """115 folds are not 115 tests, and the write-up must not imply they are."""
    n = len(validations["random_walk"])
    assert n > 100
    assert pm.effective_sample_size(n) < 5


# ---------------------------------------------------------------------------
# The finding
# ---------------------------------------------------------------------------


def test_no_model_beats_the_random_walk_by_a_material_margin(monthly, validations):
    """The result the forecasting section rests on, stated precisely.

    One model, `damped_trend`, does edge the baseline. The claim is therefore
    not that nothing beats a random walk, it is that nothing beats it by enough
    to matter: a skill score of a few percent, on a horizon with roughly two
    and a half independent windows behind it, is not a margin this sample can
    distinguish from luck.

    The 0.25 threshold is deliberately generous. Anything genuinely useful for
    a cost model would clear it easily.
    """
    base = validations["random_walk"]
    for name in pm.PRESPECIFIED:
        if name == pm.BASELINE:
            continue
        score = pm.evaluate(validations[name], name, baseline=base)
        assert score.skill_vs_baseline < 0.25, f"{name} did unexpectedly well, suspect a leak"


def test_the_best_model_is_still_unusable(monthly, validations):
    """Winning the comparison and being fit for purpose are different things."""
    base = validations["random_walk"]
    best = max(
        (pm.evaluate(validations[n], n, baseline=base) for n in pm.PRESPECIFIED),
        key=lambda s: s.skill_vs_baseline,
    )
    assert best.mape_pct > 40
    assert np.exp(best.median_abs_log_error) > 2.0


def test_trend_extrapolating_models_degrade_as_the_horizon_grows(monthly):
    """The systematic pattern, which is more informative than any single cell.

    Every model that extrapolates an undamped trend gets monotonically worse
    the further ahead it is asked to look. That ordering is not noise, and it
    is the evidence that the carbon price is not trend-following at long range.
    """
    sweep = pm.horizon_sweep(monthly, horizons=(6, 12, 24, 36, 48))
    skill = sweep.pivot(index="model", columns="horizon_months", values="skill_vs_baseline")
    for name in ("drift", "ar1_log", "theta"):
        row = skill.loc[name]
        assert row[48] < row[6], f"{name} did not degrade with horizon"
        assert (row < 0).all(), f"{name} beat the baseline somewhere"


def test_short_horizon_evidence_rests_on_a_usable_sample(monthly):
    """Six-month conclusions are worth more than four-year ones, and why."""
    sweep = pm.horizon_sweep(monthly, horizons=(6, 48))
    by_h = sweep.drop_duplicates("horizon_months").set_index("horizon_months")
    assert by_h.loc[6, "effective_folds"] > 20
    assert by_h.loc[48, "effective_folds"] < 5


def test_four_year_ahead_error_is_large_enough_to_be_disqualifying(monthly, validations):
    """A typical miss of more than a factor of two is not a usable forecast."""
    score = pm.evaluate(validations["random_walk"], "random_walk")
    assert score.mape_pct > 40
    assert np.exp(score.median_abs_log_error) > 2.0


def test_skill_is_zero_by_construction_for_the_baseline(monthly, validations):
    score = pm.evaluate(validations["random_walk"], "random_walk", baseline=validations["random_walk"])
    assert score.skill_vs_baseline == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# Intervals, and the comparison with the consensus
# ---------------------------------------------------------------------------


def test_intervals_are_wider_than_the_institutional_consensus(monthly):
    """The finding that justifies keeping sourced anchors as the base case."""
    con = pm.consensus_2030()
    for name, fn in pm.MODELS.items():
        f = pm.forecast_with_interval(monthly, fn, name)
        assert f.width_ratio() > con["width_ratio"] * 2, name


def test_models_are_biased_low_over_this_sample(monthly):
    """Every model under-predicted, because the sample contains one big rise.

    Pinned because it is the mechanism behind intervals that can sit entirely
    above their own point forecast, which otherwise reads as a bug.
    """
    for name, fn in pm.MODELS.items():
        f = pm.forecast_with_interval(monthly, fn, name)
        assert f.bias_factor() > 1.0, name


def test_consensus_central_is_not_contradicted_by_the_data(monthly):
    """EUR 126 sits inside what the price history admits. It is not refuted."""
    f = pm.forecast_with_interval(monthly, pm.random_walk, "random_walk")
    assert f.contains(pm.consensus_2030()["central"])


def test_comparison_reports_every_field_the_writeup_quotes(monthly):
    f = pm.forecast_with_interval(monthly, pm.random_walk, "random_walk")
    out = pm.compare_with_consensus(f)
    expected = {
        "model",
        "model_point_eur",
        "model_interval_eur",
        "model_width_ratio",
        "consensus_central_eur",
        "consensus_range_eur",
        "consensus_width_ratio",
        "consensus_inside_model_interval",
        "model_interval_is_wider_by",
        "model_bias_factor",
    }
    assert set(out) == expected
    assert out["model_interval_is_wider_by"] > 1


def test_narrower_interval_requested_gives_narrower_interval(monthly):
    wide = pm.forecast_with_interval(monthly, pm.random_walk, "rw", interval_pct=90)
    narrow = pm.forecast_with_interval(monthly, pm.random_walk, "rw", interval_pct=50)
    assert narrow.width_ratio() < wide.width_ratio()
