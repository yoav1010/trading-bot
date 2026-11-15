import pandas as pd
import pytest

from bot import backtest, metrics
from bot.config import RiskParams

from conftest import make_bars

FLAT_20 = [100.0, 101.0] * 10  # mean 100.5, std 0.5
NO_DD = RiskParams(max_drawdown=0.99)


def timed(df):
    df.index = pd.date_range("2026-01-05 09:30", periods=len(df), freq="15min")
    return df


def run_spy(closes, **kw):
    df = timed(make_bars(closes))
    return df, backtest.run(df, backtest.SPY_MEAN_REVERSION, slippage=0.0, risk=kw.pop("risk", NO_DD), **kw)


def test_signal_on_last_bar_is_never_traded():
    _, res = run_spy([100.5] + FLAT_20 + [97.0])  # the only signal fires on the final bar
    assert res.trades.empty


def test_entry_fills_at_next_bar_open():
    df, res = run_spy(FLAT_20 + [97.0, 97.2, 97.4, 101.0, 101.0])
    first = res.trades.iloc[0]
    assert first["side"] == "long"
    assert first["entry_time"] == df.index[21]               # signal on bar 20, filled on bar 21
    assert first["entry_price"] == pytest.approx(df["open"].iloc[21])
    assert "below" in first["entry_reason"]


def test_exit_when_price_reverts():
    df, res = run_spy(FLAT_20 + [97.0, 97.2, 97.4, 101.0, 101.0])
    first = res.trades.iloc[0]
    assert "reverted" in first["exit_reason"]
    assert first["exit_time"] == df.index[24]                 # reversion seen on bar 23, exit on bar 24 open
    assert first["pnl"] > 0


def test_stop_loss_exits_at_stop_or_gap():
    df, res = run_spy(FLAT_20 + [97.0, 97.2, 80.0, 80.0])  # crash through the stop
    first = res.trades.iloc[0]
    assert first["exit_reason"].startswith("Stop hit")
    assert first["exit_time"] == df.index[22]
    assert first["exit_price"] <= first["entry_price"]


def test_equity_change_equals_sum_of_trade_pnl():
    _, res = run_spy(FLAT_20 + [97.0, 97.2, 97.4, 101.0, 101.0, 104.0, 103.0, 100.5, 100.0])
    assert res.equity.iloc[-1] - 10_000 == pytest.approx(res.trades["pnl"].sum())


def test_benchmark_is_buy_and_hold():
    df, res = run_spy(FLAT_20 + [97.0, 99.0])
    assert res.benchmark.iloc[-1] == pytest.approx(10_000 * 99.0 / df["close"].iloc[0])


def test_circuit_breaker_blocks_new_entries():
    tight = RiskParams(max_drawdown=0.001)
    _, res = run_spy(FLAT_20 + [97.0, 97.2, 80.0, 80.0] + FLAT_20 + [97.0, 97.0, 97.0], risk=tight)
    assert len(res.trades) == 1  # the stop-out trips the breaker, so the second setup is ignored


def test_btc_breakout_runs_long_only():
    closes = [100.0] * 20 + [110.0, 112.0, 115.0, 100.0, 99.0]
    volumes = [100.0] * 20 + [300.0, 100.0, 100.0, 100.0, 100.0]
    df = make_bars(closes, volumes)
    df.index = pd.date_range("2026-01-01", periods=len(df), freq="1h")
    res = backtest.run(df, backtest.BTC_BREAKOUT, slippage=0.0, risk=NO_DD)
    assert len(res.trades) >= 1
    assert set(res.trades["side"]) == {"long"}


def test_metrics_on_known_curve():
    eq = pd.Series([100.0, 120.0, 90.0, 130.0])
    assert metrics.total_return(eq) == pytest.approx(0.30)
    assert metrics.max_drawdown(eq) == pytest.approx(0.25)
    stats = metrics.trade_stats(pd.DataFrame({"pnl": [10.0, -5.0, 20.0, -5.0]}))
    assert stats["win_rate"] == 0.5
    assert stats["profit_factor"] == pytest.approx(3.0)
