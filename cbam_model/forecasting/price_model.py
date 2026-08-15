"""Forecasting the EUA price, and measuring honestly whether it works.

WHAT THIS IS FOR
----------------
Not to produce a better carbon price than the sourced anchors. To establish
what the price history alone can and cannot support, so the study can say
something evidenced about the uncertainty around its central case instead of
asserting that a scenario bracket is adequate.

The result that matters is therefore the validation, not the forecast.

THE THREE MODELS, AND WHY THESE THREE
-------------------------------------
`random_walk`   Tomorrow's price is today's price. The baseline, and the one
                to beat. On an efficient market it is famously hard to beat,
                which is exactly why it is the honest benchmark. A model that
                cannot beat it has demonstrated nothing.

`drift`         Random walk plus the average historical growth rate. The naive
                "carry on as before" forecast most people produce by eye.

`ar1_log`       AR(1) on log price, fitted by least squares. The simplest model
                with a genuinely different assumption: that price reverts
                toward a long-run level rather than wandering freely. If carbon
                prices are policy-anchored rather than random, this should win.

Deliberately no ARIMA, no gradient boosting, no neural network. With 2.4
effectively independent observations at this horizon (see
`effective_sample_size`), a more flexible model would fit the noise and its
apparent skill would be an artefact of overlapping folds. Choosing the simplest
model the data can support is the methodological point, not a limitation.

FREQUENCY AND TARGET
--------------------
Monthly mean prices, forecast 48 months ahead. Monthly because 223
observations give enough walk-forward folds to say anything, where 19 annual
observations would not. The mean rather than the month-end close because the
cost model consumes an annual average price, so the mean is the quantity the
study actually needs forecast.

THE CAVEAT THAT GOVERNS EVERY NUMBER OUT OF HERE
------------------------------------------------
Walk-forward folds at a 48-month horizon overlap almost completely. 115 folds
sound like 115 tests; they amount to 2.4 independent ones. Every error
metric here is computed over correlated samples and should be read as
indicative rather than as a precise estimate of out-of-sample accuracy.
`effective_sample_size` returns the honest number and it belongs beside any
metric quoted in the write-up.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import regulatory_constants as rc

HORIZON_MONTHS = 48
MIN_TRAIN_MONTHS = 60


# ---------------------------------------------------------------------------
# Models. Each takes a training series and returns a point forecast `horizon`
# steps ahead, so walk_forward can treat them interchangeably.
# ---------------------------------------------------------------------------


def random_walk(train: pd.Series, horizon: int) -> float:
    """The baseline: the last observed price, unchanged, forever."""
    return float(train.iloc[-1])


def drift(train: pd.Series, horizon: int) -> float:
    """Random walk with drift, extrapolating mean historical log growth."""
    log_returns = np.diff(np.log(train.to_numpy()))
    mu = float(np.mean(log_returns))
    return float(train.iloc[-1] * np.exp(mu * horizon))


def ar1_log(train: pd.Series, horizon: int) -> float:
    """AR(1) on log price, fitted by ordinary least squares.

    log p_t = c + phi * log p_{t-1} + e_t

    Iterated forward `horizon` steps. With phi below 1 the forecast decays
    toward the fitted long-run mean c / (1 - phi); at phi equal to 1 the model
    degenerates to the random walk, which is the honest thing for it to do.

    Fitted on logs rather than levels because the price is bounded below by
    zero and has varied by a factor of thirty over the sample, so additive
    errors would be wrong at both ends of that range.
    """
    y = np.log(train.to_numpy())
    x_lag, y_next = y[:-1], y[1:]
    design = np.column_stack([np.ones_like(x_lag), x_lag])
    c, phi = np.linalg.lstsq(design, y_next, rcond=None)[0]

    level = y[-1]
    for _ in range(horizon):
        level = c + phi * level
    return float(np.exp(level))


def linear_trend_log(train: pd.Series, horizon: int) -> float:
    """Ordinary least squares of log price on time, extrapolated forward.

    The most naive "draw a line through it" forecast. Included because it is
    what a reader assumes was done if the methodology does not say otherwise,
    so it is worth having its performance on record.
    """
    y = np.log(train.to_numpy())
    t = np.arange(len(y), dtype=float)
    intercept, slope = np.linalg.lstsq(np.column_stack([np.ones_like(t), t]), y, rcond=None)[0]
    return float(np.exp(intercept + slope * (len(y) - 1 + horizon)))


def _fit_ses(y: np.ndarray, grid: np.ndarray) -> tuple[float, float]:
    """Simple exponential smoothing, alpha chosen by one-step in-sample SSE."""
    best_alpha, best_sse, best_level = grid[0], np.inf, y[0]
    for alpha in grid:
        level, sse = y[0], 0.0
        for obs in y[1:]:
            sse += (obs - level) ** 2
            level = alpha * obs + (1 - alpha) * level
        if sse < best_sse:
            best_alpha, best_sse, best_level = alpha, sse, level
    return float(best_alpha), float(best_level)


def ses(train: pd.Series, horizon: int) -> float:
    """Exponentially weighted average of the past, held flat.

    A random walk that listens to more than the last observation. If recent
    prices are noisy around a level, this should beat the random walk. If the
    series genuinely wanders, it should not.
    """
    _, level = _fit_ses(np.log(train.to_numpy()), np.arange(0.1, 1.0, 0.1))
    return float(np.exp(level))


def damped_trend(train: pd.Series, horizon: int) -> float:
    """Holt's linear trend with damping, parameters by grid search.

    The model designed for exactly the failure the drift model shows here.
    A trend is estimated but multiplied by phi < 1 at each step ahead, so the
    extrapolation flattens out instead of compounding for four years. If the
    problem with `drift` is over-extrapolation rather than the trend itself,
    this is the model that fixes it.
    """
    y = np.log(train.to_numpy())
    best = (np.inf, y[-1], 0.0, 0.9)

    for alpha in (0.1, 0.3, 0.5, 0.7, 0.9):
        for beta in (0.05, 0.1, 0.3):
            for phi in (0.8, 0.9, 0.98):
                level, trend, sse = y[0], y[1] - y[0], 0.0
                for obs in y[1:]:
                    fitted = level + phi * trend
                    sse += (obs - fitted) ** 2
                    new_level = alpha * obs + (1 - alpha) * fitted
                    trend = beta * (new_level - level) + (1 - beta) * phi * trend
                    level = new_level
                if sse < best[0]:
                    best = (sse, level, trend, phi)

    _, level, trend, phi = best
    damping = sum(phi**i for i in range(1, horizon + 1))
    return float(np.exp(level + damping * trend))


def theta(train: pd.Series, horizon: int) -> float:
    """The Theta method, a benchmark that won the M3 forecasting competition.

    In its standard form it is exponential smoothing plus half the slope of the
    fitted linear trend. Included because it is the method a forecasting
    reviewer will ask why you did not try.
    """
    y = np.log(train.to_numpy())
    t = np.arange(len(y), dtype=float)
    _, slope = np.linalg.lstsq(np.column_stack([np.ones_like(t), t]), y, rcond=None)[0]
    _, level = _fit_ses(y, np.arange(0.1, 1.0, 0.1))
    return float(np.exp(level + 0.5 * slope * horizon))


MODELS = {
    "random_walk": random_walk,
    "drift": drift,
    "ar1_log": ar1_log,
    "linear_trend": linear_trend_log,
    "ses": ses,
    "damped_trend": damped_trend,
    "theta": theta,
}
BASELINE = "random_walk"

# The set fixed before any of it was run, so that reporting all seven is not a
# choice made after seeing which one won. With 2.4 independent windows at the
# four-year horizon, searching model space until something beats the baseline
# would find a winner whether or not one exists.
PRESPECIFIED = tuple(MODELS)


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------


def walk_forward(
    series: pd.Series,
    model,
    horizon: int = HORIZON_MONTHS,
    min_train: int = MIN_TRAIN_MONTHS,
) -> pd.DataFrame:
    """Expanding-window validation: fit on the past, predict, step, repeat.

    Never fits on data later than the origin, so no future information reaches
    a forecast. That is the whole point of validating this way rather than
    splitting at random, which on a time series would let the model see the
    future and would report accuracy that cannot be achieved in use.
    """
    rows = []
    for end in range(min_train, len(series) - horizon):
        train = series.iloc[:end]
        target_idx = end + horizon - 1
        rows.append(
            {
                "origin": series.index[end - 1],
                "target": series.index[target_idx],
                "actual": float(series.iloc[target_idx]),
                "predicted": model(train, horizon),
            }
        )
    out = pd.DataFrame(rows)
    out["log_error"] = np.log(out["actual"]) - np.log(out["predicted"])
    return out


def effective_sample_size(n_folds: int, horizon: int = HORIZON_MONTHS) -> float:
    """How many genuinely independent tests those folds amount to.

    Consecutive folds at this horizon share almost all of their target window,
    so they are not independent trials. Dividing by the horizon gives the
    number of non-overlapping windows the validation actually contains, which
    is the number a reader should have in mind when judging any metric here.
    """
    return round(n_folds / horizon, 1)


@dataclass(frozen=True)
class Score:
    """Out-of-sample performance of one model at one horizon."""

    model: str
    folds: int
    effective_folds: float
    mae_eur: float
    rmse_eur: float
    mape_pct: float
    median_abs_log_error: float
    skill_vs_baseline: float

    def beats_baseline(self) -> bool:
        return self.skill_vs_baseline > 0


def evaluate(results: pd.DataFrame, name: str, baseline: pd.DataFrame | None = None) -> Score:
    """Score a model, and express skill relative to the random walk.

    Skill is 1 - MSE_model / MSE_baseline on log errors. Zero means no better
    than the random walk, positive means better, negative means worse. It is
    reported on logs rather than levels so that a large miss at EUR 90 and a
    proportionally identical miss at EUR 5 count the same, which matters over a
    sample where the price varied thirtyfold.
    """
    err = results["log_error"].to_numpy()
    abs_eur = (results["actual"] - results["predicted"]).abs()

    if baseline is None:
        skill = 0.0
    else:
        mse_model = float(np.mean(err**2))
        mse_base = float(np.mean(baseline["log_error"].to_numpy() ** 2))
        skill = 1.0 - mse_model / mse_base

    return Score(
        model=name,
        folds=len(results),
        effective_folds=effective_sample_size(len(results)),
        mae_eur=float(abs_eur.mean()),
        rmse_eur=float(np.sqrt(((results["actual"] - results["predicted"]) ** 2).mean())),
        mape_pct=float((abs_eur / results["actual"]).mean() * 100),
        median_abs_log_error=float(np.median(np.abs(err))),
        skill_vs_baseline=float(skill),
    )


# ---------------------------------------------------------------------------
# Forecasting with intervals
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Forecast:
    """A point forecast with an interval calibrated on out-of-sample error.

    THE INTERVAL CAN EXCLUDE THE POINT FORECAST, and when it does that is a
    result rather than an error. It happens when the model was systematically
    biased over the validation sample, which every model here is: the EUA price
    rose roughly sixfold between 2017 and 2022, so a model fitted on any
    earlier window under-predicted almost every target it was asked about, and
    the empirical error distribution is therefore shifted well away from zero.

    `bias_log` reports that shift. Exponentiated it is the factor by which the
    model typically missed low. A large positive bias means the interval is
    doing the honest thing, saying the model's own history suggests its point
    forecast is too low, rather than politely centring itself on a number the
    evidence does not support.

    The reason not to simply de-bias the point forecast: the bias comes from
    one directional regime change, the Market Stability Reserve tightening
    supply from 2019. Correcting for it would assume that change repeats, which
    is a policy assumption dressed as a statistical one.
    """

    model: str
    target_date: pd.Timestamp
    point_eur: float
    lower_eur: float
    upper_eur: float
    interval_pct: int
    bias_log: float

    def width_ratio(self) -> float:
        """Upper over lower. A blunt measure of how much the forecast claims."""
        return self.upper_eur / self.lower_eur

    def bias_factor(self) -> float:
        """Typical multiplicative miss. Above 1 means it forecast too low."""
        return float(np.exp(self.bias_log))

    def contains(self, price: float) -> bool:
        return self.lower_eur <= price <= self.upper_eur


def forecast_with_interval(
    series: pd.Series,
    model,
    name: str,
    horizon: int = HORIZON_MONTHS,
    interval_pct: int = 80,
    min_train: int = MIN_TRAIN_MONTHS,
) -> Forecast:
    """Fit on everything, forecast ahead, and size the interval from real errors.

    The interval comes from the empirical distribution of the model's own
    walk-forward log errors, not from a parametric assumption about the noise.
    That is deliberate: an interval derived from an assumed normal distribution
    would be far too narrow here, because the errors are fat-tailed and the
    largest of them come from regime changes rather than from noise.

    An 80% interval is the default rather than 95% because with roughly three
    independent windows behind it, a 95% interval is an extrapolation into a
    tail the sample does not contain.
    """
    validation = walk_forward(series, model, horizon=horizon, min_train=min_train)
    errors = validation["log_error"].to_numpy()

    tail = (100 - interval_pct) / 200
    lo_q, hi_q = np.quantile(errors, [tail, 1 - tail])

    point = model(series, horizon)
    target = series.index[-1] + pd.DateOffset(months=horizon)

    return Forecast(
        model=name,
        target_date=target,
        point_eur=point,
        lower_eur=point * float(np.exp(lo_q)),
        upper_eur=point * float(np.exp(hi_q)),
        interval_pct=interval_pct,
        bias_log=float(np.median(errors)),
    )


# ---------------------------------------------------------------------------
# The comparison the study is actually placed to make
# ---------------------------------------------------------------------------


def horizon_sweep(
    series: pd.Series,
    horizons: tuple[int, ...] = (6, 12, 24, 36, 48),
    min_train: int = MIN_TRAIN_MONTHS,
) -> pd.DataFrame:
    """Skill of every model at every horizon, to locate where predictability dies.

    This is a more informative experiment than adding model classes. A price
    series can be genuinely forecastable over six months and completely
    unforecastable over four years, and if that is the pattern here it is worth
    knowing, because it says the problem is the horizon the study needs rather
    than the models it chose.

    Read the columns, not the maximum. At four years there are 2.4 independent
    windows, so the best cell in that column is close to meaningless on its
    own. At six months there are 26.2, and a result there is worth something.
    """
    rows = []
    for h in horizons:
        base = walk_forward(series, random_walk, horizon=h, min_train=min_train)
        for name in PRESPECIFIED:
            results = walk_forward(series, MODELS[name], horizon=h, min_train=min_train)
            score = evaluate(results, name, baseline=None if name == BASELINE else base)
            rows.append(
                {
                    "horizon_months": h,
                    "model": name,
                    "folds": score.folds,
                    "effective_folds": effective_sample_size(score.folds, h),
                    "mape_pct": round(score.mape_pct, 1),
                    "skill_vs_baseline": round(score.skill_vs_baseline, 3),
                }
            )
    return pd.DataFrame(rows)


def consensus_2030() -> dict:
    """The institutional forecast the cost model already uses, for comparison.

    Sourced in `regulatory_constants`: a GMK Center consensus aggregating
    Bloomberg, ABN Amro, Refinitiv, ICIS, S&P Global, Aurora and the Potsdam
    Institute, spanning EUR 80 to 147 with a central figure near EUR 126.
    """
    anchors = rc.EU_ETS_PRICE_SCENARIOS_BY_YEAR[2030]
    return {
        "low": anchors["low"],
        "central": anchors["medium"],
        "high": anchors["high"],
        "width_ratio": anchors["high"] / anchors["low"],
    }


def compare_with_consensus(forecast: Forecast) -> dict:
    """Set a fitted forecast against the institutional consensus.

    WHAT THIS CAN AND CANNOT SHOW, because the difference is easy to overstate
    and the write-up must not. 2030 has not happened, so this is not a test of
    which is more accurate and no such test is available. What it does show is
    whether the two are consistent, and how much more precise the consensus is
    than the price history by itself can justify.

    That second quantity is the finding. If the institutions publish a range
    several times narrower than the data supports, they are relying on
    knowledge the price series does not contain, namely the policy trajectory.
    Which is the study's own argument for using sourced anchors rather than a
    fitted forecast, arrived at from the opposite direction.
    """
    con = consensus_2030()
    return {
        "model": forecast.model,
        "model_point_eur": round(forecast.point_eur, 1),
        "model_interval_eur": (round(forecast.lower_eur, 1), round(forecast.upper_eur, 1)),
        "model_width_ratio": round(forecast.width_ratio(), 2),
        "consensus_central_eur": con["central"],
        "consensus_range_eur": (con["low"], con["high"]),
        "consensus_width_ratio": round(con["width_ratio"], 2),
        "consensus_inside_model_interval": forecast.contains(con["central"]),
        "model_interval_is_wider_by": round(forecast.width_ratio() / con["width_ratio"], 1),
        "model_bias_factor": round(forecast.bias_factor(), 2),
    }
