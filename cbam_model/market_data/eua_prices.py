"""EU ETS allowance (EUA) daily futures prices, 2008 to present.

WHAT THIS SERIES IS
-------------------
ICE EUA futures, front-month continuous, EUR per tonne CO2e. Daily open, high,
low, settlement and volume.

"Continuous" is the caveat that matters for any modelling built on this. It is
not one contract. It is a chain of front-month contracts spliced together at
each expiry, so a small part of the day-to-day variation is roll effects
between contracts rather than a move in the price of carbon. For a study
forecasting annual price levels out to 2030 that is immaterial. For anything
reading daily returns it is not.

MODEL THE SETTLEMENT PRICE, NOT THE RANGE
-----------------------------------------
Use `price`. Treat `open`, `high` and `low` as unreliable before roughly 2019.
On 1,266 weekday rows, 26% of the series and heavily concentrated in 2009 to
2018, all four columns hold the same value, which is what a vendor writes when
it has a settlement price and no intraday range rather than what a market does.
Any feature built on the daily high-low spread would therefore be measuring the
vendor's record-keeping and would find a spurious structural break around 2019.
`data_quality_report` returns the counts.

PROVENANCE, AND THE HONEST CAVEAT
---------------------------------
Downloaded by hand from Investing.com on 13 August 2026, covering 4 February
2008 to 13 August 2026.

This is the weakest provenance of any input in the repository, and it is worth
being explicit about why rather than letting it pass. Every figure in `config/`
names a legal instrument that anyone can go and read. This one names a
commercial aggregator that does not publish its own methodology, redistributes
exchange data under its own terms, and offers no revision history. It cannot be
verified the way a regulatory constant can.

The reason it is here anyway: daily EUA history is a commercial product.
Checked on 13 August 2026 and found paywalled, bot-protected or chart-only at
ICE, EEX, the World Bank Carbon Pricing Dashboard, Sandbag and Ember. See
`docs/supervisor_meeting_2026-08-13_technical.md` for the search.

BEFORE THIS APPEARS IN THE DISSERTATION, replace it with the same series from
Refinitiv Datastream or Eikon through the university library if that access
exists. Identical data, licensed for academic use, citable. This file is the
unblocking copy, not the submission copy. If the swap happens, the only thing
that should need to change is the file this module reads.

WHAT IT IS FOR
--------------
Two possible consumers, neither of which is the cost model:

  - A fitted forecast of the carbon price, which would give the study a
    sampled distribution rather than three sourced scenario anchors.
  - Price coefficients for an optimisation formulation.

WHAT IT IS NOT FOR
------------------
Do not let a number from this file reach a headline corridor verdict. The three
carbon price scenarios in `config/scenarios.py` are sourced anchors and stay
the basis of every published result. Anything computed from this series is a
parallel extension, reported separately and labelled as such.
"""

from pathlib import Path

import pandas as pd

from ..validation.unit_checks import ContractViolation

RAW_PATH = Path(__file__).parent.parent / "data" / "market" / "eua_futures_daily_raw.csv"

# Sanity bounds on the EUA price in EUR/tCO2e. The series has genuinely traded
# under EUR 1 (the Phase I collapse in 2007, before this file starts) and over
# EUR 100 (February 2023), so the bounds are wide on purpose. They exist to
# catch a vendor changing units or currency, not to police market moves.
MIN_PLAUSIBLE_EUR = 0.01
MAX_PLAUSIBLE_EUR = 500.0

# The first date in the file. Phase II of the EU ETS opened in January 2008 and
# is the first phase with a functioning forward market, which is why the series
# starts here rather than at scheme launch in 2005.
EXPECTED_START = pd.Timestamp("2008-02-04")


def _parse_volume(value: object) -> float:
    """Turn Investing.com's abbreviated volume into a float.

    The vendor writes volume as "11.26K" or "1.03M", and as "-" when a day has
    no reported volume. Returning NaN for the latter rather than zero, because
    a missing report and a day of genuinely zero trading are different facts
    and only one of them is true here.
    """
    if not isinstance(value, str):
        return float("nan")
    text = value.strip().replace(",", "")
    if text in {"", "-"}:
        return float("nan")
    multipliers = {"K": 1e3, "M": 1e6, "B": 1e9}
    if text[-1].upper() in multipliers:
        return float(text[:-1]) * multipliers[text[-1].upper()]
    return float(text)


def _parse_price(value: object) -> float:
    """Strip the thousands separator the vendor inserts above 1,000."""
    if isinstance(value, str):
        return float(value.strip().replace(",", ""))
    return float(value)


def load_eua_daily(path: Path | None = None) -> pd.DataFrame:
    """Load and validate the daily EUA series, oldest first.

    Returns a frame indexed by date with columns price, open, high, low,
    volume and change_pct. Price is the settlement price in EUR/tCO2e.
    """
    source = Path(path) if path is not None else RAW_PATH
    if not source.exists():
        raise ContractViolation(
            f"EUA price file not found at {source}. It is downloaded by hand, "
            "not fetched, so it will not appear on a fresh clone. See this "
            "module's docstring for where it comes from."
        )

    # utf-8-sig strips the BOM the vendor writes ahead of the header, which
    # otherwise turns the first column name into '﻿Date' and makes every
    # lookup of "Date" fail with a message that does not mention encoding.
    raw = pd.read_csv(source, encoding="utf-8-sig")

    required = {"Date", "Price", "Open", "High", "Low", "Vol.", "Change %"}
    missing = required - set(raw.columns)
    if missing:
        raise ContractViolation(
            f"EUA price file is missing columns: {sorted(missing)}. The vendor "
            "changed their export format. Re-check the download before using it."
        )

    df = pd.DataFrame(
        {
            # The vendor exports US month/day/year regardless of locale.
            # Passing the format explicitly rather than letting pandas infer,
            # because an inferred parse would read 03/04/2020 as 4 March and be
            # silently wrong for every day of the month below the 13th.
            "date": pd.to_datetime(raw["Date"], format="%m/%d/%Y"),
            "price": raw["Price"].map(_parse_price),
            "open": raw["Open"].map(_parse_price),
            "high": raw["High"].map(_parse_price),
            "low": raw["Low"].map(_parse_price),
            "volume": raw["Vol."].map(_parse_volume),
            "change_pct": raw["Change %"].astype(str).str.rstrip("%").astype(float),
        }
    )

    df = df.sort_values("date").set_index("date")
    df = _drop_non_trading_days(df)
    return validate_eua_daily(df)


def _drop_non_trading_days(df: pd.DataFrame) -> pd.DataFrame:
    """Remove weekend rows, which the exchange cannot have produced.

    The download contains 42 Sunday rows, all between 2009 and 2014. Every one
    is a flat bar, open equal to high equal to low equal to settlement, with no
    reported volume, and the price is usually the previous Friday's close. ICE
    does not trade on a Sunday, so these are vendor filler rather than
    observations.

    They matter more than 42 rows out of 4,800 suggests. Each one sits between
    a Friday and a Monday and injects two fabricated returns where there should
    be one real one, so anything reading day-to-day changes gets 84 spurious
    moves, most of them zero, clustered in a single five-year window.

    Weekday flat bars are a separate case and are deliberately kept. There are
    1,266 of them, concentrated in 2009 to 2018, and they look like days where
    the vendor had a settlement price but no intraday range and filled the OHLC
    columns with the settlement. The settlement itself is plausible, so the row
    is real even though its high and low are not informative. See
    `data_quality_report` and the caveat on OHLC in the module docstring.
    """
    weekend = df.index.dayofweek >= 5
    return df[~weekend]


def validate_eua_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Fail loudly on anything that would make the series silently wrong."""
    if df.empty:
        raise ContractViolation("EUA price series is empty.")

    if df.index.has_duplicates:
        dupes = df.index[df.index.duplicated()].unique()[:5]
        raise ContractViolation(
            f"EUA series has duplicate dates, first few: {list(dupes)}. A "
            "duplicated day double-counts in any resample."
        )

    if not df.index.is_monotonic_increasing:
        raise ContractViolation("EUA series is not sorted oldest first.")

    if df["price"].isna().any():
        n = int(df["price"].isna().sum())
        raise ContractViolation(f"EUA series has {n} rows with no settlement price.")

    out_of_range = df[(df["price"] < MIN_PLAUSIBLE_EUR) | (df["price"] > MAX_PLAUSIBLE_EUR)]
    if not out_of_range.empty:
        raise ContractViolation(
            f"{len(out_of_range)} EUA prices fall outside "
            f"EUR {MIN_PLAUSIBLE_EUR} to {MAX_PLAUSIBLE_EUR}/tCO2e. Most likely "
            "the vendor switched currency or units. First offending date: "
            f"{out_of_range.index[0].date()}, price {out_of_range['price'].iloc[0]}."
        )

    # low <= high is a property of the data, not of the market. If it fails,
    # the columns have been transposed somewhere in the export.
    inverted = df[df["low"] > df["high"]]
    if not inverted.empty:
        raise ContractViolation(
            f"{len(inverted)} rows have low above high, first on "
            f"{inverted.index[0].date()}. High and low columns are transposed."
        )

    if df.index[0] != EXPECTED_START:
        raise ContractViolation(
            f"EUA series starts {df.index[0].date()}, expected "
            f"{EXPECTED_START.date()}. A different download window changes what "
            "any fitted model was trained on, so it is worth noticing."
        )

    return df


def data_quality_report(df: pd.DataFrame) -> dict:
    """Counts worth quoting in the methodology rather than leaving implicit.

    Every number a reader would want in order to judge whether the series is
    fit for what it is being asked to do, computed rather than asserted.
    """
    flat = (
        (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["price"])
    )
    return {
        "rows": len(df),
        "first_date": df.index[0].date().isoformat(),
        "last_date": df.index[-1].date().isoformat(),
        "trading_days_per_year_median": int(df.groupby(df.index.year).size().median()),
        "rows_missing_volume": int(df["volume"].isna().sum()),
        "flat_ohlc_rows": int(flat.sum()),
        "flat_ohlc_share": round(float(flat.mean()), 3),
        "weekend_rows": int((df.index.dayofweek >= 5).sum()),
        "price_min": float(df["price"].min()),
        "price_max": float(df["price"].max()),
    }


def to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Month-end resample: mean, last, and within-month volatility.

    Monthly rather than daily is the right frequency for this study. The
    forecast horizon is annual out to 2030, the cost model has one carbon price
    per year, and daily resolution contributes noise and roll effects to a
    question that does not turn on either.
    """
    monthly = df["price"].resample("ME").agg(["mean", "last", "std", "count"])
    monthly.columns = ["price_mean", "price_last", "price_std", "trading_days"]
    return monthly


def to_annual(df: pd.DataFrame) -> pd.DataFrame:
    """Calendar-year resample, the frequency the cost model actually consumes."""
    annual = df["price"].resample("YE").agg(["mean", "last", "min", "max", "count"])
    annual.columns = ["price_mean", "price_last", "price_min", "price_max", "trading_days"]
    annual.index = annual.index.year
    annual.index.name = "year"
    return annual
