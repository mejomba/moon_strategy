from django.db import models


class Candle(models.Model):
    """A single historical OHLCV bar for a (symbol, timeframe).

    Stored market data backs backtests instead of the synthetic fallback. Data
    is validated/cleaned on ingest (CLAUDE.md §8) so the engine only ever sees
    high-quality candles.
    """

    symbol = models.CharField(max_length=32, db_index=True)
    timeframe = models.CharField(max_length=8)
    timestamp = models.DateTimeField()
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    volume = models.FloatField(default=0.0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["symbol", "timeframe", "timestamp"],
                name="uniq_candle_per_symbol_timeframe_ts",
            )
        ]
        indexes = [models.Index(fields=["symbol", "timeframe", "timestamp"])]
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.symbol} {self.timeframe} @ {self.timestamp:%Y-%m-%d}"
