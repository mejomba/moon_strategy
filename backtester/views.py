from django.db.models import Count
from django.shortcuts import render

from .models import Backtest, Strategy


def dashboard(request):
    """Landing page summarising strategies and recent backtests."""
    context = {
        "strategy_count": Strategy.objects.count(),
        "backtest_count": Backtest.objects.count(),
        "strategies": Strategy.objects.annotate(
            run_count=Count("backtests")
        )[:10],
        "recent_backtests": Backtest.objects.select_related("strategy")[:10],
    }
    return render(request, "backtester/dashboard.html", context)
