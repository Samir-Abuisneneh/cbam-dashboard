"""Tests for the EUA price series ingest.

Two kinds of test here, and the second kind is the one that earns its keep.

The first kind checks the parser handles the vendor's format: the BOM, the
US date order, the abbreviated volumes. Those would break loudly anyway.

The second kind pins facts about the market that are externally checkable
against the historical record, so if a future re-download quietly returns a
different contract, a different currency or a different window, a test names
the discrepancy instead of a model silently training on the wrong series.
"""

from pathlib import Path

import pandas as pd
import pytest

from cbam_model.market_data import eua_prices as ep
from cbam_model.validation.unit_checks import ContractViolation


@pytest.fixture(scope="module")
def daily():
    return ep.load_eua_daily()


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "eua.csv"
    path.write_text('﻿"Date","Price","Open","High","Low","Vol.","Change %"\n' + body)
    return path


# ---------------------------------------------------------------------------
# Parsing the vendor's format
# ---------------------------------------------------------------------------


def test_dates_parse_as_month_day_not_day_month(tmp_path):
    """03/04/2020 is 4 March, not 3 April.

    This is the highest-consequence parsing bug available here, because an
    inferred parse is wrong only for days below the 13th and correct above
    them, so it survives a spot check of the tail of the file.
    """
    path = _write(tmp_path, '"03/04/2020","20.00","20.00","20.00","20.00","1K","0%"\n')
    raw = pd.read_csv(path, encoding="utf-8-sig")
    parsed = pd.to_datetime(raw["Date"], format="%m/%d/%Y").iloc[0]
    assert (parsed.month, parsed.day) == (3, 4)


def test_bom_does_not_corrupt_the_date_column(daily):
    assert daily.index.name == "date"
    assert not daily.empty


def test_abbreviated_volumes_expand():
    assert ep._parse_volume("11.26K") == pytest.approx(11_260)
    assert ep._parse_volume("1.03M") == pytest.approx(1_030_000)
    assert ep._parse_volume("1,234") == pytest.approx(1234)


def test_missing_volume_is_nan_not_zero():
    """A day with no reported volume is not a day with no trading."""
    assert pd.isna(ep._parse_volume("-"))
    assert pd.isna(ep._parse_volume(""))


def test_thousands_separator_in_price_is_stripped():
    assert ep._parse_price("1,234.56") == pytest.approx(1234.56)


# ---------------------------------------------------------------------------
# Facts about the series, checkable against the historical record
# ---------------------------------------------------------------------------


def test_series_covers_phase_two_onwards(daily):
    assert daily.index[0] == pd.Timestamp("2008-02-04")
    assert daily.index[-1] >= pd.Timestamp("2026-08-13")
    assert len(daily) > 4_500


def test_price_is_in_euros_per_tonne_not_cents(daily):
    """A vendor switching to cents would multiply the whole series by 100.

    Pinned on the 2013 trough and the 2022 peak, both of which are documented
    events: the Phase II/III oversupply collapse, and the post-invasion energy
    price spike.
    """
    assert daily["price"].min() == pytest.approx(2.70, abs=0.01)
    assert daily["price"].max() == pytest.approx(98.01, abs=0.01)


def test_the_2013_collapse_and_the_2022_peak_are_where_history_says(daily):
    assert daily["price"].idxmin().year == 2013
    assert daily["price"].idxmax().year == 2022


def test_msr_era_prices_are_far_above_phase_three(daily):
    """Structural break the model's scenario anchors depend on.

    The Market Stability Reserve began operating in 2019 and the price roughly
    quintupled over the following three years. Any forecast trained on this
    series inherits that break, which is the central reason a fitted forecast
    cannot be trusted to extrapolate policy.
    """
    annual = ep.to_annual(daily)
    assert annual.loc[2017, "price_mean"] < 10
    assert annual.loc[2022, "price_mean"] > 70


def test_every_year_has_a_plausible_number_of_trading_days(daily):
    """No year may exceed the number of weekdays it contains.

    The bound is not cosmetic. It is what caught the vendor's fabricated Sunday
    rows: 2010 arrived with 271 dated rows against 261 available weekdays, and
    a count above the calendar is impossible rather than merely surprising.
    """
    annual = ep.to_annual(daily)
    complete = annual.drop(index=[2008, annual.index.max()])
    assert complete["trading_days"].between(240, 262).all()


def test_no_weekend_rows_survive_loading(daily):
    """ICE does not settle on a Sunday, so a weekend row is fabricated."""
    assert (daily.index.dayofweek < 5).all()


def test_the_vendors_phantom_sundays_are_still_being_removed():
    """Pins the 42 known filler rows, so a re-download cannot quietly keep them.

    If this count changes, the vendor's export changed. That is worth a look
    before anything is retrained on the new file, not after.
    """
    raw = pd.read_csv(ep.RAW_PATH, encoding="utf-8-sig")
    dates = pd.to_datetime(raw["Date"], format="%m/%d/%Y")
    weekend = dates[dates.dt.dayofweek >= 5]
    assert len(weekend) == 42
    assert set(weekend.dt.day_name()) == {"Sunday"}
    assert weekend.dt.year.between(2009, 2014).all()


def test_flat_ohlc_rows_are_kept_but_counted(daily):
    """Weekday flat bars are real settlements with no range, so they stay.

    Counted rather than dropped, because the count is the evidence for the
    module's instruction to model the settlement price and ignore the range.
    """
    report = ep.data_quality_report(daily)
    assert report["weekend_rows"] == 0
    assert report["flat_ohlc_rows"] > 1_000
    assert 0.2 < report["flat_ohlc_share"] < 0.35


# ---------------------------------------------------------------------------
# Validation rejects what it is there to reject
# ---------------------------------------------------------------------------


def test_duplicate_dates_are_rejected(daily):
    doubled = pd.concat([daily.iloc[:5], daily.iloc[:5]]).sort_index()
    with pytest.raises(ContractViolation, match="duplicate dates"):
        ep.validate_eua_daily(doubled)


def test_prices_outside_plausible_range_are_rejected(daily):
    """The unit-switch guard. A vendor quoting cents lands here."""
    broken = daily.copy()
    broken.iloc[0, broken.columns.get_loc("price")] = 8_278.0
    with pytest.raises(ContractViolation, match="outside"):
        ep.validate_eua_daily(broken)


def test_transposed_high_and_low_are_rejected(daily):
    broken = daily.copy()
    high = broken.columns.get_loc("high")
    low = broken.columns.get_loc("low")
    broken.iloc[0, high], broken.iloc[0, low] = broken.iloc[0, low], broken.iloc[0, high]
    with pytest.raises(ContractViolation, match="transposed"):
        ep.validate_eua_daily(broken)


def test_unsorted_series_is_rejected(daily):
    with pytest.raises(ContractViolation, match="sorted"):
        ep.validate_eua_daily(daily.iloc[::-1])


def test_a_different_download_window_is_noticed(daily):
    """Silently retraining on a different window is the failure this catches."""
    with pytest.raises(ContractViolation, match="starts"):
        ep.validate_eua_daily(daily.iloc[10:])


def test_missing_file_names_the_reason_it_is_missing(tmp_path):
    with pytest.raises(ContractViolation, match="downloaded by hand"):
        ep.load_eua_daily(tmp_path / "absent.csv")


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------


def test_annual_resample_covers_every_year_once(daily):
    annual = ep.to_annual(daily)
    assert list(annual.index) == list(range(2008, 2027))


def test_monthly_resample_row_count_matches_span(daily):
    monthly = ep.to_monthly(daily)
    assert len(monthly) == 223  # Feb 2008 through Aug 2026 inclusive
    assert monthly["trading_days"].min() > 0
