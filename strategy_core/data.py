"""Market data structures and loaders for the backtesting engine.

The engine operates on ordered sequences of OHLCV :class:`Bar` objects. Data
can be loaded from a CSV file or generated synthetically (useful for demos and
tests, and when no historical feed is configured).
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class Bar:
    """A single OHLCV candle."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


# Approximate number of bars per calendar year for each timeframe. Used to
# annualise the Sharpe ratio. Crypto-style 24/7 markets are assumed.
_TIMEFRAME_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}

_MINUTES_PER_YEAR = 365 * 24 * 60


def timeframe_to_timedelta(timeframe: str) -> timedelta:
    """Return the bar duration for a timeframe string like ``"1h"``."""
    try:
        return timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
    except KeyError as exc:
        raise ValueError(f"Unsupported timeframe: {timeframe!r}") from exc


def periods_per_year(timeframe: str) -> float:
    """Number of bars of ``timeframe`` length that fit in one year."""
    return _MINUTES_PER_YEAR / _TIMEFRAME_MINUTES[timeframe]


def load_csv(path: str | Path) -> list[Bar]:
    """Load bars from a CSV file with a header row.

    Expected columns (case-insensitive): ``timestamp, open, high, low, close``
    and an optional ``volume``. The timestamp may be an ISO 8601 string or a
    UNIX epoch (seconds).
    """
    bars: list[Bar] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        field_map = {name.lower(): name for name in (reader.fieldnames or [])}
        for name in ("timestamp", "open", "high", "low", "close"):
            if name not in field_map:
                raise ValueError(f"CSV is missing required column: {name!r}")
        for row in reader:
            bars.append(
                Bar(
                    timestamp=_parse_timestamp(row[field_map["timestamp"]]),
                    open=float(row[field_map["open"]]),
                    high=float(row[field_map["high"]]),
                    low=float(row[field_map["low"]]),
                    close=float(row[field_map["close"]]),
                    volume=float(row[field_map["volume"]]) if "volume" in field_map else 0.0,
                )
            )
    bars.sort(key=lambda b: b.timestamp)
    return bars


def _parse_timestamp(value: str) -> datetime:
    value = value.strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Fall back to a UNIX epoch in seconds.
        return datetime.fromtimestamp(float(value), tz=timezone.utc)


def generate_synthetic(
    *,
    start: datetime,
    end: datetime,
    timeframe: str = "1d",
    start_price: float = 100.0,
    volatility: float = 0.02,
    drift: float = 0.0005,
    seed: int | None = None,
) -> list[Bar]:
    """Generate a reproducible random-walk price series.

    Prices follow a geometric Brownian motion so they stay positive. The series
    is deterministic for a given ``seed``, which keeps tests stable.
    """
    if end <= start:
        raise ValueError("end must be after start")

    rng = random.Random(seed)
    step = timeframe_to_timedelta(timeframe)
    bars: list[Bar] = []
    price = float(start_price)
    ts = start
    while ts <= end:
        shock = rng.gauss(drift, volatility)
        new_close = max(price * math.exp(shock), 1e-9)
        high = max(price, new_close) * (1 + abs(rng.gauss(0, volatility / 2)))
        low = min(price, new_close) * (1 - abs(rng.gauss(0, volatility / 2)))
        volume = abs(rng.gauss(1000, 250))
        bars.append(
            Bar(
                timestamp=ts,
                open=price,
                high=high,
                low=low,
                close=new_close,
                volume=volume,
            )
        )
        price = new_close
        ts += step
    return bars


def synthetic_from_dates(start_date, end_date, timeframe="1d", *, seed=None) -> list[Bar]:
    """Convenience wrapper that builds bars from two ``date`` objects."""
    start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_date, time.min, tzinfo=timezone.utc)
    return generate_synthetic(start=start, end=end, timeframe=timeframe, seed=seed)
