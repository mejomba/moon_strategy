"""Strategy backed by a no-code logic graph (CLAUDE.md §4b)."""

from __future__ import annotations

from strategy_core.data import Bar
from strategy_core.graph import GraphValidationError, evaluate_graph
from strategy_core.strategies.base import BaseStrategy


class GraphStrategy(BaseStrategy):
    """Execute the visual builder's logic graph as a strategy.

    The graph is passed as the ``graph`` parameter (the executable strategy-JSON
    produced by the frontend). All trading logic lives in the graph; this class
    is just the adapter to the engine's ``generate_signals`` contract.
    """

    name = "graph"
    defaults = {"graph": None}

    def generate_signals(self, bars: list[Bar]) -> list[int]:
        if not self.graph:
            raise GraphValidationError("Strategy has no logic graph to run.")
        return evaluate_graph(self.graph, bars)
