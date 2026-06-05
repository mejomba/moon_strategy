"""API tests for the strategies/backtests/trades endpoints."""

from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase

from backtester.models import Backtest, Strategy


class StrategyApiTests(APITestCase):
    def test_create_and_retrieve_preserves_strategy_json_envelope(self):
        """The free-form parameters (incl. the frontend `_meta`) round-trip."""
        payload = {
            "name": "SMA 10/30",
            "description": "fast/slow crossover",
            "kind": "sma_crossover",
            "status": "active",
            "parameters": {
                "fast": 10,
                "slow": 30,
                "allow_short": False,
                "_meta": {"schemaVersion": 1, "graph": None},
            },
        }
        resp = self.client.post("/api/strategies/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        strategy_id = resp.data["id"]

        resp = self.client.get(f"/api/strategies/{strategy_id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Byte-for-byte compatible with what the frontend sent (CLAUDE.md §5).
        self.assertEqual(resp.data["parameters"], payload["parameters"])
        self.assertEqual(resp.data["status"], "active")

    def test_list_returns_paginated_envelope(self):
        Strategy.objects.create(name="A", kind="rsi")
        resp = self.client.get("/api/strategies/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertEqual(resp.data["count"], 1)


class BacktestApiTests(APITestCase):
    def setUp(self):
        self.strategy = Strategy.objects.create(
            name="SMA", kind="sma_crossover", parameters={"fast": 5, "slow": 20}
        )

    def test_create_runs_synchronously_and_returns_metrics(self):
        payload = {
            "strategy": self.strategy.id,
            "symbol": "BTCUSDT",
            "timeframe": "1d",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 10000,
        }
        resp = self.client.post("/api/backtests/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], Backtest.Status.COMPLETED)
        # Metrics are populated on completion.
        self.assertIsNotNone(resp.data["final_equity"])
        self.assertIsNotNone(resp.data["total_return_pct"])
        self.assertEqual(resp.data["strategy_name"], "SMA")

    def test_rejects_inverted_date_range(self):
        payload = {
            "strategy": self.strategy.id,
            "symbol": "BTCUSDT",
            "timeframe": "1d",
            "start_date": "2023-12-31",
            "end_date": "2023-01-01",
            "initial_capital": 10000,
        }
        resp = self.client.post("/api/backtests/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", resp.data)

    def test_list_filters_by_strategy(self):
        other = Strategy.objects.create(name="Other", kind="rsi")
        Backtest.objects.create(
            strategy=self.strategy,
            symbol="BTCUSDT",
            start_date="2023-01-01",
            end_date="2023-02-01",
        )
        Backtest.objects.create(
            strategy=other,
            symbol="ETHUSDT",
            start_date="2023-01-01",
            end_date="2023-02-01",
        )
        resp = self.client.get(f"/api/backtests/?strategy={self.strategy.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["strategy"], self.strategy.id)

    def test_response_includes_cost_breakdown_and_warnings(self):
        payload = {
            "strategy": self.strategy.id,
            "symbol": "BTCUSDT",
            "timeframe": "1d",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 10000,
        }
        resp = self.client.post("/api/backtests/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Cost breakdown is populated on completion.
        self.assertIsNotNone(resp.data["total_commission"])
        self.assertIsNotNone(resp.data["total_funding"])
        # Every run carries at least the in-sample-only reliability warning.
        codes = {w["code"] for w in resp.data["warnings"]}
        self.assertIn("in_sample_only", codes)
        for warning in resp.data["warnings"]:
            self.assertIn(warning["severity"], {"info", "warning"})

    def test_detail_includes_equity_curve_but_list_does_not(self):
        payload = {
            "strategy": self.strategy.id,
            "symbol": "BTCUSDT",
            "timeframe": "1d",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 10000,
        }
        created = self.client.post("/api/backtests/", payload, format="json")
        backtest_id = created.data["id"]
        # The create/detail response carries a non-empty, well-shaped curve.
        self.assertIn("equity_curve", created.data)
        self.assertGreater(len(created.data["equity_curve"]), 0)
        point = created.data["equity_curve"][0]
        self.assertIn("t", point)
        self.assertIn("equity", point)

        detail = self.client.get(f"/api/backtests/{backtest_id}/")
        self.assertIn("equity_curve", detail.data)
        self.assertGreater(len(detail.data["equity_curve"]), 0)

        # The list endpoint stays light — no curve per row.
        listing = self.client.get("/api/backtests/")
        self.assertNotIn("equity_curve", listing.data["results"][0])

    def test_trades_endpoint_returns_trade_log(self):
        payload = {
            "strategy": self.strategy.id,
            "symbol": "BTCUSDT",
            "timeframe": "1d",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 10000,
        }
        created = self.client.post("/api/backtests/", payload, format="json")
        backtest_id = created.data["id"]
        resp = self.client.get(f"/api/backtests/{backtest_id}/trades/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)


class SchemaApiTests(APITestCase):
    def test_openapi_schema_is_served(self):
        resp = self.client.get("/api/schema/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


def _threshold_graph(value: float) -> dict:
    """enter_long when price > value, exit when price < value."""
    return {
        "nodes": [
            {"id": "p", "type": "indicator", "op": "price", "params": {}},
            {"id": "c", "type": "indicator", "op": "constant", "params": {"value": value}},
            {"id": "gt", "type": "condition", "op": "greater_than", "params": {}},
            {"id": "lt", "type": "condition", "op": "less_than", "params": {}},
            {"id": "enter", "type": "signal", "op": "enter_long", "params": {}},
            {"id": "exit", "type": "signal", "op": "exit", "params": {}},
        ],
        "edges": [
            {"id": "1", "source": "p", "target": "gt", "targetPort": "a"},
            {"id": "2", "source": "c", "target": "gt", "targetPort": "b"},
            {"id": "3", "source": "p", "target": "lt", "targetPort": "a"},
            {"id": "4", "source": "c", "target": "lt", "targetPort": "b"},
            {"id": "5", "source": "gt", "target": "enter", "targetPort": "in"},
            {"id": "6", "source": "lt", "target": "exit", "targetPort": "in"},
        ],
    }


class GraphStrategyApiTests(APITestCase):
    def _run(self, parameters: dict):
        strategy = Strategy.objects.create(
            name="Graph strat", kind="graph", parameters=parameters
        )
        return self.client.post(
            "/api/backtests/",
            {
                "strategy": strategy.id,
                "symbol": "BTCUSDT",
                "timeframe": "1d",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "initial_capital": 10000,
            },
            format="json",
        )

    def test_graph_strategy_runs_end_to_end(self):
        resp = self._run({"graph": _threshold_graph(100)})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], Backtest.Status.COMPLETED)
        self.assertIsNotNone(resp.data["final_equity"])

    def test_graph_from_legacy_meta_location_runs(self):
        resp = self._run({"_meta": {"schemaVersion": 1, "graph": _threshold_graph(100)}})
        self.assertEqual(resp.data["status"], Backtest.Status.COMPLETED)

    def test_invalid_graph_fails_with_message(self):
        bad = _threshold_graph(100)
        bad["nodes"] = [n for n in bad["nodes"] if n["id"] != "enter"]
        bad["edges"] = [e for e in bad["edges"] if e["target"] != "enter"]
        resp = self._run({"graph": bad})
        self.assertEqual(resp.data["status"], Backtest.Status.FAILED)
        self.assertIn("enter_long", resp.data["error_message"])


class CorsTests(APITestCase):
    def test_api_response_allows_the_frontend_origin(self):
        resp = self.client.get(
            "/api/strategies/", HTTP_ORIGIN="http://localhost:3000"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resp.headers.get("Access-Control-Allow-Origin"),
            "http://localhost:3000",
        )

    def test_disallowed_origin_gets_no_cors_header(self):
        resp = self.client.get(
            "/api/strategies/", HTTP_ORIGIN="http://evil.example.com"
        )
        self.assertNotIn("Access-Control-Allow-Origin", resp.headers)
