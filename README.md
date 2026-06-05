# Strategy Tester

A Django project for defining trading strategies and running historical
backtests against them.

## Stack

- Python 3.11+
- Django 5.1
- SQLite (development default)

## Project layout

```
strategy_tester/      # Django project (settings, urls, wsgi/asgi)
backtester/           # Main app: strategies, backtests, trades
manage.py
requirements.txt
```

## Domain models

- **Strategy** — a named strategy definition with a `kind` (which engine
  implementation backs it) and free-form `parameters`.
- **Backtest** — one run of a strategy over a symbol and date range, with
  aggregate performance metrics (return, drawdown, Sharpe, win rate).
- **Trade** — an individual simulated trade produced by a backtest.

## Backtesting engine

The engine lives in `backtester/engine/` and is pure Python (no extra
dependencies):

```
engine/
  data.py          # Bar (OHLCV), CSV loader, synthetic data generator
  indicators.py    # SMA, EMA, RSI
  portfolio.py     # cash/position bookkeeping, equity curve, trade log
  metrics.py       # total return, max drawdown, Sharpe, win rate
  engine.py        # BacktestEngine: event-driven bar-by-bar loop
  runner.py        # runs a stored Backtest and persists results
  strategies/      # BaseStrategy + SMA crossover, RSI, and a registry
```

A strategy maps each bar to a target position (long / flat / short). The engine
opens and closes a fully invested position whenever the target changes,
marks the portfolio to market each bar, and computes performance metrics.

Built-in strategies:

- `sma_crossover` — long when the fast SMA is above the slow SMA
  (params: `fast`, `slow`, `allow_short`).
- `rsi` — buy oversold, exit overbought
  (params: `period`, `oversold`, `overbought`).

### Data sources

By default a deterministic synthetic price series is generated from the
backtest's date range (seeded by the symbol, so runs are reproducible). To use
your own data, add a `data_csv` key to the strategy's `parameters` pointing at a
CSV with `timestamp, open, high, low, close[, volume]` columns.

### Running backtests

```bash
# Seed a couple of demo strategies + backtests and run them
python manage.py seed_demo

# Run a specific backtest by id and print its metrics
python manage.py run_backtest <id>
```

Backtests can also be run from the Django admin via the
"Run selected backtests" action on the Backtest list.

## Getting started

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply database migrations
python manage.py migrate

# 4. Create an admin user
python manage.py createsuperuser

# 5. Run the development server
python manage.py runserver
```

Then open:

- Dashboard: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

## Configuration

Settings can be overridden with environment variables:

| Variable               | Default | Description                              |
| ---------------------- | ------- | ---------------------------------------- |
| `DJANGO_SECRET_KEY`    | (dev key) | Secret key — set a real one in production. |
| `DJANGO_DEBUG`         | `True`  | Set to `False` in production.            |
| `DJANGO_ALLOWED_HOSTS` | (empty) | Comma-separated list of allowed hosts.   |
