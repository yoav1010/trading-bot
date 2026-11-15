"""Mean reversion (used on SPY, 15-minute bars).

Idea: an index that stretches far from its recent average tends to snap back.
- Flat:  close >= entry_z std devs BELOW the mean -> go long; ABOVE -> go short.
- Long:  exit once close is back at or above the mean.
- Short: exit once close is back at or below the mean.
Stops are handled by the risk manager, not here.
"""

import pandas as pd

from bot.config import MeanReversionParams, MEAN_REVERSION
from bot.indicators import sma, rolling_std
from bot.strategies.base import Action, Position, Signal, check_bars


def evaluate(df: pd.DataFrame, position: Position, params: MeanReversionParams = MEAN_REVERSION) -> Signal:
    """Signal for the last (most recent closed) bar in `df`."""
    check_bars(df)
    if len(df) < params.lookback:
        return Signal(Action.HOLD, f"Need {params.lookback} bars, have {len(df)}")

    close = df["close"]
    mean = sma(close, params.lookback).iloc[-1]
    std = rolling_std(close, params.lookback).iloc[-1]
    price = close.iloc[-1]
    if std == 0 or pd.isna(std):
        return Signal(Action.HOLD, "No price movement in the lookback window")

    z = (price - mean) / std
    details = {"close": float(price), "mean": float(mean), "std": float(std), "z": float(z)}

    if position == Position.FLAT:
        if z <= -params.entry_z:
            return Signal(Action.ENTER_LONG,
                          f"Close {price:.2f} is {abs(z):.2f} std devs below the {params.lookback}-bar mean {mean:.2f}",
                          details)
        if z >= params.entry_z:
            return Signal(Action.ENTER_SHORT,
                          f"Close {price:.2f} is {z:.2f} std devs above the {params.lookback}-bar mean {mean:.2f}",
                          details)
        return Signal(Action.HOLD, f"z = {z:.2f}, inside +/-{params.entry_z}", details)

    if position == Position.LONG and price >= mean:
        return Signal(Action.EXIT, f"Close {price:.2f} reverted to the mean {mean:.2f}", details)
    if position == Position.SHORT and price <= mean:
        return Signal(Action.EXIT, f"Close {price:.2f} reverted to the mean {mean:.2f}", details)
    return Signal(Action.HOLD, f"Waiting for reversion (z = {z:.2f})", details)
