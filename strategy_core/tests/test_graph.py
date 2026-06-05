"""Unit tests for the logic-graph interpreter (no Django)."""

import unittest
from datetime import datetime, timedelta

from strategy_core.data import Bar
from strategy_core.graph import GraphValidationError, evaluate_graph


def make_bars(closes: list[float]) -> list[Bar]:
    start = datetime(2023, 1, 1)
    return [
        Bar(
            timestamp=start + timedelta(days=i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=0.0,
        )
        for i, c in enumerate(closes)
    ]


def price_vs_constant_graph(value: float) -> dict:
    """enter_long when price > value, exit when price < value."""
    return {
        "nodes": [
            {"id": "p", "type": "indicator", "op": "price", "params": {"source": "close"}},
            {"id": "c", "type": "indicator", "op": "constant", "params": {"value": value}},
            {"id": "gt", "type": "condition", "op": "greater_than", "params": {}},
            {"id": "lt", "type": "condition", "op": "less_than", "params": {}},
            {"id": "enter", "type": "signal", "op": "enter_long", "params": {}},
            {"id": "exit", "type": "signal", "op": "exit", "params": {}},
        ],
        "edges": [
            {"id": "e1", "source": "p", "target": "gt", "targetPort": "a"},
            {"id": "e2", "source": "c", "target": "gt", "targetPort": "b"},
            {"id": "e3", "source": "p", "target": "lt", "targetPort": "a"},
            {"id": "e4", "source": "c", "target": "lt", "targetPort": "b"},
            {"id": "e5", "source": "gt", "target": "enter", "targetPort": "in"},
            {"id": "e6", "source": "lt", "target": "exit", "targetPort": "in"},
        ],
    }


class GraphExecutionTests(unittest.TestCase):
    def test_threshold_entry_and_exit(self):
        graph = price_vs_constant_graph(100)
        positions = evaluate_graph(graph, make_bars([90, 110, 120, 95, 90]))
        self.assertEqual(positions, [0, 1, 1, 0, 0])

    def test_crosses_above_semantics(self):
        graph = {
            "nodes": [
                {"id": "p", "type": "indicator", "op": "price", "params": {}},
                {"id": "c", "type": "indicator", "op": "constant", "params": {"value": 2}},
                {"id": "x", "type": "condition", "op": "crosses_above", "params": {}},
                {"id": "enter", "type": "signal", "op": "enter_long", "params": {}},
            ],
            "edges": [
                {"id": "1", "source": "p", "target": "x", "targetPort": "a"},
                {"id": "2", "source": "c", "target": "x", "targetPort": "b"},
                {"id": "3", "source": "x", "target": "enter", "targetPort": "in"},
            ],
        }
        # price crosses above 2 only at index 2 (1 -> 2 -> 3).
        positions = evaluate_graph(graph, make_bars([1, 2, 3]))
        self.assertEqual(positions, [0, 0, 1])

    def test_sma_crossover_graph_runs(self):
        graph = {
            "nodes": [
                {"id": "f", "type": "indicator", "op": "sma", "params": {"period": 2}},
                {"id": "s", "type": "indicator", "op": "sma", "params": {"period": 4}},
                {"id": "up", "type": "condition", "op": "crosses_above", "params": {}},
                {"id": "dn", "type": "condition", "op": "crosses_below", "params": {}},
                {"id": "enter", "type": "signal", "op": "enter_long", "params": {}},
                {"id": "exit", "type": "signal", "op": "exit", "params": {}},
            ],
            "edges": [
                {"id": "1", "source": "f", "target": "up", "targetPort": "a"},
                {"id": "2", "source": "s", "target": "up", "targetPort": "b"},
                {"id": "3", "source": "f", "target": "dn", "targetPort": "a"},
                {"id": "4", "source": "s", "target": "dn", "targetPort": "b"},
                {"id": "5", "source": "up", "target": "enter", "targetPort": "in"},
                {"id": "6", "source": "dn", "target": "exit", "targetPort": "in"},
            ],
        }
        closes = [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4]
        positions = evaluate_graph(graph, make_bars(closes))
        self.assertEqual(len(positions), len(closes))
        self.assertIn(1, positions)  # goes long at some point
        self.assertTrue(all(p in (0, 1) for p in positions))

    def test_and_logic_combines_conditions(self):
        graph = {
            "nodes": [
                {"id": "p", "type": "indicator", "op": "price", "params": {}},
                {"id": "lo", "type": "indicator", "op": "constant", "params": {"value": 10}},
                {"id": "hi", "type": "indicator", "op": "constant", "params": {"value": 20}},
                {"id": "gt", "type": "condition", "op": "greater_than", "params": {}},
                {"id": "lt", "type": "condition", "op": "less_than", "params": {}},
                {"id": "band", "type": "logic", "op": "and", "params": {}},
                {"id": "enter", "type": "signal", "op": "enter_long", "params": {}},
            ],
            "edges": [
                {"id": "1", "source": "p", "target": "gt", "targetPort": "a"},
                {"id": "2", "source": "lo", "target": "gt", "targetPort": "b"},
                {"id": "3", "source": "p", "target": "lt", "targetPort": "a"},
                {"id": "4", "source": "hi", "target": "lt", "targetPort": "b"},
                {"id": "5", "source": "gt", "target": "band"},
                {"id": "6", "source": "lt", "target": "band"},
                {"id": "7", "source": "band", "target": "enter", "targetPort": "in"},
            ],
        }
        # In range (10,20) only on the middle bar.
        positions = evaluate_graph(graph, make_bars([5, 15, 25]))
        self.assertEqual(positions, [0, 1, 1])


class GraphValidationTests(unittest.TestCase):
    def test_requires_an_enter_long(self):
        graph = price_vs_constant_graph(100)
        graph["nodes"] = [n for n in graph["nodes"] if n["id"] != "enter"]
        graph["edges"] = [e for e in graph["edges"] if e["target"] != "enter"]
        with self.assertRaises(GraphValidationError):
            evaluate_graph(graph, make_bars([1, 2, 3]))

    def test_detects_cycle(self):
        graph = {
            "nodes": [
                {"id": "a", "type": "logic", "op": "not", "params": {}},
                {"id": "b", "type": "logic", "op": "not", "params": {}},
                {"id": "enter", "type": "signal", "op": "enter_long", "params": {}},
            ],
            "edges": [
                {"id": "1", "source": "a", "target": "b"},
                {"id": "2", "source": "b", "target": "a"},
                {"id": "3", "source": "b", "target": "enter", "targetPort": "in"},
            ],
        }
        with self.assertRaises(GraphValidationError):
            evaluate_graph(graph, make_bars([1, 2, 3]))

    def test_unknown_op(self):
        graph = {
            "nodes": [
                {"id": "x", "type": "indicator", "op": "frobnicate", "params": {}},
                {"id": "enter", "type": "signal", "op": "enter_long", "params": {}},
            ],
            "edges": [{"id": "1", "source": "x", "target": "enter", "targetPort": "in"}],
        }
        with self.assertRaises(GraphValidationError):
            evaluate_graph(graph, make_bars([1, 2, 3]))

    def test_missing_condition_input(self):
        graph = price_vs_constant_graph(100)
        # Drop the edge feeding port "b" of the greater_than node.
        graph["edges"] = [
            e
            for e in graph["edges"]
            if not (e["target"] == "gt" and e.get("targetPort") == "b")
        ]
        with self.assertRaises(GraphValidationError):
            evaluate_graph(graph, make_bars([1, 2, 3]))

    def test_type_mismatch_boolean_into_numeric_port(self):
        graph = {
            "nodes": [
                {"id": "p", "type": "indicator", "op": "price", "params": {}},
                {"id": "c", "type": "indicator", "op": "constant", "params": {"value": 1}},
                {"id": "cond", "type": "condition", "op": "greater_than", "params": {}},
                {"id": "bad", "type": "condition", "op": "greater_than", "params": {}},
                {"id": "enter", "type": "signal", "op": "enter_long", "params": {}},
            ],
            "edges": [
                {"id": "1", "source": "p", "target": "cond", "targetPort": "a"},
                {"id": "2", "source": "c", "target": "cond", "targetPort": "b"},
                # Feed a boolean (cond) into a numeric port of another condition.
                {"id": "3", "source": "cond", "target": "bad", "targetPort": "a"},
                {"id": "4", "source": "c", "target": "bad", "targetPort": "b"},
                {"id": "5", "source": "bad", "target": "enter", "targetPort": "in"},
            ],
        }
        with self.assertRaises(GraphValidationError):
            evaluate_graph(graph, make_bars([1, 2, 3]))

    def test_constant_requires_value(self):
        graph = price_vs_constant_graph(100)
        for node in graph["nodes"]:
            if node["id"] == "c":
                node["params"] = {}
        with self.assertRaises(GraphValidationError):
            evaluate_graph(graph, make_bars([1, 2, 3]))


if __name__ == "__main__":
    unittest.main()
