"""Run a stored backtest by id and print its results."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from backtester.runner import run_backtest
from backtester.models import Backtest


class Command(BaseCommand):
    help = "Run the backtest with the given id and persist its results."

    def add_arguments(self, parser):
        parser.add_argument("backtest_id", type=int, help="Backtest primary key")

    def handle(self, *args, **options):
        pk = options["backtest_id"]
        try:
            backtest = Backtest.objects.select_related("strategy").get(pk=pk)
        except Backtest.DoesNotExist as exc:
            raise CommandError(f"Backtest {pk} does not exist") from exc

        self.stdout.write(f"Running backtest #{pk}: {backtest}...")
        run_backtest(backtest)

        if backtest.status == Backtest.Status.FAILED:
            raise CommandError(f"Backtest failed: {backtest.error_message}")

        costs = backtest.trades.aggregate(
            commission=Sum("commission"), funding=Sum("funding")
        )
        commission = costs["commission"] or 0
        funding = costs["funding"] or 0

        self.stdout.write(self.style.SUCCESS("Completed."))
        self.stdout.write(f"  Trades:        {backtest.trades.count()}")
        self.stdout.write(f"  Final equity:  {backtest.final_equity}")
        self.stdout.write(f"  Total return:  {backtest.total_return_pct:.2f}%")
        self.stdout.write(f"  Max drawdown:  {backtest.max_drawdown_pct:.2f}%")
        self.stdout.write(f"  Sharpe ratio:  {backtest.sharpe_ratio:.2f}")
        self.stdout.write(f"  Win rate:      {backtest.win_rate_pct:.2f}%")
        self.stdout.write(f"  Commission:    {commission}")
        self.stdout.write(f"  Funding:       {funding}")
