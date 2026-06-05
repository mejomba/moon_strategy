# CLAUDE.md — Backend (Strategy Tester API)

This file gives Claude Code the context and rules for working in the **backend**
repository. Read it fully before making any change.

> The frontend lives in a **separate Next.js repository**. This repo is the **API
> backend only** — it serves JSON, not HTML pages.

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

## 2. Tech Stack (this repo)

| Layer | Technology |
|---|---|
| Web / API | Python, **Django** + **Django REST Framework (DRF)** |
| API schema | **OpenAPI** via `drf-spectacular` (source of truth for the frontend) |
| Backtest core | Pure **Python** package, **independent of Django** |
| Forex bridge | **MQL5** Expert Advisor + Python bridge |
| Historical data | Time-series oriented storage |
| Strategy format | Intermediate **JSON / logic graph** (shared with frontend) |

Constraints:
- This backend is an **API service**. Do **not** add server-rendered HTML templates or
  build UI here — the UI is the Next.js repo's job.
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
   never commit them. Use environment variables + `.env` (gitignored).
6. Expose clear legal disclaimers through the API where trading flows require them.

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
- is produced by the Next.js no-code visual builder,
- is **executed by the Python backtest engine** (this repo), and
- can be **translated to MQL5** for forex live execution.

This format is the **single source of truth for a strategy** and is **shared with the
frontend repo**. Keep its schema versioned. Any change here must be coordinated with the
frontend — flag it explicitly.

---

## 5. Frontend/Backend Contract (cross-repo)

The Next.js frontend is a separate repo and consumes this API.

- This repo owns the **API contract**. Generate/maintain the **OpenAPI schema**
  (`drf-spectacular`) so the frontend can generate its types/client from it.
- When you add or change an endpoint: update the serializer, the schema, and note the
  change so the frontend client can be updated in its own repo.
- Keep the **strategy JSON schema** byte-for-byte compatible with what the frontend
  builder produces.
- **Do not** put frontend code in this repo, and do not assume direct file access to the
  frontend — communicate through the API contract.

---

## 6. Scope

**In scope:** multi-timeframe historical data, backtest engine + performance reporting
(API), paper trading then live execution, crypto via API + MT5 via Expert Advisor,
user/subscription/billing, serving the no-code builder's needs via API.

**Out of scope (phase 1):** holding user funds (ever), strategy marketplace & copy
trading, dedicated mobile app, stocks/options markets. Do not build these unless asked.

---

## 7. Roadmap — Build in Phase Order

Do not jump ahead. **Phase 1 is crypto-only** (simpler, cheaper API). Forex/MT5 comes
later, after the core is stable.

| Phase | Months | Focus |
|---|---|---|
| 1. Backtest core | 1–5 | Backtest engine + data management + metrics (**crypto only**) |
| 2. No-code builder | 5–9 | Intermediate JSON + reporting API (UI built in frontend repo) |
| 3. Crypto live | 9–12 | Exchange connection + paper trading + live with risk management |
| 4. Forex / MT5 | 12–15 | MT5 adapter + EA + MQL5 translator |
| 5. Polish & growth | 15–18 | Optimizer, walk-forward, marketplace |

When asked for a feature that belongs to a later phase, point this out before building.

---

## 8. Backtest Quality Requirements (product differentiator)

Naive backtests are misleading and must be avoided. The engine must model:
- Realistic **slippage, commission, spread, and overnight swap**.
- **Out-of-sample** testing and **walk-forward analysis**.
- **Overfitting warnings**.
- Clean, high-quality historical data (validate/clean on ingest).

Never produce backtest results that silently ignore trading costs.

---

## 9. Code Conventions

- Python: follow PEP 8; use type hints; keep functions small and testable.
- Django: organize by focused apps (e.g. `marketdata`, `backtest`, `strategies`,
  `execution`, `accounts`). Keep business logic out of views/serializers where reasonable.
- Keep the **backtest core decoupled** from Django (plain Python package).
- All API responses are JSON; use DRF serializers; keep the OpenAPI schema in sync.
- Names, comments, and commit messages in **English**.

---

## 10. Testing

- Write tests for every non-trivial change, especially for the **backtest engine** and
  **risk-management logic** — bugs there are financially costly.
- Run the test suite before committing.

```bash
python manage.py test          # Django/DRF tests
# (add backtest-core test command here once it exists, e.g. pytest)
```

---

## 11. Common Commands

```bash
python manage.py runserver     # dev server (API)
python manage.py migrate
python manage.py makemigrations
python manage.py spectacular --file schema.yml   # regenerate OpenAPI schema
python manage.py test
```

> Update this section as real commands/scripts are added.

---

## 12. Workflow Expectations for Claude Code

1. **Plan first** for anything non-trivial (especially §4): explain the approach before
   writing code.
2. Implement in **small, focused steps** — one task at a time.
3. **Write/extend tests** for the change.
4. **Commit in this repo only** with a clear English message. Do not mix backend and
   frontend work in one commit.
5. When a change affects the API contract or strategy JSON, **call it out** so the
   frontend repo can be updated to match.
6. Respect §3 safety rules absolutely; flag conflicts instead of working around them.
7. Stay within the current roadmap phase unless told otherwise.
