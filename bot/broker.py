"""Broker access: Alpaca PAPER trading only.

The bot never trades real money. AlpacaPaperBroker always connects with paper=True and
refuses to start if the environment asks for anything else. There is deliberately no
live-trading option in this codebase.

Every broker exposes the same small interface, so the live runner can be tested with
FakeBroker (see tests/) and no network or keys.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

from bot.strategies.base import Position


@dataclass(frozen=True)
class Holding:
    side: Position
    qty: float          # always positive
    avg_price: float


FLAT = Holding(Position.FLAT, 0.0, 0.0)


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env reader (KEY=VALUE lines). Existing environment variables win."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


class AlpacaPaperBroker:
    """Thin wrapper around alpaca-py, locked to the paper-trading endpoint."""

    def __init__(self) -> None:
        if os.environ.get("ALPACA_PAPER", "true").strip().lower() != "true":
            raise RuntimeError("This bot only supports paper trading. Set ALPACA_PAPER=true.")
        key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
        if not key or not secret:
            raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set (paper keys).")

        from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
        from alpaca.trading.client import TradingClient

        self._trading = TradingClient(key, secret, paper=True)
        self._stocks = StockHistoricalDataClient(key, secret)
        self._crypto = CryptoHistoricalDataClient(key, secret)

    # ---- account -------------------------------------------------------
    def equity(self) -> float:
        return float(self._trading.get_account().equity)

    def market_open(self) -> bool:
        return bool(self._trading.get_clock().is_open)

    def holding(self, symbol: str) -> Holding:
        from alpaca.common.exceptions import APIError
        try:
            pos = self._trading.get_open_position(symbol.replace("/", ""))
        except APIError:
            return FLAT  # Alpaca returns an error when there is no position
        qty = float(pos.qty)
        side = Position.LONG if qty > 0 else Position.SHORT
        return Holding(side, abs(qty), float(pos.avg_entry_price))

    # ---- data ----------------------------------------------------------
    def bars(self, symbol: str, minutes: int, lookback_bars: int, crypto: bool) -> pd.DataFrame:
        """Recent OHLCV bars, oldest first, UTC index. May include the still-forming bar."""
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        timeframe = TimeFrame(minutes, TimeFrameUnit.Minute) if minutes < 60 else TimeFrame(minutes // 60, TimeFrameUnit.Hour)
        # Ask for plenty of calendar time: stock bars only exist during market hours.
        span = timedelta(minutes=minutes * lookback_bars * (1 if crypto else 5))
        start = datetime.now(timezone.utc) - span
        if crypto:
            req = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=timeframe, start=start)
            raw = self._crypto.get_crypto_bars(req).df
        else:
            req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=timeframe, start=start, feed=DataFeed.IEX)
            raw = self._stocks.get_stock_bars(req).df
        df = raw.xs(symbol, level="symbol") if isinstance(raw.index, pd.MultiIndex) else raw
        df.index = pd.to_datetime(df.index, utc=True)
        return df[["open", "high", "low", "close", "volume"]].sort_index().tail(lookback_bars)

    # ---- orders --------------------------------------------------------
    def market_order(self, symbol: str, qty: float, buy: bool, crypto: bool) -> str:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        order = self._trading.submit_order(MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if buy else OrderSide.SELL,
            time_in_force=TimeInForce.GTC if crypto else TimeInForce.DAY,
        ))
        return str(order.id)

    def close(self, symbol: str) -> str:
        order = self._trading.close_position(symbol.replace("/", ""))
        return str(order.id)
