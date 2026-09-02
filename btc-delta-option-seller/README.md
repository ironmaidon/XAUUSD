# BTC Delta Exchange Option Seller V1

Safety-first BTC options platform. M0–M10 provide exchange transports, historical persistence, production-shared strategy/risk analytics, defined-risk structures, research backtesting, realistic paper execution, and a FastAPI + React operations dashboard. It cannot place real orders: `DeltaOrderService` deliberately exposes no submission method. Defaults are `PAPER`, live trading false, and disarmed on every startup.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check .
.venv\Scripts\mypy src
.venv\Scripts\bos verify-public --config config/default.yaml
.venv\Scripts\bos verify-history --config config/default.yaml
```

Run the dashboard backend with `.venv\Scripts\python -m uvicorn bos.dashboard.app:app --port 8000` and the frontend with `pnpm --dir frontend dev`. The frontend proxies `/api` and `/ws` to the local backend.

Credentials are optional for public M1 verification and are read only from `DELTA_API_KEY` and `DELTA_API_SECRET`. Never commit `.env`.

See [ARCHITECTURE.md](ARCHITECTURE.md), [DELTA_API.md](DELTA_API.md), [CONFIGURATION.md](CONFIGURATION.md), and [LIVE_TRADING_SAFETY.md](LIVE_TRADING_SAFETY.md).
