"""Registry mapping strategy keys to their implementations.

The ``kind`` field on the :class:`~backtester.models.Strategy` model stores one
of these keys; the runner uses :func:`get_strategy` to instantiate the matching
engine strategy with the strategy's stored parameters.
"""

from __future__ import annotations

from strategy_core.strategies.base import BaseStrategy
from strategy_core.strategies.graph_strategy import GraphStrategy
from strategy_core.strategies.rsi import RsiStrategy
from strategy_core.strategies.sma_crossover import SmaCrossoverStrategy

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    SmaCrossoverStrategy.name: SmaCrossoverStrategy,
    RsiStrategy.name: RsiStrategy,
    GraphStrategy.name: GraphStrategy,
}


def get_strategy(kind: str, **params) -> BaseStrategy:
    """Instantiate the registered strategy ``kind`` with ``params``."""
    try:
        strategy_cls = STRATEGY_REGISTRY[kind]
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGY_REGISTRY))
        raise ValueError(
            f"Unknown strategy kind {kind!r}. Available: {available}"
        ) from exc
    return strategy_cls(**params)


def strategy_choices() -> list[tuple[str, str]]:
    """Return ``(value, label)`` pairs for use in Django model choices."""
    return [
        (key, cls.name.replace("_", " ").title())
        for key, cls in STRATEGY_REGISTRY.items()
    ]
