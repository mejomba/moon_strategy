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

from backtester.engine.data import Bar, load_csv, synthetic_from_dates
from backtester.engine.engine import BacktestEngine
from backtester.engine.strategies import get_strategy


def _to_decimal(value, places: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places))


def load_bars(backtest) -> list[Bar]:
    """Resolve market data for a backtest.

    If the strategy parameters include a ``data_csv`` path, bars are loaded from
    that file; otherwise a deterministic synthetic series is generated from the
    backtest's date range (seeded by the symbol so runs are reproducible).
    """
    params = backtest.strategy.parameters or {}
    csv_path = params.get("data_csv")
    if csv_path:
        bars = load_csv(csv_path)
        return [
            b
            for b in bars
            if backtest.start_date <= b.timestamp.date() <= backtest.end_date
        ]
    # Stable per-symbol seed so synthetic runs are reproducible across
    # processes (Python's built-in hash() is salted per interpreter).
    digest = hashlib.md5(backtest.symbol.encode()).hexdigest()
    seed = int(digest[:8], 16)
    return synthetic_from_dates(
        backtest.start_date,
        backtest.end_date,
        timeframe=backtest.timeframe,
        seed=seed,
    )


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
        strategy = get_strategy(backtest.strategy.kind, **params)

        bars = load_bars(backtest)
        engine = BacktestEngine(
            initial_capital=float(backtest.initial_capital),
            timeframe=backtest.timeframe,
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
        backtest.status = Backtest.Status.COMPLETED
        backtest.completed_at = timezone.now()
        backtest.save()
    return backtest
