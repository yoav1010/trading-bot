import csv
from datetime import timedelta

import pandas as pd
import pytest

from bot import live
from bot.broker import FLAT, AlpacaPaperBroker, Holding
from bot.strategies.base import Position

from conftest import make_bars


class FakeBroker:
    """In-memory stand-in for AlpacaPaperBroker: same methods, no network."""

    def __init__(self, bars: pd.DataFrame, equity: float = 100_000.0, is_open: bool = True):
        self._bars, self._equity, self.is_open = bars, equity, is_open
        self.holdings: dict[str, Holding] = {}
        self.orders: list[tuple] = []

    def equity(self):
        return self._equity

    def market_open(self):
        return self.is_open

    def holding(self, symbol):
        return self.holdings.get(symbol, FLAT)

    def bars(self, symbol, minutes, lookback_bars, crypto):
        return self._bars

    def market_order(self, symbol, qty, buy, crypto):
        self.orders.append(("buy" if buy else "sell", symbol, qty))
        price = float(self._bars["close"].iloc[-1])
        self.holdings[symbol] = Holding(Position.LONG if buy else Position.SHORT, qty, price)
        return f"order-{len(self.orders)}"

    def close(self, symbol):
        self.orders.append(("close", symbol, self.holdings[symbol].qty))
        self.holdings.pop(symbol)
        return f"order-{len(self.orders)}"


SPY = live.Market("SPY", live.SPY_MEAN_REVERSION, 15, crypto=False)  # default params: lookback 20, z 1.5


def spy_bars(last_close: float, n: int = 80):
    closes = [100.0, 101.0] * (n // 2)
    closes[-1] = last_close
    df = make_bars(closes)
    df.index = pd.date_range("2026-11-16 14:30", periods=n, freq="15min", tz="UTC")
    return df


def after(df, bars_closed=1):
    """A time just after the last `bars_closed` bars have finished."""
    return df.index[-1] + timedelta(minutes=15 * bars_closed, seconds=5)


@pytest.fixture
def paths(tmp_path):
    return {"state_path": tmp_path / "state.json", "log_dir": tmp_path / "logs"}


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_entry_places_order_sets_stop_and_logs_reason(paths):
    df = spy_bars(97.0)
    broker = FakeBroker(df)
    out = live.run(broker, now=after(df), markets=[SPY], **paths)
    assert broker.orders[0][0] == "buy"
    assert "enter_long" in out[0]
    state = live.load_state(paths["state_path"])
    assert state["markets"]["SPY"]["stop"] < 97.0
    trades = read(paths["log_dir"] / "trades.csv")
    assert trades[0]["action"] == "enter_long" and "below" in trades[0]["reason"]


def test_forming_bar_is_ignored(paths):
    df = spy_bars(97.0)
    broker = FakeBroker(df)
    live.run(broker, now=df.index[-1] + timedelta(minutes=5), markets=[SPY], **paths)  # last bar still open
    assert broker.orders == []


def test_same_bar_is_never_acted_on_twice(paths):
    df = spy_bars(97.0)
    broker = FakeBroker(df)
    live.run(broker, now=after(df), markets=[SPY], **paths)
    broker.holdings.clear()  # even if the position disappeared, the bar was already handled
    out = live.run(broker, now=after(df) + timedelta(minutes=3), markets=[SPY], **paths)
    assert len(broker.orders) == 1
    assert "no new bar" in out[0]


def test_stock_skipped_when_market_closed(paths):
    df = spy_bars(97.0)
    broker = FakeBroker(df, is_open=False)
    out = live.run(broker, now=after(df), markets=[SPY], **paths)
    assert broker.orders == [] and "market closed" in out[0]


def test_stop_hit_closes_position(paths):
    df = spy_bars(97.0)
    broker = FakeBroker(df)
    live.run(broker, now=after(df), markets=[SPY], **paths)
    crash = pd.concat([df, make_bars([90.0])])
    crash.index = list(df.index) + [df.index[-1] + timedelta(minutes=15)]
    broker._bars = crash
    out = live.run(broker, now=after(crash), markets=[SPY], **paths)
    assert broker.orders[-1][0] == "close"
    assert "Stop hit" in out[0]
    assert live.load_state(paths["state_path"])["markets"]["SPY"]["stop"] is None


def test_circuit_breaker_blocks_entries(paths):
    df = spy_bars(97.0)
    paths["state_path"].write_text('{"peak_equity": 200000, "breaker_tripped": false, "markets": {}}')
    broker = FakeBroker(df, equity=100_000.0)  # 50% below the recorded peak
    out = live.run(broker, now=after(df), markets=[SPY], **paths)
    assert broker.orders == []
    assert live.load_state(paths["state_path"])["breaker_tripped"] is True
    assert "entry skipped" in out[0]


def test_one_market_error_does_not_stop_others(paths):
    class Broken(FakeBroker):
        def bars(self, symbol, *a):
            if symbol == "BTC/USD":
                raise ConnectionError("API down")
            return super().bars(symbol, *a)

    df = spy_bars(97.0)
    btc = live.Market("BTC/USD", live.BTC_BREAKOUT, 60, crypto=True)
    out = live.run(Broken(df), now=after(df), markets=[btc, SPY], **paths)
    assert "ERROR" in out[0] and "enter_long" in out[1]


def test_refuses_anything_but_paper(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER", "false")
    monkeypatch.setenv("ALPACA_API_KEY", "x")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "y")
    with pytest.raises(RuntimeError, match="paper"):
        AlpacaPaperBroker()


def test_requires_keys(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="KEY"):
        AlpacaPaperBroker()
