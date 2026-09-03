# Delta Exchange India API (M1)

Verified against the official v2 documentation on 2026-09-02:

- Production REST: `https://api.india.delta.exchange`
- Demo REST: `https://cdn-ind.testnet.deltaex.org`
- Production public WebSocket: `wss://public-socket.india.delta.exchange`
- Production private WebSocket: `wss://socket.india.delta.exchange`
- Demo public/private sockets: `wss://socket-ind-pub.testnet.deltaex.org` and `wss://socket-ind.testnet.deltaex.org`
- Products: `GET /v2/products`, `GET /v2/products/{symbol}`
- Tickers/option chain: `GET /v2/tickers`, `GET /v2/tickers/{symbol}` with option-chain filters `contract_types`, `underlying_asset_symbols`, and `expiry_date`

REST signing prehash is uppercase method + epoch-seconds timestamp + path + optional `?query` + compact JSON body. Required authenticated headers are `api-key`, `signature`, `timestamp`, and `User-Agent`.

Current private socket authentication is `key-auth`; its signature prehash is `GET` + timestamp + `/live`. The deprecated `auth` method is not implemented.

M11 adds authenticated contracts for `GET /v2/orders`, `DELETE /v2/orders`, `GET /v2/fills`, `GET /v2/positions`, `GET /v2/wallet/balances`, `POST /v2/heartbeat/create`, `POST /v2/heartbeat`, and `GET /v2/heartbeat`. The dead-man heartbeat is configured with `cancel_orders`; TTL is milliseconds. Public and private sockets enable the documented connection heartbeat after connect.

Schemas intentionally allow unknown fields so additive exchange changes do not break ingestion, while required identifiers and envelope shape are validated. Run `bos verify-public` to validate current public responses without secrets.
