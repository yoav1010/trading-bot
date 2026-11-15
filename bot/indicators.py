"""Technical indicators on OHLCV DataFrames.

Every function returns a Series aligned with the input index. Values at bar t use
only bars 0..t (no lookahead), except where a function says it uses prior bars only.
"""

import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average over the last `period` bars."""
    return series.rolling(period, min_periods=period).mean()


def rolling_std(series: pd.Series, period: int) -> pd.Series:
    """Population standard deviation over the last `period` bars."""
    return series.rolling(period, min_periods=period).std(ddof=0)


def zscore(series: pd.Series, period: int) -> pd.Series:
    """How many standard deviations each value is from its moving average."""
    return (series - sma(series, period)) / rolling_std(series, period)


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average with the standard smoothing 2 / (period + 1)."""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    """max(high - low, |high - previous close|, |low - previous close|)."""
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average true range using Wilder's smoothing (alpha = 1 / period)."""
    return true_range(df).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def prior_high(series: pd.Series, period: int) -> pd.Series:
    """Highest value of the `period` bars BEFORE each bar (excludes the current bar)."""
    return series.shift(1).rolling(period, min_periods=period).max()


def prior_low(series: pd.Series, period: int) -> pd.Series:
    """Lowest value of the `period` bars BEFORE each bar (excludes the current bar)."""
    return series.shift(1).rolling(period, min_periods=period).min()


def prior_mean(series: pd.Series, period: int) -> pd.Series:
    """Average of the `period` bars BEFORE each bar (excludes the current bar)."""
    return series.shift(1).rolling(period, min_periods=period).mean()
