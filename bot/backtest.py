"""Event-driven backtester.

Order of events on each bar t:
  1. Fill any order signalled on the previous bar's close at THIS bar's open (+ slippage).
  2. Check whether the bar traded through the stop; if so, exit at the stop
     (or at the open, if price gapped past the stop).
  3. Mark the account to market at the close and update the drawdown circuit breaker.
  4. Move the trailing stop, for strategies that trail.
  5. Ask the strategy for a signal using only bars up to and including t.
     Any order it produces is filled on bar t + 1 (step 1), never on bar t.

Step 5 feeding step 1 of the NEXT bar is what keeps the backtest free of lookahead.
"""

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from bot import metrics
from bot.config import BREAKOUT, MEAN_REVERSION, RISK, RiskParams
from bot.indicators import atr
from bot.risk import DrawdownGuard, initial_stop, position_size, stop_hit, trailing_stop
from bot.strategies import mean_reversion, momentum_breakout
from bot.strategies.base import Action, Position, Signal


@dataclass(frozen=True)
class StrategySpec:
    name: str
    evaluate: Callable
    params: object
    stop_atr_mult: float
    trailing: bool           # trailing stop (True) or fixed stop (False)
    fractional: bool         # fractional quantities allowed (crypto) or whole shares
    periods_per_year: float  # bars per year, for annualizing the Sharpe ratio
    window: int              # bars the strategy needs to produce a signal


SPY_MEAN_REVERSION = StrategySpec(
    "SPY mean reversion", mean_reversion.evaluate, MEAN_REVERSION, MEAN_REVERSION.stop_atr_mult,
    trailing=False, fractional=False, periods_per_year=26 * 252, window=MEAN_REVERSION.lookback)

BTC_BREAKOUT = StrategySpec(
    "BTC breakout", momentum_breakout.evaluate, BREAKOUT, BREAKOUT.stop_atr_mult,
    trailing=True, fractional=True, periods_per_year=24 * 365, window=BREAKOUT.lookback + 1)


@dataclass
class BacktestResult:
    spec: StrategySpec
    equity: pd.Series
    benchmark: pd.Series   # buy and hold, same starting equity
    trades: pd.DataFrame
    stats: dict
    benchmark_stats: dict


TRADE_COLUMNS = ["entry_time", "exit_time", "side", "qty", "entry_price", "exit_price",
                 "pnl", "return_pct", "entry_reason", "exit_reason"]


def run(df: pd.DataFrame, spec: StrategySpec, initial_equity: float = 10_000.0,
        slippage: float = 0.0005, risk: RiskParams = RISK) -> BacktestResult:
    """Backtest one strategy on OHLCV bars (oldest first)."""
    if len(df) < spec.window + 2:
        raise ValueError(f"need at least {spec.window + 2} bars, got {len(df)}")

    atr_values = atr(df, risk.atr_period)
    guard = DrawdownGuard(max_drawdown=risk.max_drawdown)

    cash = initial_equity
    qty = 0.0                 # signed: positive long, negative short
    side = Position.FLAT
    stop = entry_price = 0.0
    entry_time = entry_reason = None
    pending: Signal | None = None
    trades, equity = [], []

    def close_position(price: float, when, reason: str) -> None:
        nonlocal cash, qty, side, stop
        fill = price * (1 - slippage) if side == Position.LONG else price * (1 + slippage)
        cash += qty * fill
        size = abs(qty)
        pnl = (fill - entry_price) * size if side == Position.LONG else (entry_price - fill) * size
        trades.append({
            "entry_time": entry_time, "exit_time": when, "side": side.value, "qty": size,
            "entry_price": entry_price, "exit_price": fill, "pnl": pnl,
            "return_pct": pnl / (entry_price * size), "entry_reason": entry_reason, "exit_reason": reason,
        })
        qty, side, stop = 0.0, Position.FLAT, 0.0

    for t in range(len(df)):
        bar = df.iloc[t]
        when = df.index[t]

        # 1. Fill the order signalled on the previous bar, at this bar's open.
        if pending is not None:
            if pending.action == Action.EXIT and side != Position.FLAT:
                close_position(bar["open"], when, pending.reason)
            elif pending.action in (Action.ENTER_LONG, Action.ENTER_SHORT) and side == Position.FLAT:
                new_side = Position.LONG if pending.action == Action.ENTER_LONG else Position.SHORT
                fill = bar["open"] * (1 + slippage) if new_side == Position.LONG else bar["open"] * (1 - slippage)
                signal_atr = atr_values.iloc[t - 1]  # the ATR known when the signal fired
                size = position_size(cash, fill, signal_atr, spec.stop_atr_mult, spec.fractional, risk)
                if size > 0:
                    side = new_side
                    qty = size if side == Position.LONG else -size
                    cash -= qty * fill
                    entry_price, entry_time, entry_reason = fill, when, pending.reason
                    stop = initial_stop(fill, signal_atr, spec.stop_atr_mult, side)
            pending = None

        # 2. Stop check inside the bar.
        if side != Position.FLAT and stop_hit(side, bar["low"], bar["high"], stop):
            exit_price = min(bar["open"], stop) if side == Position.LONG else max(bar["open"], stop)
            close_position(exit_price, when, f"Stop hit at {stop:.2f}")

        # 3. Mark to market and update the circuit breaker.
        value = cash + qty * bar["close"]
        equity.append(value)
        trading_allowed = guard.update(value)
        if not trading_allowed and side != Position.FLAT:
            pending = Signal(Action.EXIT, f"Circuit breaker: {guard.drawdown:.1%} drawdown from peak")
            continue

        # 4. Trail the stop.
        bar_atr = atr_values.iloc[t]
        if side != Position.FLAT and spec.trailing and pd.notna(bar_atr):
            stop = trailing_stop(stop, bar["close"], bar_atr, spec.stop_atr_mult, side)

        # 5. New signal from closed bars only; it fills on the next bar.
        if t + 1 >= len(df) or t + 1 < spec.window:
            continue
        signal = spec.evaluate(df.iloc[t + 1 - spec.window: t + 1], side, spec.params)
        is_entry = signal.action in (Action.ENTER_LONG, Action.ENTER_SHORT)
        if signal.action == Action.HOLD or (is_entry and (not trading_allowed or pd.isna(bar_atr))):
            continue
        pending = signal

    # Close anything still open at the last close so the stats include it.
    if side != Position.FLAT:
        close_position(df["close"].iloc[-1], df.index[-1], "End of backtest")
        equity[-1] = cash

    equity_series = pd.Series(equity, index=df.index, name="strategy")
    benchmark = (initial_equity * df["close"] / df["close"].iloc[0]).rename("buy_and_hold")
    trades_df = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    return BacktestResult(
        spec=spec,
        equity=equity_series,
        benchmark=benchmark,
        trades=trades_df,
        stats=metrics.summarize(equity_series, trades_df, spec.periods_per_year),
        benchmark_stats={
            "total_return": metrics.total_return(benchmark),
            "max_drawdown": metrics.max_drawdown(benchmark),
            "sharpe": metrics.sharpe(benchmark, spec.periods_per_year),
        },
    )
