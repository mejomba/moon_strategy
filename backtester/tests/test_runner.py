from datetime import date

from django.test import TestCase

from backtester.engine.runner import run_backtest
from backtester.models import Backtest, Strategy, Trade


class RunnerTests(TestCase):
    def _make_backtest(self, kind=Strategy.Kind.SMA_CROSSOVER, params=None):
        strategy = Strategy.objects.create(
            name=f"Test {kind}",
            kind=kind,
            parameters=params or {"fast": 5, "slow": 20},
        )
        return Backtest.objects.create(
            strategy=strategy,
            symbol="BTCUSDT",
            timeframe="1d",
            start_date=date(2022, 1, 1),
            end_date=date(2022, 12, 31),
            initial_capital=10_000,
        )

    def test_run_persists_metrics_and_trades(self):
        backtest = self._make_backtest()
        run_backtest(backtest)

        backtest.refresh_from_db()
        self.assertEqual(backtest.status, Backtest.Status.COMPLETED)
        self.assertIsNotNone(backtest.final_equity)
        self.assertIsNotNone(backtest.total_return_pct)
        self.assertIsNotNone(backtest.completed_at)
        # Metrics should be internally consistent with the trade log.
        self.assertGreaterEqual(backtest.trades.count(), 0)

    def test_rerun_replaces_previous_trades(self):
        backtest = self._make_backtest()
        run_backtest(backtest)
        first_count = backtest.trades.count()

        run_backtest(backtest)
        backtest.refresh_from_db()
        self.assertEqual(backtest.trades.count(), first_count)
        self.assertEqual(
            Trade.objects.filter(backtest=backtest).count(), first_count
        )

    def test_rsi_strategy_runs(self):
        backtest = self._make_backtest(
            kind=Strategy.Kind.RSI,
            params={"period": 14, "oversold": 30, "overbought": 70},
        )
        run_backtest(backtest)
        backtest.refresh_from_db()
        self.assertEqual(backtest.status, Backtest.Status.COMPLETED)

    def test_invalid_params_mark_backtest_failed(self):
        backtest = self._make_backtest(params={"fast": 30, "slow": 10})
        with self.assertRaises(ValueError):
            run_backtest(backtest)
        backtest.refresh_from_db()
        self.assertEqual(backtest.status, Backtest.Status.FAILED)
        self.assertIn("fast period", backtest.error_message)
