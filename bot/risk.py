"""Risk management: position sizing, stops and the drawdown circuit breaker.

Sizing rule: put the stop `stop_atr_mult` ATRs away, then size the position so that
getting stopped out loses exactly `risk_per_trade` of equity. A quiet market (small ATR)
gets a bigger position and a volatile one gets a smaller position, so the dollar risk
per trade stays the same.
"""

import math
from dataclasses import dataclass

from bot.config import RISK, RiskParams
from bot.strategies.base import Position


def position_size(equity: float, price: float, atr_value: float, stop_atr_mult: float,
                  fractional: bool = False, params: RiskParams = RISK) -> float:
    """Quantity to trade. Returns 0 when the inputs don't allow a safe position."""
    if equity <= 0 or price <= 0 or atr_value <= 0 or stop_atr_mult <= 0:
        return 0.0
    risk_dollars = equity * params.risk_per_trade
    stop_distance = atr_value * stop_atr_mult
    qty = risk_dollars / stop_distance
    max_qty = equity * params.max_position_pct / price  # cap on capital in one position
    qty = min(qty, max_qty)
    if not fractional:
        qty = math.floor(qty)
    return float(qty)


def initial_stop(entry_price: float, atr_value: float, stop_atr_mult: float, side: Position) -> float:
    """Stop price `stop_atr_mult` ATRs against the entry."""
    distance = atr_value * stop_atr_mult
    if side == Position.LONG:
        return entry_price - distance
    if side == Position.SHORT:
        return entry_price + distance
    raise ValueError("a stop needs a long or short side")


def trailing_stop(current_stop: float, price: float, atr_value: float, stop_atr_mult: float,
                  side: Position) -> float:
    """Move the stop toward price as the trade gains. Never moves it further away."""
    distance = atr_value * stop_atr_mult
    if side == Position.LONG:
        return max(current_stop, price - distance)
    if side == Position.SHORT:
        return min(current_stop, price + distance)
    raise ValueError("a stop needs a long or short side")


def stop_hit(side: Position, bar_low: float, bar_high: float, stop: float) -> bool:
    """True if the bar traded through the stop."""
    if side == Position.LONG:
        return bar_low <= stop
    if side == Position.SHORT:
        return bar_high >= stop
    return False


@dataclass
class DrawdownGuard:
    """Circuit breaker: once equity falls `max_drawdown` below its peak, stop trading."""
    max_drawdown: float = RISK.max_drawdown
    peak: float = 0.0
    last: float = 0.0
    tripped: bool = False

    def update(self, equity: float) -> bool:
        """Record the latest equity. Returns True if trading is still allowed."""
        self.last = equity
        self.peak = max(self.peak, equity)
        if self.peak > 0 and equity <= self.peak * (1 - self.max_drawdown):
            self.tripped = True  # stays tripped until a human resets it
        return not self.tripped

    @property
    def drawdown(self) -> float:
        """Current decline from the peak, as a fraction (0.05 = 5%)."""
        return 0.0 if self.peak == 0 else 1 - self.last / self.peak
