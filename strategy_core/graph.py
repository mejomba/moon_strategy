"""Executable interpreter for the no-code strategy logic graph (CLAUDE.md §4b).

This turns the intermediate strategy-JSON graph — produced by the frontend
visual builder — into a per-bar sequence of target positions, the same contract
every other strategy implements (``generate_signals``). It is pure Python and
Django-independent so it can be unit tested and, later, mirrored by an MQL5
translator for forex live execution.

Graph shape (the shared v1 contract)::

    {
      "nodes": [{"id", "type", "op", "params": {...}}, ...],
      "edges": [{"id", "source", "target", "targetPort"?}, ...]
    }

Node types / ops:
  - indicator  → numeric series:  price, sma, ema, rsi, constant
  - condition  → boolean series:  greater_than, less_than, crosses_above,
                                   crosses_below            (ports "a", "b")
  - logic      → boolean series:  and, or (n-ary), not (one input)
  - signal     → boolean sink:    enter_long, exit          (port "in")

Position resolution: start flat; on each bar, if flat and any ``enter_long`` is
true go long; if long and any ``exit`` is true go flat.
"""

from __future__ import annotations

from strategy_core.data import Bar
from strategy_core.indicators import ema, rsi, sma
from strategy_core.strategies.base import FLAT, LONG

NUMERIC_OPS = {"price", "sma", "ema", "rsi", "constant"}
CONDITION_OPS = {"greater_than", "less_than", "crosses_above", "crosses_below"}
LOGIC_OPS = {"and", "or", "not"}
SIGNAL_OPS = {"enter_long", "exit"}
PRICE_SOURCES = {"open", "high", "low", "close"}

# Series "kind" produced by each node type.
NUMERIC = "numeric"
BOOLEAN = "boolean"


class GraphValidationError(ValueError):
    """Raised when a logic graph is structurally invalid or unrunnable."""


def evaluate_graph(graph: dict, bars: list[Bar]) -> list[int]:
    """Run a logic ``graph`` over ``bars`` and return one target position/bar."""
    interpreter = _GraphInterpreter(graph, bars)
    return interpreter.run()


class _GraphInterpreter:
    def __init__(self, graph: dict, bars: list[Bar]):
        if not isinstance(graph, dict):
            raise GraphValidationError("Graph must be an object with nodes/edges.")
        self.bars = bars
        self.n = len(bars)
        self.nodes: dict[str, dict] = {}
        for node in graph.get("nodes", []):
            node_id = node.get("id")
            if not node_id:
                raise GraphValidationError("Every node needs an id.")
            if node_id in self.nodes:
                raise GraphValidationError(f"Duplicate node id {node_id!r}.")
            self.nodes[node_id] = node

        self.edges = graph.get("edges", [])
        # Incoming edges per target node: {target_id: [(port, source_id), ...]}.
        self.incoming: dict[str, list[tuple[str, str]]] = {}
        for edge in self.edges:
            src, tgt = edge.get("source"), edge.get("target")
            if src not in self.nodes or tgt not in self.nodes:
                raise GraphValidationError("Edge references an unknown node.")
            self.incoming.setdefault(tgt, []).append((edge.get("targetPort"), src))

        self._cache: dict[str, tuple[str, list]] = {}
        self._visiting: set[str] = set()

    # -- public ---------------------------------------------------------------

    def run(self) -> list[int]:
        signals = [n for n in self.nodes.values() if n.get("type") == "signal"]
        enter_nodes = [n for n in signals if n.get("op") == "enter_long"]
        if not enter_nodes:
            raise GraphValidationError(
                "Graph needs at least one 'enter_long' signal node."
            )

        enters = [self._boolean_input(n) for n in enter_nodes]
        exits = [
            self._boolean_input(n) for n in signals if n.get("op") == "exit"
        ]

        positions: list[int] = []
        position = FLAT
        for i in range(self.n):
            if position == FLAT and any(series[i] for series in enters):
                position = LONG
            elif position == LONG and any(series[i] for series in exits):
                position = FLAT
            positions.append(position)
        return positions

    # -- evaluation -----------------------------------------------------------

    def _evaluate(self, node_id: str) -> tuple[str, list]:
        """Return ``(kind, series)`` for a node, memoised, detecting cycles."""
        if node_id in self._cache:
            return self._cache[node_id]
        if node_id in self._visiting:
            raise GraphValidationError("Graph contains a cycle.")
        self._visiting.add(node_id)

        node = self.nodes[node_id]
        node_type = node.get("type")
        op = node.get("op")

        if node_type == "indicator":
            result = (NUMERIC, self._numeric(node, op))
        elif node_type == "condition":
            result = (BOOLEAN, self._condition(node, op))
        elif node_type == "logic":
            result = (BOOLEAN, self._logic(node, op))
        else:
            raise GraphValidationError(
                f"Node {node_id!r} has unsupported type {node_type!r}."
            )

        self._visiting.discard(node_id)
        self._cache[node_id] = result
        return result

    def _numeric(self, node: dict, op: str) -> list:
        if op not in NUMERIC_OPS:
            raise GraphValidationError(f"Unknown indicator op {op!r}.")
        params = node.get("params") or {}

        if op == "constant":
            try:
                value = float(params["value"])
            except (KeyError, TypeError, ValueError):
                raise GraphValidationError("constant needs a numeric 'value'.")
            return [value] * self.n

        source = params.get("source", "close")
        if source not in PRICE_SOURCES:
            raise GraphValidationError(
                f"Invalid price source {source!r}; use one of {sorted(PRICE_SOURCES)}."
            )
        prices = [getattr(bar, source) for bar in self.bars]

        if op == "price":
            return prices
        period = _int_param(params, "period", op)
        if op == "sma":
            return sma(prices, period)
        if op == "ema":
            return ema(prices, period)
        return rsi(prices, period)  # op == "rsi"

    def _condition(self, node: dict, op: str) -> list:
        if op not in CONDITION_OPS:
            raise GraphValidationError(f"Unknown condition op {op!r}.")
        a = self._numeric_input(node, "a")
        b = self._numeric_input(node, "b")

        out = [False] * self.n
        for i in range(self.n):
            ai, bi = a[i], b[i]
            if ai is None or bi is None:
                continue
            if op == "greater_than":
                out[i] = ai > bi
            elif op == "less_than":
                out[i] = ai < bi
            elif op in ("crosses_above", "crosses_below"):
                if i == 0:
                    continue
                pa, pb = a[i - 1], b[i - 1]
                if pa is None or pb is None:
                    continue
                if op == "crosses_above":
                    out[i] = pa <= pb and ai > bi
                else:
                    out[i] = pa >= pb and ai < bi
        return out

    def _logic(self, node: dict, op: str) -> list:
        if op not in LOGIC_OPS:
            raise GraphValidationError(f"Unknown logic op {op!r}.")
        inputs = self._boolean_inputs(node)

        if op == "not":
            if len(inputs) != 1:
                raise GraphValidationError("'not' takes exactly one input.")
            return [not v for v in inputs[0]]

        if not inputs:
            raise GraphValidationError(f"'{op}' needs at least one input.")
        if op == "and":
            return [all(series[i] for series in inputs) for i in range(self.n)]
        return [any(series[i] for series in inputs) for i in range(self.n)]

    # -- input helpers --------------------------------------------------------

    def _sources_for(self, node: dict, port: str | None = None) -> list[str]:
        edges = self.incoming.get(node["id"], [])
        if port is None:
            return [src for _, src in edges]
        return [src for p, src in edges if p == port]

    def _numeric_input(self, node: dict, port: str) -> list:
        srcs = self._sources_for(node, port)
        if len(srcs) != 1:
            raise GraphValidationError(
                f"{node['op']!r} needs exactly one input on port {port!r}."
            )
        kind, series = self._evaluate(srcs[0])
        if kind != NUMERIC:
            raise GraphValidationError(
                f"Port {port!r} of {node['op']!r} expects a numeric input."
            )
        return series

    def _boolean_inputs(self, node: dict) -> list[list]:
        series_list = []
        for src in self._sources_for(node):
            kind, series = self._evaluate(src)
            if kind != BOOLEAN:
                raise GraphValidationError(
                    f"{node['op']!r} expects boolean inputs."
                )
            series_list.append(series)
        return series_list

    def _boolean_input(self, node: dict) -> list:
        srcs = self._sources_for(node)
        if len(srcs) != 1:
            raise GraphValidationError(
                f"Signal {node['op']!r} needs exactly one input."
            )
        kind, series = self._evaluate(srcs[0])
        if kind != BOOLEAN:
            raise GraphValidationError(
                f"Signal {node['op']!r} expects a boolean input."
            )
        return series


def _int_param(params: dict, key: str, op: str) -> int:
    try:
        value = int(params[key])
    except (KeyError, TypeError, ValueError):
        raise GraphValidationError(f"{op} needs an integer '{key}'.")
    if value < 1:
        raise GraphValidationError(f"{op} '{key}' must be >= 1.")
    return value
