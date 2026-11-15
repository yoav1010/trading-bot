"""Historical bars for backtesting.

Uses Yahoo Finance through `yfinance` (free, no account). Free intraday history is limited:
about the last 60 days for 15-minute bars and about 2 years for 1-hour bars.
Downloads are cached as CSV in data/raw/ (git-ignored) so reruns are fast and repeatable.
"""

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
COLUMNS = ["open", "high", "low", "close", "volume"]


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    # Stock bars span daylight-saving changes (-04:00 and -05:00), so parse everything as UTC.
    df.index = pd.to_datetime(df.index, utc=True)
    return df[COLUMNS]


def fetch_yahoo(ticker: str, interval: str, period: str, refresh: bool = False) -> pd.DataFrame:
    """OHLCV bars, oldest first, with lowercase columns. Regular trading hours only for stocks."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = RAW_DIR / f"{ticker.replace('/', '-')}_{interval}_{period}.csv"
    if cache.exists() and not refresh:
        return load_csv(cache)

    import yfinance as yf  # imported here so tests don't need network access

    raw = yf.download(ticker, interval=interval, period=period, auto_adjust=False,
                      prepost=False, progress=False, multi_level_index=False)
    if raw.empty:
        raise RuntimeError(f"no data returned for {ticker} {interval} {period}")
    df = raw.rename(columns=str.lower)[COLUMNS].dropna()
    df = df[df["volume"] > 0] if ticker != "BTC-USD" else df  # drop empty stock bars
    df.to_csv(cache)
    return df
