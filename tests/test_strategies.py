import pytest

from bot.strategies import mean_reversion as mr
from bot.strategies import momentum_breakout as mb
from bot.strategies.base import Action, Position

FLAT_20 = [100.0, 101.0] * 10  # mean 100.5, std 0.5


def test_mean_reversion_needs_enough_bars(bars):
    assert mr.evaluate(bars([100] * 5), Position.FLAT).action == Action.HOLD


def test_mean_reversion_enters_long_when_stretched_down(bars):
    sig = mr.evaluate(bars(FLAT_20[1:] + [97.0]), Position.FLAT)
    assert sig.action == Action.ENTER_LONG
    assert sig.details["z"] <= -1.5
    assert "below" in sig.reason


def test_mean_reversion_enters_short_when_stretched_up(bars):
    sig = mr.evaluate(bars(FLAT_20[1:] + [104.0]), Position.FLAT)
    assert sig.action == Action.ENTER_SHORT


def test_mean_reversion_holds_inside_band(bars):
    assert mr.evaluate(bars(FLAT_20), Position.FLAT).action == Action.HOLD


def test_mean_reversion_exits_long_at_mean(bars):
    sig = mr.evaluate(bars(FLAT_20[1:] + [101.0]), Position.LONG)
    assert sig.action == Action.EXIT


def test_mean_reversion_flat_prices_hold(bars):
    assert mr.evaluate(bars([100.0] * 25), Position.FLAT).action == Action.HOLD


def test_breakout_enters_on_high_with_volume(bars):
    closes = [100.0] * 20 + [110.0]
    volumes = [100.0] * 20 + [200.0]
    sig = mb.evaluate(bars(closes, volumes), Position.FLAT)
    assert sig.action == Action.ENTER_LONG
    assert sig.details["volume_ratio"] == pytest.approx(2.0)


def test_breakout_rejects_low_volume(bars):
    closes = [100.0] * 20 + [110.0]
    volumes = [100.0] * 20 + [120.0]
    sig = mb.evaluate(bars(closes, volumes), Position.FLAT)
    assert sig.action == Action.HOLD
    assert "volume" in sig.reason


def test_breakout_exits_on_breakdown(bars):
    sig = mb.evaluate(bars([100.0] * 20 + [90.0]), Position.LONG)
    assert sig.action == Action.EXIT


def test_breakout_is_long_only(bars):
    with pytest.raises(ValueError):
        mb.evaluate(bars([100.0] * 25), Position.SHORT)


@pytest.mark.parametrize("module,position", [(mr, Position.FLAT), (mr, Position.LONG), (mr, Position.SHORT),
                                             (mb, Position.FLAT), (mb, Position.LONG)])
def test_precomputed_path_matches_live_evaluate_on_every_bar(bars, module, position):
    import math
    closes = [100 + 5 * math.sin(i / 3) + (i % 7) for i in range(80)]
    volumes = [100 + 80 * (i % 5 == 0) for i in range(80)]
    df = bars(closes, volumes)
    rows = module.precompute(df).to_dict("records")
    for t in range(len(df)):
        live = module.evaluate(df.iloc[: t + 1], position)
        fast = module.decide(rows[t], position)
        assert live.action == fast.action, t
        if live.action != Action.HOLD:
            assert live.reason == fast.reason


def test_missing_columns_raise(bars):
    df = bars([100.0] * 25).drop(columns=["volume"])
    with pytest.raises(ValueError):
        mr.evaluate(df, Position.FLAT)
