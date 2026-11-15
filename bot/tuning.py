"""Walk-forward parameter tuning.

Picking the parameters that did best on all the data and then reporting how well they did
on that same data is overfitting: the result looks good because the test data was used to
choose. Walk-forward testing avoids that:

  fold 1: [ train ][ test ]
  fold 2:         [ train ][ test ]
  fold 3:                 [ train ][ test ]

For each fold, every parameter combination is backtested on the TRAIN window, the one with
the best Sharpe ratio is chosen, and only that choice is run on the TEST window that comes
after it. Stitching the test windows together gives an out-of-sample result: performance on
data the tuning never saw. The default parameters and buy and hold are run on the same test
windows for comparison.

Usage:  python -m bot.tuning
"""

import itertools
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from bot import backtest, metrics
from bot.backtest import StrategySpec

WARMUP = 60  # bars of history before each window, used only to warm up indicators
MIN_TRAIN_TRADES = 5

GRIDS = {
    "SPY mean reversion": {"lookback": [20, 40], "entry_z": [1.5, 2.0, 2.5], "stop_atr_mult": [1.0, 2.0, 3.0]},
    "BTC breakout": {"lookback": [20, 50], "volume_mult": [1.0, 1.5, 2.0], "stop_atr_mult": [2.0, 3.0, 4.0]},
}


def expand(grid: dict) -> list[dict]:
    """All combinations of a parameter grid, e.g. {"a": [1, 2], "b": [3]} -> [{a:1,b:3}, {a:2,b:3}]."""
    keys = list(grid)
    return [dict(zip(keys, values)) for values in itertools.product(*(grid[k] for k in keys))]


def folds(n_bars: int, train_len: int, test_len: int, warmup: int = WARMUP) -> list[tuple[int, int, int]]:
    """(train_start, test_start, test_end) bar indices; test windows follow each other with no overlap."""
    out, train_start = [], warmup
    while train_start + train_len + test_len <= n_bars:
        test_start = train_start + train_len
        out.append((train_start, test_start, test_start + test_len))
        train_start += test_len
    return out


def window_run(df: pd.DataFrame, spec: StrategySpec, start: int, end: int):
    """Backtest bars [start, end), with WARMUP bars before `start` used only for indicators."""
    lo = max(0, start - WARMUP)
    return backtest.run(df.iloc[lo:end], spec, trade_from=start - lo)


@dataclass
class Fold:
    train_period: str
    test_period: str
    chosen: dict
    train_sharpe: float
    tuned: backtest.BacktestResult
    default: backtest.BacktestResult


def walk_forward(df: pd.DataFrame, spec: StrategySpec, grid: dict, train_len: int, test_len: int) -> list[Fold]:
    results = []
    for train_start, test_start, test_end in folds(len(df), train_len, test_len):
        best, best_sharpe = None, -math.inf
        for combo in expand(grid):
            res = window_run(df, spec.with_params(**combo), train_start, test_start)
            if res.stats["trades"] >= MIN_TRAIN_TRADES and res.stats["sharpe"] > best_sharpe:
                best, best_sharpe = combo, res.stats["sharpe"]
        chosen_spec = spec.with_params(**best) if best else spec
        results.append(Fold(
            train_period=f"{df.index[train_start]:%Y-%m-%d} to {df.index[test_start - 1]:%Y-%m-%d}",
            test_period=f"{df.index[test_start]:%Y-%m-%d} to {df.index[test_end - 1]:%Y-%m-%d}",
            chosen=best or {"(defaults)": "too few trades"},
            train_sharpe=best_sharpe if best else float("nan"),
            tuned=window_run(df, chosen_spec, test_start, test_end),
            default=window_run(df, spec, test_start, test_end),
        ))
    return results


def stitch(curves: list[pd.Series], start: float = 10_000.0) -> pd.Series:
    """Chain the test-window equity curves: each window continues from where the last one ended."""
    pieces, level = [], start
    for curve in curves:
        scaled = curve / curve.iloc[0] * level
        pieces.append(scaled)
        level = scaled.iloc[-1]
    return pd.concat(pieces)


# ---------------------------------------------------------------- report

RUNS = [
    # (spec, ticker, interval, period, slug, train bars, test bars)
    (backtest.SPY_MEAN_REVERSION, "SPY", "15m", "60d", "spy", 26 * 20, 26 * 10),      # 20 days / 10 days
    (backtest.BTC_BREAKOUT, "BTC-USD", "1h", "730d", "btc", 24 * 180, 24 * 90),        # ~6 months / ~3 months
]


def describe(combo: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in combo.items())


def report(df, spec, fold_results, slug: str, docs: Path) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tuned = stitch([f.tuned.equity for f in fold_results])
    default = stitch([f.default.equity for f in fold_results])
    hold = stitch([f.tuned.benchmark for f in fold_results])
    periods = spec.periods_per_year

    lines = [f"### {spec.name}: walk-forward ({len(fold_results)} folds)", "",
             "| Test window | Chosen on train window | Train Sharpe | Test return (tuned) | Test return (defaults) | Buy and hold |",
             "|---|---|---|---|---|---|"]
    for f in fold_results:
        lines.append(f"| {f.test_period} | {describe(f.chosen)} | {f.train_sharpe:.2f} | "
                     f"{f.tuned.stats['total_return']:+.1%} ({f.tuned.stats['trades']} trades) | "
                     f"{f.default.stats['total_return']:+.1%} | {f.tuned.benchmark_stats['total_return']:+.1%} |")
    lines += ["", "| Out-of-sample, all test windows | Return | Max drawdown | Sharpe |", "|---|---|---|---|"]
    for name, curve in (("Tuned (walk-forward)", tuned), ("Defaults", default), ("Buy and hold", hold)):
        lines.append(f"| {name} | {metrics.total_return(curve):+.1%} | {metrics.max_drawdown(curve):.1%} | "
                     f"{metrics.sharpe(curve, periods):.2f} |")

    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = range(len(tuned))
    ax.plot(x, tuned.values, color="#2166ac", label="Tuned (walk-forward)")
    ax.plot(x, default.values, color="#b2182b", label="Defaults")
    ax.plot(x, hold.values, color="#999", ls="--", label="Buy and hold")
    ax.set_title(f"{spec.name}: out-of-sample equity across {len(fold_results)} test windows")
    ax.legend(loc="upper left", fontsize=8)
    ticks = list(range(0, len(tuned), max(1, len(tuned) // 6)))
    ax.set_xticks(ticks, [tuned.index[i].strftime("%Y-%m-%d") for i in ticks], fontsize=8)
    fig.tight_layout()
    fig.savefig(docs / f"walkforward_{slug}.png", dpi=110)
    plt.close(fig)
    return "\n".join(lines)


def main() -> None:
    from bot.data import fetch_yahoo

    docs = Path(__file__).resolve().parents[1] / "docs"
    docs.mkdir(exist_ok=True)
    sections = []
    for spec, ticker, interval, period, slug, train_len, test_len in RUNS:
        df = fetch_yahoo(ticker, interval, period)
        fold_results = walk_forward(df, spec, GRIDS[spec.name], train_len, test_len)
        sections.append(report(df, spec, fold_results, slug, docs))
    text = "\n\n".join(sections)
    (docs / "walkforward_summary.md").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
