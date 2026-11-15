"""Performance statistics for an equity curve and a list of closed trades."""

import math

import pandas as pd


def total_return(equity: pd.Series) -> float:
    """Final equity / starting equity - 1."""
    return float(equity.iloc[-1] / equity.iloc[0] - 1)


def drawdown_series(equity: pd.Series) -> pd.Series:
    """Decline from the running peak at every bar (0.1 = 10% below the peak)."""
    return 1 - equity / equity.cummax()


def max_drawdown(equity: pd.Series) -> float:
    return float(drawdown_series(equity).max())


def sharpe(equity: pd.Series, periods_per_year: float) -> float:
    """Annualized Sharpe ratio of per-bar returns, assuming a 0% risk-free rate."""
    returns = equity.pct_change().dropna()
    std = returns.std(ddof=1)
    if len(returns) < 2 or std == 0 or math.isnan(std):
        return 0.0
    return float(returns.mean() / std * math.sqrt(periods_per_year))


def trade_stats(trades: pd.DataFrame) -> dict:
    """Win rate, average win and loss, and profit factor from closed trades (needs a 'pnl' column)."""
    if trades.empty:
        return {"trades": 0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "profit_factor": 0.0}
    wins = trades.loc[trades["pnl"] > 0, "pnl"]
    losses = trades.loc[trades["pnl"] <= 0, "pnl"]
    gross_loss = -losses.sum()
    return {
        "trades": int(len(trades)),
        "win_rate": float(len(wins) / len(trades)),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else float("inf"),
    }


def summarize(equity: pd.Series, trades: pd.DataFrame, periods_per_year: float) -> dict:
    stats = trade_stats(trades)
    stats.update({
        "total_return": total_return(equity),
        "max_drawdown": max_drawdown(equity),
        "sharpe": sharpe(equity, periods_per_year),
    })
    return stats
