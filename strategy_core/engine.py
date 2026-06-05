"""The core event-driven backtesting loop."""

from __future__ import annotations

from dataclasses import dataclass

from strategy_core.costs import ZERO_COST, CostModel
from strategy_core.data import Bar, periods_per_year, timeframe_to_timedelta
from strategy_core.metrics import PerformanceMetrics, compute_metrics
from strategy_core.portfolio import Portfolio, TradeRecord
from strategy_core.strategies.base import BaseStrategy


@dataclass
class BacktestResult:
    """Everything produced by a single backtest run."""

    metrics: PerformanceMetrics
    trades: list[TradeRecord]
    equity_curve: list


class BacktestEngine:
    """Run a strategy over historical bars and simulate the resulting trades.

    The strategy emits a target position per bar (long/flat/short). Whenever the
    target changes, the engine closes any open position and opens the new one at
    that bar's close price (through the cost model), accrues funding for the
    holding period, then marks the portfolio to market.
    """

    def __init__(
        self,
        initial_capital: float = 10_000.0,
        timeframe: str = "1d",
        cost_model: CostModel | None = None,
    ):
        self.initial_capital = float(initial_capital)
        self.timeframe = timeframe
        self.cost_model = cost_model or ZERO_COST
        self.bar_hours = timeframe_to_timedelta(timeframe).total_seconds() / 3600.0

    def run(self, bars: list[Bar], strategy: BaseStrategy) -> BacktestResult:
        if not bars:
            raise ValueError("Cannot run a backtest with no bars")

        signals = strategy.generate_signals(bars)
        if len(signals) != len(bars):
            raise ValueError(
                "Strategy must return one signal per bar "
                f"(got {len(signals)} signals for {len(bars)} bars)"
            )

        portfolio = Portfolio(
            initial_capital=self.initial_capital, cost_model=self.cost_model
        )
        for bar, target in zip(bars, signals):
            if target != portfolio.side:
                portfolio.close_position(bar.close, bar.timestamp)
                if target != 0:
                    portfolio.open_position(target, bar.close, bar.timestamp)
            # Funding accrues on whatever position is held over this bar.
            portfolio.accrue_funding(bar.close, self.bar_hours)
            portfolio.mark(bar.close, bar.timestamp)

        # Liquidate any position still open at the end of the series.
        last_bar = bars[-1]
        if portfolio.position != 0:
            portfolio.close_position(last_bar.close, last_bar.timestamp)
            portfolio.equity_curve[-1] = (
                last_bar.timestamp,
                portfolio.equity(last_bar.close),
            )

        metrics = compute_metrics(
            portfolio.equity_curve,
            portfolio.trades,
            periods_per_year(self.timeframe),
            self.initial_capital,
        )
        return BacktestResult(
            metrics=metrics,
            trades=portfolio.trades,
            equity_curve=portfolio.equity_curve,
        )
