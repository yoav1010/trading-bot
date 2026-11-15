"""Live paper-trading runner. One call = one check of every market.

Meant to run on a schedule (GitHub Actions every 15 minutes, or by hand):
    python -m bot.live

For each market it:
  1. fetches recent bars and drops the bar that is still forming,
  2. skips if there is no new closed bar since the last run (so a bar is never acted on twice),
  3. skips stocks while the market is closed,
  4. exits on a stop hit or a tripped circuit breaker,
  5. trails the stop, then asks the strategy for a signal on the latest closed bar,
  6. places a market order if needed (it fills near the next bar's open, as in the backtest),
  7. appends what it saw and did to logs/*.csv, which the dashboard reads.

State that must survive between runs (last bar seen, stop prices, equity peak) is kept in
state/bot_state.json. The broker is the source of truth for positions and equity.
"""

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from bot.backtest import BTC_BREAKOUT, SPY_MEAN_REVERSION, StrategySpec
from bot.config import RISK
from bot.indicators import atr
from bot.risk import initial_stop, position_size, stop_hit, trailing_stop
from bot.strategies.base import Action, Position

ROOT = Path(__file__).resolve().parents[1]
# GitHub Actions points these at a checkout of the `paper-log` branch, so the bot's
# frequent log commits stay out of the main code history.
STATE_FILE = Path(os.environ.get("BOT_STATE_FILE", ROOT / "state" / "bot_state.json"))
LOG_DIR = Path(os.environ.get("BOT_LOG_DIR", ROOT / "logs"))
MIN_BARS = 60


@dataclass(frozen=True)
class Market:
    symbol: str
    spec: StrategySpec
    minutes: int
    crypto: bool
    lookback_bars: int = 300


# Live parameters come from the most recent walk-forward fold (docs/walkforward_summary.md):
# SPY chose lookback=40, entry_z=2.0, stop=2 ATR in every fold; BTC's latest fold chose the defaults.
MARKETS = [
    Market("SPY", SPY_MEAN_REVERSION.with_params(lookback=40, entry_z=2.0, stop_atr_mult=2.0), 15, crypto=False),
    Market("BTC/USD", BTC_BREAKOUT, 60, crypto=True),
]

SIGNAL_FIELDS = ["run_time", "bar_time", "symbol", "position", "action", "reason", "close", "equity"]
TRADE_FIELDS = ["run_time", "symbol", "action", "qty", "ref_price", "stop", "reason", "order_id"]
EQUITY_FIELDS = ["run_time", "equity"]


# ------------------------------------------------------------------ state and logs

def load_state(path: Path = STATE_FILE) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"peak_equity": 0.0, "breaker_tripped": False, "markets": {}}


def save_state(state: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def append_row(name: str, fields: list[str], row: dict, log_dir: Path = LOG_DIR) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / name
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fields})


# ------------------------------------------------------------------ one market, one run

def run_market(broker, market: Market, state: dict, now: datetime, log_dir: Path = LOG_DIR) -> str:
    """Check one market once. Returns a one-line summary of what happened."""
    spec, symbol = market.spec, market.symbol
    run_time = now.isoformat(timespec="seconds")

    bars = broker.bars(symbol, market.minutes, market.lookback_bars, market.crypto)
    closed = bars[bars.index + pd.Timedelta(minutes=market.minutes) <= now]  # drop the forming bar
    if len(closed) < MIN_BARS:
        return f"{symbol}: only {len(closed)} closed bars, need {MIN_BARS}"

    mstate = state["markets"].setdefault(symbol, {"last_bar": None, "stop": None})
    bar_time = closed.index[-1]
    if mstate["last_bar"] == bar_time.isoformat():
        return f"{symbol}: no new bar since {bar_time:%Y-%m-%d %H:%M}"
    if not market.crypto and not broker.market_open():
        return f"{symbol}: market closed"
    mstate["last_bar"] = bar_time.isoformat()

    bar = closed.iloc[-1]
    holding = broker.holding(symbol)
    equity = broker.equity()
    bar_atr = atr(closed, RISK.atr_period).iloc[-1]

    def trade(action: str, qty: float, reason: str, order_id: str) -> None:
        append_row("trades.csv", TRADE_FIELDS, {
            "run_time": run_time, "symbol": symbol, "action": action, "qty": qty,
            "ref_price": float(bar["close"]), "stop": mstate["stop"], "reason": reason, "order_id": order_id,
        }, log_dir)

    def log_signal(action: str, reason: str, position: Position) -> None:
        append_row("signals.csv", SIGNAL_FIELDS, {
            "run_time": run_time, "bar_time": bar_time.isoformat(), "symbol": symbol,
            "position": position.value, "action": action, "reason": reason,
            "close": float(bar["close"]), "equity": equity,
        }, log_dir)

    # A position with no recorded stop (e.g. state was lost): rebuild it from the entry price.
    if holding.side != Position.FLAT and mstate["stop"] is None:
        mstate["stop"] = initial_stop(holding.avg_price, bar_atr, spec.stop_atr_mult, holding.side)

    # Stop hit on the latest closed bar, or circuit breaker tripped: get out.
    if holding.side != Position.FLAT:
        exit_reason = None
        if stop_hit(holding.side, bar["low"], bar["high"], mstate["stop"]):
            exit_reason = f"Stop hit at {mstate['stop']:.2f}"
        elif state["breaker_tripped"]:
            exit_reason = "Circuit breaker tripped"
        if exit_reason:
            order_id = broker.close(symbol)
            trade("exit", holding.qty, exit_reason, order_id)
            log_signal("exit", exit_reason, holding.side)
            mstate["stop"] = None
            return f"{symbol}: {exit_reason}, closed {holding.qty}"
        if spec.trailing and pd.notna(bar_atr):
            mstate["stop"] = trailing_stop(mstate["stop"], float(bar["close"]), bar_atr, spec.stop_atr_mult, holding.side)

    signal = spec.decide(spec.precompute(closed, spec.params).iloc[-1], holding.side, spec.params)
    log_signal(signal.action.value, signal.reason, holding.side)

    if signal.action == Action.EXIT and holding.side != Position.FLAT:
        order_id = broker.close(symbol)
        trade("exit", holding.qty, signal.reason, order_id)
        mstate["stop"] = None
        return f"{symbol}: exit - {signal.reason}"

    if signal.action in (Action.ENTER_LONG, Action.ENTER_SHORT) and holding.side == Position.FLAT:
        if state["breaker_tripped"] or pd.isna(bar_atr):
            return f"{symbol}: entry skipped (breaker tripped or ATR not ready)"
        price = float(bar["close"])
        qty = position_size(equity, price, bar_atr, spec.stop_atr_mult, spec.fractional, RISK)
        if qty <= 0:
            return f"{symbol}: entry skipped (size rounds to 0)"
        side = Position.LONG if signal.action == Action.ENTER_LONG else Position.SHORT
        order_id = broker.market_order(symbol, qty, buy=side == Position.LONG, crypto=market.crypto)
        mstate["stop"] = initial_stop(price, bar_atr, spec.stop_atr_mult, side)
        trade(signal.action.value, qty, signal.reason, order_id)
        return f"{symbol}: {signal.action.value} {qty} - {signal.reason}"

    return f"{symbol}: {signal.action.value} - {signal.reason}"


def update_breaker(state: dict, equity: float) -> None:
    """Track the equity peak; trip (and stay tripped) after a RISK.max_drawdown decline."""
    state["peak_equity"] = max(state.get("peak_equity", 0.0), equity)
    if state["peak_equity"] > 0 and equity <= state["peak_equity"] * (1 - RISK.max_drawdown):
        state["breaker_tripped"] = True


def run(broker, now: datetime | None = None, state_path: Path = STATE_FILE, log_dir: Path = LOG_DIR,
        markets: list[Market] = MARKETS) -> list[str]:
    now = now or datetime.now(timezone.utc)
    state = load_state(state_path)
    equity = broker.equity()
    update_breaker(state, equity)
    append_row("equity.csv", EQUITY_FIELDS, {"run_time": now.isoformat(timespec="seconds"), "equity": equity}, log_dir)

    summaries = []
    for market in markets:
        try:
            summaries.append(run_market(broker, market, state, now, log_dir))
        except Exception as exc:  # one market failing must not stop the other
            summaries.append(f"{market.symbol}: ERROR {type(exc).__name__}: {exc}")
    save_state(state, state_path)
    return summaries


def main() -> None:
    from bot.broker import AlpacaPaperBroker, load_dotenv

    from alpaca.common.exceptions import APIError

    load_dotenv(str(ROOT / ".env"))
    broker = AlpacaPaperBroker()
    try:
        broker.equity()
    except APIError as exc:
        if "unauthorized" in str(exc).lower() or "forbidden" in str(exc).lower():
            raise SystemExit("Alpaca rejected the API keys. Use PAPER trading keys (Key ID starts "
                             "with PK) from the Paper Trading dashboard, and check .env.") from None
        raise
    summaries = run(broker)
    for line in summaries:
        print(line)
    if any(": ERROR " in line for line in summaries):
        raise SystemExit(1)  # state and logs are already saved; a non-zero exit flags the run in CI


if __name__ == "__main__":
    main()
