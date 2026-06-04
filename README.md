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

- **Strategy** — a named strategy definition with free-form `parameters`.
- **Backtest** — one run of a strategy over a symbol and date range, with
  aggregate performance metrics (return, drawdown, Sharpe, win rate).
- **Trade** — an individual simulated trade produced by a backtest.

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
