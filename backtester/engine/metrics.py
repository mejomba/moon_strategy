"""Performance metrics computed from an equity curve and trade log."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from backtester.engine.portfolio import TradeRecord


@dataclass
class PerformanceMetrics:
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float  # reported as a positive magnitude, e.g. 12.5
    sharpe_ratio: float
    win_rate_pct: float
    num_trades: int


def compute_metrics(
    equity_curve: list[tuple[datetime, float]],
    trades: list[TradeRecord],
    periods_per_year: float,
    initial_capital: float,
) -> PerformanceMetrics:
    """Summarise a backtest run into aggregate performance statistics."""
    equities = [e for _, e in equity_curve]
    final_equity = equities[-1] if equities else float(initial_capital)

    total_return_pct = (
        (final_equity / initial_capital - 1.0) * 100.0 if initial_capital else 0.0
    )

    return PerformanceMetrics(
        final_equity=final_equity,
        total_return_pct=total_return_pct,
        max_drawdown_pct=_max_drawdown_pct(equities),
        sharpe_ratio=_sharpe_ratio(equities, periods_per_year),
        win_rate_pct=_win_rate_pct(trades),
        num_trades=len(trades),
    )


def _max_drawdown_pct(equities: list[float]) -> float:
    """Largest peak-to-trough decline, as a positive percentage."""
    peak = float("-inf")
    max_dd = 0.0
    for value in equities:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (peak - value) / peak
            max_dd = max(max_dd, drawdown)
    return max_dd * 100.0


def _sharpe_ratio(equities: list[float], periods_per_year: float) -> float:
    """Annualised Sharpe ratio of per-bar returns (risk-free rate = 0)."""
    if len(equities) < 3:
        return 0.0
    returns = [
        equities[i] / equities[i - 1] - 1.0
        for i in range(1, len(equities))
        if equities[i - 1] > 0
    ]
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(periods_per_year)


def _win_rate_pct(trades: list[TradeRecord]) -> float:
    closed = [t for t in trades if t.pnl is not None]
    if not closed:
        return 0.0
    wins = sum(1 for t in closed if t.pnl > 0)
    return wins / len(closed) * 100.0
