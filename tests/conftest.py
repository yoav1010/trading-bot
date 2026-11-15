import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_bars(closes, volumes=None, spread=0.5):
    """Bars where high/low sit `spread` around the close and open equals the previous close."""
    closes = list(closes)
    volumes = list(volumes) if volumes is not None else [100.0] * len(closes)
    opens = [closes[0]] + closes[:-1]
    return pd.DataFrame({
        "open": opens,
        "high": [c + spread for c in closes],
        "low": [c - spread for c in closes],
        "close": closes,
        "volume": volumes,
    })


@pytest.fixture
def bars():
    return make_bars
