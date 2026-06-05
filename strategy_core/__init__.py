"""Pure-Python backtesting core for trading strategies.

This package is independent of Django (see CLAUDE.md §8) so it can be tested and
reused in isolation. The Django app glues it to the database in
``backtester.runner``.

Public API:

* :class:`~strategy_core.data.Bar` and data loaders
* :class:`~strategy_core.costs.CostModel` and presets
* :class:`~strategy_core.engine.BacktestEngine` / ``BacktestResult``
* strategy implementations and the strategy registry
"""

from strategy_core.costs import DEFAULT_CRYPTO_COST, ZERO_COST, CostModel
from strategy_core.data import (
    Bar,
    generate_synthetic,
    load_csv,
    periods_per_year,
    synthetic_from_dates,
)
from strategy_core.engine import BacktestEngine, BacktestResult
from strategy_core.strategies import (
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
    "CostModel",
    "ZERO_COST",
    "DEFAULT_CRYPTO_COST",
    "BacktestEngine",
    "BacktestResult",
    "BaseStrategy",
    "STRATEGY_REGISTRY",
    "get_strategy",
    "strategy_choices",
]
