# Trading Bot (paper trading)

An automated trading bot that runs two rule-based strategies on **Alpaca paper trading** (simulated money, real market prices), with a public dashboard that shows every trade and the reason it fired.

> Paper trading only. This is an engineering project, not financial advice, and it makes no claims about profit.

## Strategies

| Market | Bars | Strategy | Entry | Exit |
|---|---|---|---|---|
| SPY | 15 min | Mean reversion | Close is 1.5+ std devs from the 20-bar mean (long below, short above) | Close returns to the mean, or the 1 ATR stop |
| BTC/USD | 1 hour | Momentum breakout (long only) | Close breaks the previous 20-bar high on 1.5x+ average volume | Close breaks the previous 20-bar low, or the 2 ATR trailing stop |

BTC is long only because Alpaca does not support short-selling crypto.

## Risk management

- **ATR position sizing:** the stop sits a fixed number of ATRs away, and the position is sized so that hitting it loses exactly 1% of equity. Volatile markets get smaller positions.
- **Position cap:** at most 25% of equity in one position.
- **Stops only tighten:** the trailing stop moves toward price and never away.
- **Circuit breaker:** if equity falls 10% from its peak, the bot stops trading until it is reset by hand.

All parameters live in `bot/config.py`.

## Project layout

```
bot/
  config.py                 strategy and risk parameters
  indicators.py             SMA, std dev, z-score, EMA, ATR, prior-bar high/low/mean
  risk.py                   position sizing, stops, drawdown circuit breaker
  strategies/
    base.py                 Signal / Action / Position types
    mean_reversion.py       SPY strategy
    momentum_breakout.py    BTC strategy
tests/                      unit tests (pytest)
```

Every strategy returns a `Signal` with an action, a plain-English reason and the numbers behind it, e.g.
`ENTER_LONG: Close 97.00 is 2.85 std devs below the 20-bar mean 100.33`. The dashboard will show these.

## Design choices

- **No lookahead:** signals use only closed bars, and breakout levels use the bars *before* the current one. A test checks that appending future bars never changes past indicator values.
- **Free to run:** Alpaca paper trading, GitHub Actions for scheduling, and GitHub Pages for the dashboard. No server costs.

## Run the tests

```bash
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest -q
```

## Roadmap

- [x] Indicators, both strategies, risk manager, unit tests
- [ ] Backtester with equity curve and stats compared against buy-and-hold
- [ ] Alpaca paper-trading connection and trade log
- [ ] Scheduled runs on GitHub Actions
- [ ] React + TypeScript dashboard on GitHub Pages
