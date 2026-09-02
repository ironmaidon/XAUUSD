# Architecture

The exchange adapter is an anti-corruption boundary. Strategy and risk code added in later milestones will depend on normalized providers, never HTTP/WebSocket details.

M0 provides typed configuration, structured logging, packaging, tests, and a minimal container. M1 provides HMAC signing, validated REST envelopes, product/ticker and BTC option-chain services, the newer public socket, and current `key-auth` private authentication.

Four modes share future strategy/risk code. Only market-data and execution providers may vary. `LIVE` needs a static environment gate and a separate transient arm state. Arm state is never persisted and resets false on construction/startup.

Transport objects own connection lifecycles. The public WebSocket reconnects with bounded exponential backoff and restores subscriptions. Private stream subscription/reconciliation, order execution, database persistence, heartbeat policy, and trading remain later milestones.

