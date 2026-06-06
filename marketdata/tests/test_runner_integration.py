"""The backtest runner prefers stored candles and flags synthetic fallback."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from backtester.models import Backtest, Strategy
from backtester.runner import load_bars, run_backtest
from marketdata.models import Candle


def seed_candles(symbol="BTCUSDT", timeframe="1d", days=60):
    start = timezone.make_aware(datetime(2023, 1, 1))
    price = 100.0
    candles = []
    for i in range(days):
        price *= 1.01 if i % 2 == 0 else 0.995
        candles.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=start + timedelta(days=i),
                open=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price,
                volume=1000,
            )
        )
    Candle.objects.bulk_create(candles)


class RunnerDataSourceTests(TestCase):
    def setUp(self):
        self.strategy = Strategy.objects.create(
            name="SMA", kind="sma_crossover", parameters={"fast": 3, "slow": 8}
        )

    def _backtest(self, symbol="BTCUSDT"):
        return Backtest.objects.create(
            strategy=self.strategy,
            symbol=symbol,
            timeframe="1d",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 2, 28),
        )

    def test_uses_stored_candles_when_available(self):
        seed_candles()
        bars, source = load_bars(self._backtest())
        self.assertEqual(source, "stored")
        self.assertGreater(len(bars), 0)

    def test_stored_run_has_no_synthetic_warning(self):
        seed_candles()
        bt = self._backtest()
        run_backtest(bt)
        bt.refresh_from_db()
        self.assertEqual(bt.status, Backtest.Status.COMPLETED)
        codes = {w["code"] for w in bt.warnings}
        self.assertNotIn("synthetic_data", codes)

    def test_falls_back_to_synthetic_with_warning(self):
        bt = self._backtest(symbol="NODATA")
        run_backtest(bt)
        bt.refresh_from_db()
        self.assertEqual(bt.status, Backtest.Status.COMPLETED)
        codes = {w["code"] for w in bt.warnings}
        self.assertIn("synthetic_data", codes)
