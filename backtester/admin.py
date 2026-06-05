from django.contrib import admin, messages

from .engine.runner import run_backtest
from .models import Backtest, Strategy, Trade


class BacktestInline(admin.TabularInline):
    model = Backtest
    extra = 0
    fields = ("symbol", "timeframe", "start_date", "end_date", "status")
    show_change_link = True


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "status", "owner", "updated_at")
    list_filter = ("kind", "status")
    search_fields = ("name", "description")
    inlines = [BacktestInline]


class TradeInline(admin.TabularInline):
    model = Trade
    extra = 0
    fields = ("side", "quantity", "entry_time", "entry_price", "exit_price", "pnl")


@admin.register(Backtest)
class BacktestAdmin(admin.ModelAdmin):
    list_display = (
        "strategy",
        "symbol",
        "timeframe",
        "status",
        "total_return_pct",
        "created_at",
    )
    list_filter = ("status", "timeframe")
    search_fields = ("symbol", "strategy__name")
    inlines = [TradeInline]
    actions = ["run_selected_backtests"]

    @admin.action(description="Run selected backtests")
    def run_selected_backtests(self, request, queryset):
        succeeded = 0
        for backtest in queryset.select_related("strategy"):
            try:
                run_backtest(backtest)
                succeeded += 1
            except Exception as exc:  # noqa: BLE001
                self.message_user(
                    request,
                    f"{backtest}: {exc}",
                    level=messages.ERROR,
                )
        if succeeded:
            self.message_user(
                request, f"Ran {succeeded} backtest(s).", level=messages.SUCCESS
            )


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("backtest", "side", "quantity", "entry_time", "pnl")
    list_filter = ("side",)
