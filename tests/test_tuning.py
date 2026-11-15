import math

import pandas as pd
import pytest

from bot import backtest, tuning
from bot.config import RiskParams

from conftest import make_bars


def test_expand_grid():
    combos = tuning.expand({"a": [1, 2], "b": [3, 4, 5]})
    assert len(combos) == 6
    assert {"a": 2, "b": 5} in combos


def test_folds_never_overlap_and_test_follows_train():
    fs = tuning.folds(n_bars=1000, train_len=300, test_len=100, warmup=60)
    assert fs[0] == (60, 360, 460)
    for train_start, test_start, test_end in fs:
        assert train_start < test_start < test_end <= 1000
    for (_, _, end_a), (_, start_b, _) in zip(fs, fs[1:]):
        assert end_a == start_b  # test windows are consecutive, never overlapping


def test_no_trades_before_trade_from():
    closes = [100.0, 101.0] * 10 + [97.0, 97.2, 97.4, 101.0, 101.0] * 8
    df = make_bars(closes)
    df.index = pd.date_range("2026-01-05", periods=len(df), freq="15min")
    res = backtest.run(df, backtest.SPY_MEAN_REVERSION, slippage=0.0,
                       risk=RiskParams(max_drawdown=0.99), trade_from=25)
    assert res.equity.index[0] == df.index[25]
    assert res.equity.iloc[0] == 10_000
    assert (res.trades["entry_time"] >= df.index[25]).all()


def test_with_params_changes_only_strategy_params():
    spec = backtest.SPY_MEAN_REVERSION.with_params(entry_z=2.5, stop_atr_mult=3.0)
    assert spec.params.entry_z == 2.5 and spec.stop_atr_mult == 3.0
    assert spec.params.lookback == backtest.SPY_MEAN_REVERSION.params.lookback


def test_stitch_chains_windows():
    a = pd.Series([100.0, 110.0])
    b = pd.Series([50.0, 25.0])
    out = tuning.stitch([a, b], start=1_000.0)
    assert out.iloc[1] == pytest.approx(1_100.0)
    assert out.iloc[-1] == pytest.approx(550.0)  # second window halves what the first left


def test_walk_forward_runs_end_to_end():
    closes = [100 + 4 * math.sin(i / 5) for i in range(700)]
    df = make_bars(closes)
    df.index = pd.date_range("2026-01-05", periods=len(df), freq="15min")
    grid = {"entry_z": [1.0, 1.5], "stop_atr_mult": [1.0, 3.0]}
    results = tuning.walk_forward(df, backtest.SPY_MEAN_REVERSION, grid, train_len=200, test_len=100)
    assert len(results) == 4
    for f in results:
        assert f.tuned.equity.index[0] > pd.Timestamp(f.train_period.split(" to ")[1])
