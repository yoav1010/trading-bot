import math

import pandas as pd
import pytest

from bot import indicators as ind


def test_sma_and_std_on_known_values():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert ind.sma(s, 5).iloc[-1] == pytest.approx(3.0)
    assert ind.rolling_std(s, 5).iloc[-1] == pytest.approx(math.sqrt(2.0))  # population std
    assert pd.isna(ind.sma(s, 5).iloc[3])  # not enough bars yet


def test_zscore_sign():
    s = pd.Series([10.0] * 19 + [5.0])
    assert ind.zscore(s, 20).iloc[-1] < 0


def test_true_range_uses_previous_close_gap(bars):
    df = bars([100, 110], spread=1)  # gap up: prev close 100, bar high 111, low 109
    assert ind.true_range(df).iloc[-1] == pytest.approx(11)


def test_atr_constant_range():
    df = pd.DataFrame({"high": [11.0] * 30, "low": [9.0] * 30, "close": [10.0] * 30})
    assert ind.atr(df, 14).iloc[-1] == pytest.approx(2.0)


def test_prior_high_excludes_current_bar():
    s = pd.Series([1.0, 2.0, 3.0, 10.0])
    assert ind.prior_high(s, 3).iloc[-1] == 3.0  # the 10 on the current bar is ignored


def test_no_lookahead_appending_future_bars_does_not_change_past(bars):
    df = bars(range(100, 160))
    longer = bars(list(range(100, 160)) + [500, 1, 900])
    for fn in (lambda d: ind.zscore(d["close"], 20), lambda d: ind.atr(d, 14),
               lambda d: ind.prior_high(d["high"], 20)):
        pd.testing.assert_series_equal(fn(df), fn(longer).iloc[: len(df)])
