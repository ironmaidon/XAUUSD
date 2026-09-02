# Configuration

Defaults live in `config/default.yaml`; sensitive values must only use environment variables. Nested names use double underscores, for example `BOS_EXCHANGE__ENVIRONMENT=testnet`.

`BOS_MODE` is one of `BACKTEST`, `REPLAY`, `PAPER`, or `LIVE`. `PAPER` is the default. `BOS_LIVE__LIVE_TRADING=false` is the default and `LIVE` validation fails unless it is explicitly true. This static gate still does not arm the process.

Secrets use the exact environment names `DELTA_API_KEY` and `DELTA_API_SECRET`. They are represented by Pydantic `SecretStr`, excluded from object representations, and must never be logged. `.env` is ignored; `.env.example` contains blank placeholders only.
