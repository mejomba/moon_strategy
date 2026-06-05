"""Heuristic quality / overfitting warnings for a backtest result.

Pure Python, independent of Django (CLAUDE.md §2), so it can be unit tested in
isolation. These are honest, cheap heuristics — NOT a substitute for proper
out-of-sample testing or walk-forward analysis (roadmap phase 5). Every run is
flagged as in-sample-only until that validation exists, so results are never
presented as more reliable than they are (CLAUDE.md §3/§8).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from strategy_core.metrics import PerformanceMetrics

# Severity levels, ordered low → high.
INFO = "info"
WARNING = "warning"

# Thresholds for the heuristics (kept here so they are easy to tune/test).
MIN_ROBUST_TRADES = 30
SUSPICIOUS_SHARPE = 3.0
SUSPICIOUS_SHARPE_MAX_TRADES = 50
COST_DRAG_RATIO = 0.4


@dataclass(frozen=True)
class QualityWarning:
    """A single reliability caveat about a backtest result."""

    code: str
    severity: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def assess_quality(
    metrics: PerformanceMetrics, initial_capital: float
) -> list[QualityWarning]:
    """Return reliability warnings for a finished backtest, most severe first."""
    warnings: list[QualityWarning] = []

    # Always present until real out-of-sample/walk-forward validation exists.
    warnings.append(
        QualityWarning(
            code="in_sample_only",
            severity=WARNING,
            message=(
                "This backtest is in-sample only: no out-of-sample or walk-forward "
                "validation was performed. Real-world results are typically worse."
            ),
        )
    )

    if metrics.num_trades < MIN_ROBUST_TRADES:
        warnings.append(
            QualityWarning(
                code="few_trades",
                severity=WARNING,
                message=(
                    f"Only {metrics.num_trades} trade(s). With so few trades the "
                    "metrics are not statistically meaningful."
                ),
            )
        )

    if (
        metrics.sharpe_ratio > SUSPICIOUS_SHARPE
        and metrics.num_trades < SUSPICIOUS_SHARPE_MAX_TRADES
    ):
        warnings.append(
            QualityWarning(
                code="overfit_high_sharpe",
                severity=WARNING,
                message=(
                    f"Sharpe ratio {metrics.sharpe_ratio:.1f} from only "
                    f"{metrics.num_trades} trade(s) is unusually high and may "
                    "indicate overfitting."
                ),
            )
        )

    cost_warning = _cost_drag_warning(metrics, initial_capital)
    if cost_warning is not None:
        warnings.append(cost_warning)

    return warnings


def _cost_drag_warning(
    metrics: PerformanceMetrics, initial_capital: float
) -> QualityWarning | None:
    """Warn when trading costs eat a large share of gross profit."""
    costs = metrics.total_commission + metrics.total_funding
    if costs <= 0:
        return None
    net_gain = metrics.final_equity - initial_capital
    gross_gain = net_gain + costs
    if gross_gain <= 0:
        return None
    ratio = costs / gross_gain
    if ratio < COST_DRAG_RATIO:
        return None
    return QualityWarning(
        code="cost_drag",
        severity=INFO,
        message=(
            f"Trading costs consumed {ratio * 100:.0f}% of gross profit; the "
            "strategy's edge is thin after costs."
        ),
    )
