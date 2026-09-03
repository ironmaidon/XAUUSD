# Architecture

The exchange adapter is an anti-corruption boundary. Strategy and risk code added in later milestones will depend on normalized providers, never HTTP/WebSocket details.

M0 provides typed configuration, structured logging, packaging, tests, and a minimal container. M1 provides HMAC signing, validated REST envelopes, product/ticker and BTC option-chain services, the newer public socket, and current `key-auth` private authentication.

Four modes share future strategy/risk code. Only market-data and execution providers may vary. `LIVE` needs a static environment gate and a separate transient arm state. Arm state is never persisted and resets false on construction/startup.

Transport objects own connection lifecycles. The public WebSocket reconnects with bounded exponential backoff and restores subscriptions. Private stream subscription/reconciliation, order execution, database persistence, heartbeat policy, and trading remain later milestones.

M2 adds normalized candle/product persistence through SQLAlchemy, using SQLite locally and portable ORM types for later PostgreSQL migration. Raw history is also written as compressed Parquet with embedded provenance and quality metadata. Download manifests provide an audit trail independent of the data files.

M9 introduces a mode-independent `ExecutionProvider` contract and a paper implementation. Normalized real-time option quotes are pushed through the same provider boundary future live execution will implement. Immutable request, order, and fill records are shared across modes; paper records carry an explicit simulated flag and use the common append-only SQL journal.

M10 exposes an atomic dashboard read model through FastAPI REST and WebSocket endpoints. Strategy, market-data, risk, execution, and research services publish complete normalized snapshots; the UI never reads the trading database directly. The React/TypeScript/Vite client consumes one typed snapshot and provides dedicated overview, chain, strategy, positions, orders, risk, backtests, settings, and logs views. Live arming is intentionally not exposed.

M11 adds a safety coordinator above the mode-specific execution provider. Entry ordering is protective buys before shorts; exits and abort cleanup eliminate short exposure before removing wings. Repricing is bounded and client IDs are unique and within 32 characters. Heartbeat acknowledgment runs independently of strategy evaluation and fails health closed. Startup/reconnect reconciliation fetches wallet, positions, open orders, and fills concurrently through an exchange gateway; any mismatch blocks entries and unexpected exposure is reconstructed from exchange state.
