"""Backtesting engine for trading strategies.

Public API:

* :class:`~backtester.engine.data.Bar` and data loaders
* :class:`~backtester.engine.engine.BacktestEngine` / ``BacktestResult``
* strategy implementations and the strategy registry
* :func:`~backtester.engine.runner.run_backtest` to execute a stored
  :class:`~backtester.models.Backtest` and persist its results
"""

from backtester.engine.data import (
    Bar,
    generate_synthetic,
    load_csv,
    periods_per_year,
    synthetic_from_dates,
)
from backtester.engine.engine import BacktestEngine, BacktestResult
from backtester.engine.strategies import (
    STRATEGY_REGISTRY,
    BaseStrategy,
    get_strategy,
    strategy_choices,
)

__all__ = [
    "Bar",
    "generate_synthetic",
    "synthetic_from_dates",
    "load_csv",
    "periods_per_year",
    "BacktestEngine",
    "BacktestResult",
    "BaseStrategy",
    "STRATEGY_REGISTRY",
    "get_strategy",
    "strategy_choices",
]
