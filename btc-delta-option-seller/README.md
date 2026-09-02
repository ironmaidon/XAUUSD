# BTC Delta Exchange Option Seller V1

Safety-first BTC options platform. M0–M2 provide the exchange transports, historical downloader, SQLAlchemy store, and Parquet archive. It cannot place orders: `DeltaOrderService` deliberately exposes no submission method. Defaults are `PAPER`, live trading false, and disarmed on every startup.

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

Credentials are optional for public M1 verification and are read only from `DELTA_API_KEY` and `DELTA_API_SECRET`. Never commit `.env`.

See [ARCHITECTURE.md](ARCHITECTURE.md), [DELTA_API.md](DELTA_API.md), [CONFIGURATION.md](CONFIGURATION.md), and [LIVE_TRADING_SAFETY.md](LIVE_TRADING_SAFETY.md).
