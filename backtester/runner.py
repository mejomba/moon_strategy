"""Bridge between the engine and the Django ``Backtest`` model.

:func:`run_backtest` loads market data, runs the engine for a stored
:class:`~backtester.models.Backtest`, persists the resulting trades, and writes
the aggregate performance metrics back onto the row.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from strategy_core.costs import CostModel
from strategy_core.data import Bar, load_csv, synthetic_from_dates
from strategy_core.engine import BacktestEngine
from strategy_core.quality import assess_quality
from strategy_core.strategies import get_strategy


def _to_decimal(value, places: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places))


def build_cost_model(backtest) -> CostModel:
    """Construct the engine cost model from a backtest's cost settings."""
    return CostModel(
        commission_pct=backtest.commission_pct,
        slippage_bps=backtest.slippage_bps,
        spread_bps=backtest.spread_bps,
        funding_rate=backtest.funding_rate,
        funding_interval_hours=backtest.funding_interval_hours,
    )


def _load_stored_bars(backtest) -> list[Bar]:
    """Load ingested candles for this backtest's symbol/timeframe and range."""
    from marketdata.models import Candle

    candles = Candle.objects.filter(
        symbol=backtest.symbol,
        timeframe=backtest.timeframe,
        timestamp__date__gte=backtest.start_date,
        timestamp__date__lte=backtest.end_date,
    ).order_by("timestamp")
    return [
        Bar(
            timestamp=c.timestamp,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
        )
        for c in candles
    ]


def load_bars(backtest) -> tuple[list[Bar], str]:
    """Resolve market data for a backtest, returning ``(bars, source)``.

    Order of preference: an explicit ``data_csv`` path on the strategy, then
    ingested historical candles, then a deterministic synthetic series. The
    source is reported so the runner can warn when results rest on synthetic
    data (CLAUDE.md §8).
    """
    params = backtest.strategy.parameters or {}
    csv_path = params.get("data_csv")
    if csv_path:
        bars = load_csv(csv_path)
        bars = [
            b
            for b in bars
            if backtest.start_date <= b.timestamp.date() <= backtest.end_date
        ]
        return bars, "csv"

    stored = _load_stored_bars(backtest)
    if stored:
        return stored, "stored"

    # Stable per-symbol seed so synthetic runs are reproducible across
    # processes (Python's built-in hash() is salted per interpreter).
    digest = hashlib.md5(backtest.symbol.encode()).hexdigest()
    seed = int(digest[:8], 16)
    synthetic = synthetic_from_dates(
        backtest.start_date,
        backtest.end_date,
        timeframe=backtest.timeframe,
        seed=seed,
    )
    return synthetic, "synthetic"


SYNTHETIC_WARNING = {
    "code": "synthetic_data",
    "severity": "warning",
    "message": (
        "No historical data found for this symbol/timeframe, so a synthetic "
        "price series was used. Import real market data for meaningful results."
    ),
}


def run_backtest(backtest):
    """Execute ``backtest`` end-to-end and persist its results.

    Returns the updated :class:`~backtester.models.Backtest` instance. On
    failure the row is marked ``FAILED`` with the error message and the
    exception is re-raised.

    The result-persisting writes happen in a single transaction; the ``FAILED``
    bookkeeping is committed on its own so it survives the raised exception.
    """
    from backtester.models import Backtest, Trade

    backtest.status = Backtest.Status.RUNNING
    backtest.error_message = ""
    backtest.save(update_fields=["status", "error_message"])

    try:
        # Engine params come from the strategy's stored parameters, minus the
        # data-source key which is handled by ``load_bars``. No DB writes here.
        params = dict(backtest.strategy.parameters or {})
        params.pop("data_csv", None)
        # Graph strategies execute the logic graph stored under "graph"; accept
        # the frontend's legacy "_meta.graph" location as a fallback.
        if backtest.strategy.kind == "graph" and not params.get("graph"):
            meta = params.get("_meta") or {}
            if meta.get("graph"):
                params["graph"] = meta["graph"]
        strategy = get_strategy(backtest.strategy.kind, **params)

        bars, data_source = load_bars(backtest)
        engine = BacktestEngine(
            initial_capital=float(backtest.initial_capital),
            timeframe=backtest.timeframe,
            cost_model=build_cost_model(backtest),
        )
        result = engine.run(bars, strategy)
    except Exception as exc:  # noqa: BLE001 - we persist then re-raise
        backtest.status = Backtest.Status.FAILED
        backtest.error_message = f"{type(exc).__name__}: {exc}"
        backtest.completed_at = timezone.now()
        backtest.save(
            update_fields=["status", "error_message", "completed_at"]
        )
        raise

    with transaction.atomic():
        # Replace any trades from a previous run, then persist the new ones.
        backtest.trades.all().delete()
        Trade.objects.bulk_create(
            [
                Trade(
                    backtest=backtest,
                    side=t.side,
                    quantity=_to_decimal(t.quantity, "0.00000001"),
                    entry_time=t.entry_time,
                    entry_price=_to_decimal(t.entry_price, "0.00000001"),
                    exit_time=t.exit_time,
                    exit_price=(
                        _to_decimal(t.exit_price, "0.00000001")
                        if t.exit_price is not None
                        else None
                    ),
                    gross_pnl=(
                        _to_decimal(t.gross_pnl, "0.01")
                        if t.gross_pnl is not None
                        else None
                    ),
                    commission=_to_decimal(t.commission, "0.01"),
                    funding=_to_decimal(t.funding, "0.01"),
                    pnl=_to_decimal(t.pnl, "0.01") if t.pnl is not None else None,
                )
                for t in result.trades
            ]
        )

        m = result.metrics
        backtest.final_equity = _to_decimal(m.final_equity, "0.01")
        backtest.total_return_pct = m.total_return_pct
        backtest.max_drawdown_pct = m.max_drawdown_pct
        backtest.sharpe_ratio = m.sharpe_ratio
        backtest.win_rate_pct = m.win_rate_pct
        backtest.total_commission = _to_decimal(m.total_commission, "0.01")
        backtest.total_funding = _to_decimal(m.total_funding, "0.01")
        warnings = [
            w.to_dict()
            for w in assess_quality(m, float(backtest.initial_capital))
        ]
        if data_source == "synthetic":
            warnings.insert(0, SYNTHETIC_WARNING)
        backtest.warnings = warnings
        backtest.equity_curve = _serialize_equity_curve(result.equity_curve)
        backtest.status = Backtest.Status.COMPLETED
        backtest.completed_at = timezone.now()
        backtest.save()
    return backtest


# Cap stored points so long (e.g. minute-resolution) runs stay light to fetch
# and chart; the curve is downsampled evenly, always keeping the last point.
MAX_EQUITY_POINTS = 1500


def _serialize_equity_curve(curve) -> list[dict]:
    """Convert the engine's ``[(datetime, equity), ...]`` into JSON points."""
    points = curve or []
    step = max(1, len(points) // MAX_EQUITY_POINTS)
    sampled = points[::step]
    if points and sampled[-1] is not points[-1]:
        sampled.append(points[-1])
    return [
        {"t": when.isoformat(), "equity": round(float(equity), 2)}
        for when, equity in sampled
    ]
