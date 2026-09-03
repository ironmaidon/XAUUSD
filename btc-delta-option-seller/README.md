# BTC Delta Exchange Option Seller V1

Safety-first BTC options platform implementing M0–M12. It includes exchange transports, historical persistence, shared strategy/risk analytics, defined-risk structures, research backtesting, paper execution, dashboard, recovery controls, and a guarded live limit-order adapter. Defaults are `PAPER`, live trading false, and disarmed on every startup. No HTTP/dashboard arming surface exists.

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

For development, run the backend with `.venv\Scripts\python -m uvicorn bos.dashboard.app:app --port 8000` and the frontend with `pnpm --dir frontend dev`. For a single production-style local URL, run `pnpm --dir frontend build` followed by `.venv\Scripts\bos serve-dashboard`; FastAPI serves the built dashboard and API together at `http://127.0.0.1:8000`.

Credentials are optional for public M1 verification and are read only from `DELTA_API_KEY` and `DELTA_API_SECRET`. Never commit `.env`.

See [ARCHITECTURE.md](ARCHITECTURE.md), [DELTA_API.md](DELTA_API.md), [CONFIGURATION.md](CONFIGURATION.md), and [LIVE_TRADING_SAFETY.md](LIVE_TRADING_SAFETY.md).
