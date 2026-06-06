"""Validation and cleaning of historical OHLCV data on ingest (CLAUDE.md §8).

Pure Python (no Django) so it is easy to unit test. The API layer turns the
cleaned rows into :class:`~marketdata.models.Candle` objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")
MAX_REPORTED_ERRORS = 20


@dataclass
class CleanCandle:
    timestamp: datetime  # naive; the persistence layer attaches the timezone
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class IngestReport:
    cleaned: list[CleanCandle] = field(default_factory=list)
    skipped: int = 0
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def imported(self) -> int:
        return len(self.cleaned)

    @property
    def start(self) -> datetime | None:
        return self.cleaned[0].timestamp if self.cleaned else None

    @property
    def end(self) -> datetime | None:
        return self.cleaned[-1].timestamp if self.cleaned else None


def _add_error(report: IngestReport, message: str) -> None:
    if len(report.errors) < MAX_REPORTED_ERRORS:
        report.errors.append(message)


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO date or datetime; raise ValueError otherwise."""
    return datetime.fromisoformat(value.strip())


def clean_rows(rows: list[dict]) -> IngestReport:
    """Validate, clean, de-duplicate and sort raw CSV rows into candles.

    Bad rows are skipped (with a capped list of reasons); duplicate timestamps
    keep the first occurrence. The result is sorted ascending by timestamp.
    """
    report = IngestReport()
    if not rows:
        report.errors.append("The file has no data rows.")
        return report

    missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
    if missing:
        report.errors.append(f"Missing required column(s): {', '.join(missing)}.")
        return report

    seen: dict[datetime, CleanCandle] = {}
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            ts = _parse_timestamp(str(row["timestamp"]))
            o = float(row["open"])
            h = float(row["high"])
            low = float(row["low"])
            c = float(row["close"])
            v = float(row["volume"]) if row.get("volume") not in (None, "") else 0.0
        except (ValueError, TypeError, KeyError):
            report.skipped += 1
            _add_error(report, f"Row {i}: could not parse numbers/timestamp.")
            continue

        if min(o, h, low, c) <= 0:
            report.skipped += 1
            _add_error(report, f"Row {i}: prices must be positive.")
            continue
        if h < low or h < o or h < c or low > o or low > c:
            report.skipped += 1
            _add_error(report, f"Row {i}: inconsistent OHLC (high/low out of range).")
            continue
        if v < 0:
            report.skipped += 1
            _add_error(report, f"Row {i}: volume must be non-negative.")
            continue

        if ts in seen:
            report.duplicates += 1
            continue
        seen[ts] = CleanCandle(timestamp=ts, open=o, high=h, low=low, close=c, volume=v)

    report.cleaned = [seen[ts] for ts in sorted(seen)]
    return report
