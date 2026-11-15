"""Shared types for strategies.

A strategy looks at closed bars and the current position and returns one Signal.
Every Signal carries a human-readable reason and the numbers behind it, so the
dashboard can show exactly why each trade fired.
"""

from dataclasses import dataclass, field
from enum import Enum


class Action(str, Enum):
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"
    HOLD = "hold"


class Position(str, Enum):
    FLAT = "flat"
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class Signal:
    action: Action
    reason: str
    details: dict = field(default_factory=dict)


REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def check_bars(df) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"bars are missing columns: {missing}")
