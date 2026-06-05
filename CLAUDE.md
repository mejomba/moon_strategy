# CLAUDE.md

This file gives Claude Code the context and rules for working in this repository.
Read it fully before making any change.

---

## 1. Project Overview

**Strategy Tester** is a no-code, web-based SaaS platform that lets traders **without
programming knowledge** build, backtest, optimize, and automatically execute trading
strategies for **crypto** and **forex (MetaTrader 5)** markets.

Full product cycle:

> Idea → Visual build → Backtest → Optimization → Paper trading → Live execution

- **Product type:** Commercial financial SaaS (web)
- **Target user:** Non-coder traders (no-code)
- **Team:** Single solo developer
- **Horizon:** 12–18 months

This is a **commercial product handling real money**. Correctness, safety, and data
quality matter more than speed of delivery. When in doubt, choose the safer option and
ask before proceeding.

---

## 2. Tech Stack

| Layer | Technology                                                                                                                                                                 |
|---|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Backend / Web | Python, **Django**                                                                                                                                                         |
| Frontend | **NextJS + with type script**, HTML, CSS (individual project, repository name is: [mejomba/moon_strategy_web_client](https://github.com/mejomba/moon_strategy_web_client)) |
| Forex bridge | **MQL5** Expert Advisor + Python bridge                                                                                                                                    |
| Backtest core | Pure **Python** (must stay framework-independent)                                                                                                                          |
| Historical data | Time-series oriented storage                                                                                                                                               |
| Strategy format | Intermediate **JSON / logic graph**                                                                                                                                        |

Constraints:
- Frontend is **React NextJS** by design. use UI/UX knowledge for make it useful and simple  
- The **backtest engine core must be a pure Python package, independent of Django**, so
  it can be tested and reused in isolation.

---

## 3. Critical Safety Rules (NEVER violate)

These come from the product's legal and risk requirements. They are non-negotiable.

1. **NEVER hold, custody, or transfer user funds** under any circumstance.
2. Exchange/broker API keys must be used with **trade permission only — NEVER withdrawal
   permission**. Never write code that requests, stores, or uses withdrawal access.
3. Every live-execution path must enforce internal **risk management**: max drawdown
   limit, max position size, and an emergency stop ("kill switch").
4. **Paper Trading must come before any live execution.** Do not wire a strategy to live
   orders without a working simulated path first.
5. Treat all secrets (API keys, credentials) as sensitive: never hard-code, never log,
   never commit them. Use environment variables / Django settings + `.env` (gitignored).
6. Surface clear legal disclaimers in any user-facing trading flow.

If a requested change would conflict with any rule above, **stop and flag it** instead of
implementing it.

---

## 4. Architecture — The Two Core Challenges

These two design decisions are the heart of the product. Discuss the plan before coding.

### a) Market Abstraction Layer
Crypto and MT5 differ in order structure, volume units, and data format. Define **one
internal "standard broker interface"**, and implement a **separate adapter per market**
(crypto adapter, MT5 adapter). All higher-level code talks only to the standard interface,
never to a specific market directly.

### b) Intermediate Strategy Language
A single intermediate representation (**JSON / logic graph**) that:
- is simple enough for the no-code visual builder to produce, and
- can be **executed by the Python backtest engine**, and
- can be **translated to MQL5** for forex live execution.

Keep this format as the single source of truth for a strategy. Changes to it ripple
everywhere — design it carefully and version it.

---

## 5. Scope

**In scope:** multi-timeframe historical data, no-code visual strategy builder, backtest
engine + performance reporting, paper trading then live execution, crypto via API + MT5
via Expert Advisor, user/subscription/billing.

**Out of scope (phase 1):** holding user funds (ever), strategy marketplace & copy
trading, dedicated mobile app, stocks/options markets. Do not build these unless asked.

---

## 6. Roadmap — Build in Phase Order

Do not jump ahead. **Phase 1 is crypto-only** (simpler, cheaper API). Forex/MT5 comes
later, after the core is stable.

| Phase | Months | Focus |
|---|---|---|
| 1. Backtest core | 1–5 | Backtest engine + data management + metrics (**crypto only**) |
| 2. No-code builder | 5–9 | Visual builder + intermediate JSON + reporting |
| 3. Crypto live | 9–12 | Exchange connection + paper trading + live with risk management |
| 4. Forex / MT5 | 12–15 | MT5 adapter + EA + MQL5 translator |
| 5. Polish & growth | 15–18 | Optimizer, walk-forward, marketplace |

When asked for a feature that belongs to a later phase, point this out before building.

---

## 7. Backtest Quality Requirements (product differentiator)

Naive backtests are misleading and must be avoided. The engine must model:
- Realistic **slippage, commission, spread, and overnight swap**.
- **Out-of-sample** testing and **walk-forward analysis**.
- **Overfitting warnings**.
- Clean, high-quality historical data (validate/clean on ingest).

Never produce backtest results that silently ignore trading costs.

---

## 8. Code Conventions

- Python: follow PEP 8; use type hints and doc string; keep functions small and testable.
- Django: organize by focused apps (e.g. `marketdata`, `backtest`, `strategies`,
  `execution`, `accounts`). Keep business logic out of views where reasonable.
- Keep the **backtest core decoupled** from Django (plain Python package).
- moon_strategy_web_client: modular files, no global namespace pollution, clear separation between
  UI and the strategy-JSON model.
- Names, comments, and commit messages in **English**.

---

## 9. Testing

- Write tests for every non-trivial change, especially for the **backtest engine** and
  **risk-management logic** — bugs there are financially costly.
- Run the test suite before committing.

```bash
python manage.py test          # Django tests
# (add backtest-core test command here once it exists, e.g. pytest)
```

---

## 10. Common Commands

```bash
python manage.py runserver     # dev server
python manage.py migrate       # apply migrations
python manage.py makemigrations
python manage.py test          # run tests
```

> Update this section as real commands/scripts are added to the project.

---

## 11. Workflow Expectations for Claude Code

1. **Plan first** for anything non-trivial (especially the two core challenges in §4):
   explain the approach before writing code.
2. Implement in **small, focused steps** — one task at a time.
3. **Write/extend tests** for the change.
4. **Commit** with a clear, descriptive message after a working unit of work.
5. Respect §3 safety rules absolutely; flag conflicts instead of working around them.
6. Stay within the current roadmap phase unless told otherwise.
