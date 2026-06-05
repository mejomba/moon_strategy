# Strategy Tester

A Django project for defining trading strategies and running historical
backtests against them.

## Stack

- Python 3.11+
- Django 5.1
- SQLite (development default)

## Project layout

```
strategy_core/        # Pure-Python backtest core (no Django dependency)
strategy_tester/      # Django project (settings, urls, wsgi/asgi)
backtester/           # Django app: models, admin, runner glue, commands
manage.py
requirements.txt
```

The **backtest core is a standalone Python package** (`strategy_core/`),
independent of Django so it can be tested and reused in isolation. The
`backtester` Django app glues it to the database (`backtester/runner.py`).

## Domain models

- **Strategy** — a named strategy definition with a `kind` (which engine
  implementation backs it) and free-form `parameters`.
- **Backtest** — one run of a strategy over a symbol and date range, with
  aggregate performance metrics (return, drawdown, Sharpe, win rate).
- **Trade** — an individual simulated trade produced by a backtest.

## Backtesting engine (`strategy_core`)

The engine is pure Python with no external dependencies:

```
strategy_core/
  data.py          # Bar (OHLCV), CSV loader, synthetic data generator
  indicators.py    # SMA, EMA, RSI
  costs.py         # CostModel: commission, slippage, spread, funding/swap
  portfolio.py     # cash/position bookkeeping, equity curve, trade log
  metrics.py       # total return, max drawdown, Sharpe, win rate, costs
  engine.py        # BacktestEngine: event-driven bar-by-bar loop
  strategies/      # BaseStrategy + SMA crossover, RSI, and a registry
  tests/           # pure unittest suite (no Django required)
```

A strategy maps each bar to a target position (long / flat / short). The engine
opens and closes a fully invested position whenever the target changes — routing
every fill through the cost model — accrues funding for the holding period,
marks the portfolio to market each bar, and computes performance metrics.

Built-in strategies:

- `sma_crossover` — long when the fast SMA is above the slow SMA
  (params: `fast`, `slow`, `allow_short`).
- `rsi` — buy oversold, exit overbought
  (params: `period`, `oversold`, `overbought`).

### Trading costs

Backtests model realistic trading costs (no result silently ignores them).
Each `Backtest` carries cost settings, defaulting to a liquid crypto pair:

| Field                    | Default  | Meaning                                  |
| ------------------------ | -------- | ---------------------------------------- |
| `commission_pct`         | `0.0004` | Taker fee per side (0.04%)               |
| `slippage_bps`           | `1.0`    | Adverse fill per side (basis points)     |
| `spread_bps`             | `1.0`    | Half-spread crossed per side (bps)       |
| `funding_rate`           | `0.0`    | Funding per interval (longs pay if > 0)  |
| `funding_interval_hours` | `8.0`    | Hours between funding charges            |

Each `Trade` records `gross_pnl`, `commission`, `funding`, and net `pnl`.

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

## Testing

```bash
# Backtest core (pure Python, no Django/database needed)
python -m unittest discover -s strategy_core/tests -t .

# Django app (models, runner, persistence)
python manage.py test backtester
```

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
