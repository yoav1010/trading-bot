"""Run both backtests on real historical data and save charts + a summary for the README.

Usage:  python -m bot.report            (uses cached data if present)
        python -m bot.report --refresh  (downloads fresh data)
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to files, no window
import matplotlib.pyplot as plt  # noqa: E402

from bot import backtest  # noqa: E402
from bot.data import fetch_yahoo  # noqa: E402
from bot.metrics import drawdown_series  # noqa: E402

DOCS = Path(__file__).resolve().parents[1] / "docs"

RUNS = [
    # (spec, yahoo ticker, interval, period, file slug)
    (backtest.SPY_MEAN_REVERSION, "SPY", "15m", "60d", "spy"),
    (backtest.BTC_BREAKOUT, "BTC-USD", "1h", "730d", "btc"),
]


def plot(result, df, path: Path) -> None:
    fig, (ax_price, ax_eq, ax_dd) = plt.subplots(
        3, 1, figsize=(11, 9), sharex=True, gridspec_kw={"height_ratios": [3, 2, 1]})
    x = range(len(df))  # bar numbers, so overnight/weekend gaps don't stretch the chart
    pos = {ts: i for i, ts in enumerate(df.index)}

    ax_price.plot(x, df["close"], lw=0.8, color="#444", label="Close")
    trades = result.trades
    if not trades.empty:
        longs, shorts = trades[trades["side"] == "long"], trades[trades["side"] == "short"]
        ax_price.scatter([pos[t] for t in longs["entry_time"]], longs["entry_price"],
                         marker="^", color="#1a9850", s=40, label="Long entry", zorder=3)
        ax_price.scatter([pos[t] for t in shorts["entry_time"]], shorts["entry_price"],
                         marker="v", color="#d73027", s=40, label="Short entry", zorder=3)
        ax_price.scatter([pos[t] for t in trades["exit_time"]], trades["exit_price"],
                         marker="x", color="#000", s=30, label="Exit", zorder=3)
    ax_price.set_title(f"{result.spec.name}: trades on price")
    ax_price.legend(loc="upper left", fontsize=8)

    ax_eq.plot(x, result.equity, color="#2166ac", label="Strategy")
    ax_eq.plot(x, result.benchmark, color="#999", ls="--", label="Buy and hold")
    ax_eq.set_title("Equity (starting $10,000, paper)")
    ax_eq.legend(loc="upper left", fontsize=8)

    ax_dd.fill_between(x, -drawdown_series(result.equity) * 100, color="#d73027", alpha=0.4)
    ax_dd.set_title("Strategy drawdown (%)")
    ticks = list(range(0, len(df), max(1, len(df) // 6)))
    ax_dd.set_xticks(ticks, [df.index[i].strftime("%Y-%m-%d") for i in ticks], fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def row(name: str, s: dict) -> str:
    trades = s.get("trades", "n/a")
    win = f"{s['win_rate']:.0%}" if "win_rate" in s else "n/a"
    pf = s.get("profit_factor")
    pf = "n/a" if pf is None else ("inf" if pf == float("inf") else f"{pf:.2f}")
    return (f"| {name} | {s['total_return']:+.1%} | {s['max_drawdown']:.1%} | {s['sharpe']:.2f} "
            f"| {trades} | {win} | {pf} |")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="download fresh data")
    args = parser.parse_args()
    DOCS.mkdir(exist_ok=True)

    lines = ["| Run | Return | Max drawdown | Sharpe | Trades | Win rate | Profit factor |",
             "|---|---|---|---|---|---|---|"]
    for spec, ticker, interval, period, slug in RUNS:
        df = fetch_yahoo(ticker, interval, period, refresh=args.refresh)
        result = backtest.run(df, spec)
        plot(result, df, DOCS / f"backtest_{slug}.png")
        result.trades.to_csv(DOCS / f"trades_{slug}.csv", index=False)
        span = f"{df.index[0]:%Y-%m-%d} to {df.index[-1]:%Y-%m-%d}, {len(df)} bars"
        lines.append(row(f"{spec.name} ({span})", result.stats))
        lines.append(row(f"Buy and hold {ticker}", result.benchmark_stats))

    table = "\n".join(lines)
    (DOCS / "backtest_summary.md").write_text(table + "\n", encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
