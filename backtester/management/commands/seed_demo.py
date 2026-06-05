"""Create a couple of demo strategies and backtests, then run them.

Useful for kicking the tyres on a fresh database::

    python manage.py seed_demo
"""

from datetime import date

from django.core.management.base import BaseCommand

from backtester.engine.runner import run_backtest
from backtester.models import Backtest, Strategy


class Command(BaseCommand):
    help = "Create demo strategies and backtests and run them."

    def handle(self, *args, **options):
        sma, _ = Strategy.objects.get_or_create(
            name="Demo SMA 10/30",
            defaults={
                "kind": Strategy.Kind.SMA_CROSSOVER,
                "parameters": {"fast": 10, "slow": 30},
                "status": Strategy.Status.ACTIVE,
                "description": "Fast/slow SMA crossover demo strategy.",
            },
        )
        rsi, _ = Strategy.objects.get_or_create(
            name="Demo RSI 14",
            defaults={
                "kind": Strategy.Kind.RSI,
                "parameters": {"period": 14, "oversold": 30, "overbought": 70},
                "status": Strategy.Status.ACTIVE,
                "description": "RSI mean-reversion demo strategy.",
            },
        )

        for strategy in (sma, rsi):
            backtest = Backtest.objects.create(
                strategy=strategy,
                symbol="BTCUSDT",
                timeframe="1d",
                start_date=date(2022, 1, 1),
                end_date=date(2023, 12, 31),
                initial_capital=10_000,
            )
            run_backtest(backtest)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{strategy.name}: return {backtest.total_return_pct:.2f}%, "
                    f"{backtest.trades.count()} trades"
                )
            )
