"""Momentum breakout (used on BTC/USD, 1-hour bars). Long only.

Idea: crypto tends to keep running after it breaks out on heavy volume.
- Flat: close breaks above the highest high of the previous `lookback` bars AND
        volume is at least `volume_mult` x the previous bars' average -> go long.
- Long: exit if close breaks below the lowest low of the previous `lookback` bars.
        The ATR trailing stop is handled by the risk manager.
Long only because Alpaca does not support short-selling crypto.

Same precompute / decide / evaluate split as mean_reversion.py.
"""

import pandas as pd

from bot.config import BreakoutParams, BREAKOUT
from bot.indicators import prior_high, prior_low, prior_mean
from bot.strategies.base import Action, Position, Signal, check_bars


def precompute(df: pd.DataFrame, params: BreakoutParams = BREAKOUT) -> pd.DataFrame:
    return pd.DataFrame({
        "close": df["close"],
        "volume": df["volume"],
        "breakout_high": prior_high(df["high"], params.lookback),
        "breakdown_low": prior_low(df["low"], params.lookback),
        "avg_volume": prior_mean(df["volume"], params.lookback),
    }, index=df.index)


def decide(row, position: Position, params: BreakoutParams = BREAKOUT) -> Signal:
    if position == Position.SHORT:
        raise ValueError("breakout strategy is long only")
    price, volume = row["close"], row["volume"]
    high, low, avg_volume = row["breakout_high"], row["breakdown_low"], row["avg_volume"]
    if pd.isna(high) or pd.isna(low) or pd.isna(avg_volume):
        return Signal(Action.HOLD, f"Need {params.lookback + 1} bars")

    volume_ratio = volume / avg_volume if avg_volume > 0 else 0.0
    details = {"close": float(price), "breakout_high": float(high), "breakdown_low": float(low),
               "volume_ratio": float(volume_ratio)}

    if position == Position.FLAT:
        if price > high and volume_ratio >= params.volume_mult:
            return Signal(Action.ENTER_LONG,
                          f"Close {price:.2f} broke the {params.lookback}-bar high {high:.2f} "
                          f"on {volume_ratio:.1f}x average volume",
                          details)
        if price > high:
            return Signal(Action.HOLD,
                          f"Broke the high but volume was only {volume_ratio:.1f}x (need {params.volume_mult}x)",
                          details)
        return Signal(Action.HOLD, "No breakout", details)

    if price < low:
        return Signal(Action.EXIT, f"Close {price:.2f} broke below the {params.lookback}-bar low {low:.2f}", details)
    return Signal(Action.HOLD, "Trend intact", details)


def evaluate(df: pd.DataFrame, position: Position, params: BreakoutParams = BREAKOUT) -> Signal:
    """Signal for the last (most recent closed) bar in `df`."""
    check_bars(df)
    if position == Position.SHORT:
        raise ValueError("breakout strategy is long only")
    if len(df) < params.lookback + 1:
        return Signal(Action.HOLD, f"Need {params.lookback + 1} bars, have {len(df)}")
    return decide(precompute(df, params).iloc[-1], position, params)
