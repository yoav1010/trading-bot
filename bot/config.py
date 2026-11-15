"""Strategy and risk parameters in one place, so backtests and live runs use the same numbers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MeanReversionParams:
    symbol: str = "SPY"
    timeframe_minutes: int = 15
    lookback: int = 20          # bars for the moving average and standard deviation
    entry_z: float = 1.5        # enter when price is this many std devs from the mean
    stop_atr_mult: float = 1.0  # stop distance in ATRs (1 ATR against us = 1% of equity)


@dataclass(frozen=True)
class BreakoutParams:
    symbol: str = "BTC/USD"
    timeframe_minutes: int = 60
    lookback: int = 20          # bars for the breakout high/low and average volume
    volume_mult: float = 1.5    # breakout bar volume must be >= this x average volume
    stop_atr_mult: float = 2.0  # trailing stop distance in ATRs


@dataclass(frozen=True)
class RiskParams:
    risk_per_trade: float = 0.01   # fraction of equity lost if the stop is hit
    atr_period: int = 14
    max_position_pct: float = 0.25 # never put more than 25% of equity in one position
    max_drawdown: float = 0.10     # circuit breaker: stop trading after a 10% drop from peak


MEAN_REVERSION = MeanReversionParams()
BREAKOUT = BreakoutParams()
RISK = RiskParams()
