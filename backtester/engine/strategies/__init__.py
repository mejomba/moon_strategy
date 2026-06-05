"""Strategy implementations for the backtesting engine."""

from backtester.engine.strategies.base import FLAT, LONG, SHORT, BaseStrategy
from backtester.engine.strategies.registry import (
    STRATEGY_REGISTRY,
    get_strategy,
    strategy_choices,
)
from backtester.engine.strategies.rsi import RsiStrategy
from backtester.engine.strategies.sma_crossover import SmaCrossoverStrategy

__all__ = [
    "BaseStrategy",
    "LONG",
    "FLAT",
    "SHORT",
    "SmaCrossoverStrategy",
    "RsiStrategy",
    "STRATEGY_REGISTRY",
    "get_strategy",
    "strategy_choices",
]
