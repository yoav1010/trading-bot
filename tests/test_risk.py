import pytest

from bot import risk
from bot.config import RiskParams
from bot.strategies.base import Position

NO_CAP = RiskParams(max_position_pct=10.0)


def test_stop_out_loses_exactly_one_percent():
    equity, price, atr_value, mult = 10_000, 500.0, 5.0, 1.0
    qty = risk.position_size(equity, price, atr_value, mult, fractional=True, params=NO_CAP)
    stop = risk.initial_stop(price, atr_value, mult, Position.LONG)
    assert qty * (price - stop) == pytest.approx(100.0)  # 1% of 10,000


def test_volatile_market_gets_smaller_position():
    calm = risk.position_size(10_000, 100, 1.0, 2.0, fractional=True, params=NO_CAP)
    wild = risk.position_size(10_000, 100, 4.0, 2.0, fractional=True, params=NO_CAP)
    assert wild == pytest.approx(calm / 4)


def test_position_capped_by_max_position_pct():
    qty = risk.position_size(10_000, 100, 0.01, 1.0, fractional=True, params=RiskParams(max_position_pct=0.25))
    assert qty * 100 == pytest.approx(2_500)


def test_whole_shares_round_down():
    qty = risk.position_size(10_000, 100, 3.0, 1.0, fractional=False, params=NO_CAP)
    assert qty == 33.0  # 100 / 3 = 33.3


@pytest.mark.parametrize("args", [(0, 100, 1, 1), (10_000, 0, 1, 1), (10_000, 100, 0, 1), (10_000, 100, 1, 0)])
def test_bad_inputs_give_zero(args):
    assert risk.position_size(*args) == 0.0


def test_trailing_stop_only_tightens_long():
    stop = risk.trailing_stop(90.0, price=100.0, atr_value=2.0, stop_atr_mult=2.0, side=Position.LONG)
    assert stop == 96.0
    assert risk.trailing_stop(stop, price=95.0, atr_value=2.0, stop_atr_mult=2.0, side=Position.LONG) == 96.0


def test_trailing_stop_only_tightens_short():
    stop = risk.trailing_stop(110.0, price=100.0, atr_value=2.0, stop_atr_mult=2.0, side=Position.SHORT)
    assert stop == 104.0
    assert risk.trailing_stop(stop, price=105.0, atr_value=2.0, stop_atr_mult=2.0, side=Position.SHORT) == 104.0


def test_stop_hit():
    assert risk.stop_hit(Position.LONG, bar_low=94.9, bar_high=99, stop=95)
    assert not risk.stop_hit(Position.LONG, bar_low=95.1, bar_high=99, stop=95)
    assert risk.stop_hit(Position.SHORT, bar_low=100, bar_high=105, stop=105)


def test_drawdown_guard_trips_and_stays_tripped():
    guard = risk.DrawdownGuard(max_drawdown=0.10)
    assert guard.update(10_000)
    assert guard.update(11_000)
    assert guard.update(9_950)          # 9.5% below peak: still allowed
    assert not guard.update(9_900)      # 10% below peak: tripped
    assert guard.drawdown == pytest.approx(0.10)
    assert not guard.update(12_000)     # recovery doesn't reset it automatically
