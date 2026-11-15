"""Momentum breakout (used on BTC/USD, 1-hour bars). Long only.

Idea: crypto tends to keep running after it breaks out on heavy volume.
- Flat: close breaks above the highest high of the previous `lookback` bars AND
        volume is at least `volume_mult` x the previous bars' average -> go long.
- Long: exit if close breaks below the lowest low of the previous `lookback` bars.
        The 2x ATR trailing stop is handled by the risk manager.
Long only because Alpaca does not support short-selling crypto.
"""

import pandas as pd

from bot.config import BreakoutParams, BREAKOUT
from bot.indicators import prior_high, prior_low, prior_mean
from bot.strategies.base import Action, Position, Signal, check_bars


def evaluate(df: pd.DataFrame, position: Position, params: BreakoutParams = BREAKOUT) -> Signal:
    """Signal for the last (most recent closed) bar in `df`."""
    check_bars(df)
    if len(df) < params.lookback + 1:
        return Signal(Action.HOLD, f"Need {params.lookback + 1} bars, have {len(df)}")
    if position == Position.SHORT:
        raise ValueError("breakout strategy is long only")

    price = df["close"].iloc[-1]
    volume = df["volume"].iloc[-1]
    high = prior_high(df["high"], params.lookback).iloc[-1]
    low = prior_low(df["low"], params.lookback).iloc[-1]
    avg_volume = prior_mean(df["volume"], params.lookback).iloc[-1]
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
