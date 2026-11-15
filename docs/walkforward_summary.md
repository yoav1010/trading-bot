### SPY mean reversion: walk-forward (3 folds)

| Test window | Chosen on train window | Train Sharpe | Test return (tuned) | Test return (defaults) | Buy and hold |
|---|---|---|---|---|---|
| 2026-09-23 to 2026-10-07 | lookback=40, entry_z=2.0, stop_atr_mult=2.0 | -1.54 | +0.2% (10 trades) | -1.2% | +0.7% |
| 2026-10-07 to 2026-10-21 | lookback=40, entry_z=2.0, stop_atr_mult=2.0 | 1.86 | -0.2% (11 trades) | -1.1% | -0.5% |
| 2026-10-21 to 2026-11-04 | lookback=40, entry_z=2.0, stop_atr_mult=2.0 | 0.01 | -0.7% (11 trades) | -0.7% | -1.1% |

| Out-of-sample, all test windows | Return | Max drawdown | Sharpe |
|---|---|---|---|
| Tuned (walk-forward) | -0.7% | 1.0% | -2.94 |
| Defaults | -3.0% | 3.7% | -10.69 |
| Buy and hold | -0.9% | 4.0% | -0.57 |

### BTC breakout: walk-forward (6 folds)

| Test window | Chosen on train window | Train Sharpe | Test return (tuned) | Test return (defaults) | Buy and hold |
|---|---|---|---|---|---|
| 2025-05-17 to 2025-08-15 | lookback=50, volume_mult=1.0, stop_atr_mult=4.0 | 0.18 | +0.3% (20 trades) | -1.6% | +15.7% |
| 2025-08-15 to 2025-11-13 | lookback=20, volume_mult=2.0, stop_atr_mult=3.0 | 1.04 | +0.9% (25 trades) | -0.6% | -15.4% |
| 2025-11-14 to 2026-02-12 | lookback=20, volume_mult=2.0, stop_atr_mult=3.0 | 1.00 | -2.7% (22 trades) | -2.1% | -33.4% |
| 2026-02-12 to 2026-05-13 | lookback=20, volume_mult=2.0, stop_atr_mult=3.0 | -0.83 | +1.0% (29 trades) | +2.0% | +21.9% |
| 2026-05-13 to 2026-08-11 | lookback=20, volume_mult=1.5, stop_atr_mult=2.0 | -0.02 | -1.0% (24 trades) | -1.0% | -19.8% |
| 2026-08-11 to 2026-11-09 | lookback=20, volume_mult=1.5, stop_atr_mult=2.0 | 0.49 | +4.9% (32 trades) | +4.9% | +17.6% |

| Out-of-sample, all test windows | Return | Max drawdown | Sharpe |
|---|---|---|---|
| Tuned (walk-forward) | +3.4% | 4.3% | 0.48 |
| Defaults | +1.5% | 4.8% | 0.26 |
| Buy and hold | -25.1% | 53.1% | -0.28 |
