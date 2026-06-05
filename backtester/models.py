from django.conf import settings
from django.db import models


class Strategy(models.Model):
    """A trading strategy definition that can be backtested."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    class Kind(models.TextChoices):
        SMA_CROSSOVER = "sma_crossover", "SMA Crossover"
        RSI = "rsi", "RSI"

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    # Which engine implementation backs this strategy (see engine.strategies).
    kind = models.CharField(
        max_length=32, choices=Kind.choices, default=Kind.SMA_CROSSOVER
    )
    # Free-form parameters for the strategy (e.g. indicator periods, thresholds).
    parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="strategies",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "strategies"

    def __str__(self):
        return self.name


class Backtest(models.Model):
    """A single run of a strategy over a historical date range."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    strategy = models.ForeignKey(
        Strategy, on_delete=models.CASCADE, related_name="backtests"
    )
    symbol = models.CharField(max_length=32, help_text="Instrument ticker, e.g. BTCUSDT")
    timeframe = models.CharField(
        max_length=8, default="1d", help_text="Candle timeframe, e.g. 1m, 1h, 1d"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    initial_capital = models.DecimalField(
        max_digits=18, decimal_places=2, default=10000
    )

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    # Aggregate performance metrics, populated when the run completes.
    final_equity = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    total_return_pct = models.FloatField(null=True, blank=True)
    max_drawdown_pct = models.FloatField(null=True, blank=True)
    sharpe_ratio = models.FloatField(null=True, blank=True)
    win_rate_pct = models.FloatField(null=True, blank=True)

    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.strategy.name} · {self.symbol} ({self.start_date}–{self.end_date})"


class Trade(models.Model):
    """An individual simulated trade produced by a backtest."""

    class Side(models.TextChoices):
        LONG = "long", "Long"
        SHORT = "short", "Short"

    backtest = models.ForeignKey(
        Backtest, on_delete=models.CASCADE, related_name="trades"
    )
    side = models.CharField(max_length=5, choices=Side.choices, default=Side.LONG)
    quantity = models.DecimalField(max_digits=18, decimal_places=8)
    entry_time = models.DateTimeField()
    entry_price = models.DecimalField(max_digits=18, decimal_places=8)
    exit_time = models.DateTimeField(null=True, blank=True)
    exit_price = models.DecimalField(
        max_digits=18, decimal_places=8, null=True, blank=True
    )
    pnl = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["entry_time"]

    def __str__(self):
        return f"{self.get_side_display()} {self.quantity} @ {self.entry_price}"
