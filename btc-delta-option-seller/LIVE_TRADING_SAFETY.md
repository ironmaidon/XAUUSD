# Live Trading Safety

M1 has no order placement implementation and therefore cannot trade. Enabling the configuration gate does not add that capability.

Future live operation requires both `BOS_LIVE__LIVE_TRADING=true` and a manual, in-memory arm action after successful heartbeat and exchange-authoritative reconciliation. Every startup resets armed state to false. No secret is accepted through CLI arguments or configuration files. Protective legs must fill before short legs; these controls belong to M11–M12 and must be failure-injection tested before any live implementation.

M9 paper execution remains local and cannot reach a private REST order endpoint. A limit becomes eligible only after configured simulated latency, must cross the current executable bid/ask, and never fills outside its limit. Displayed liquidity and participation limits can produce partial fills. Every persisted fill is marked `simulated=true`.

M11 implements protective-first entry and short-first exit/cleanup as a provider-neutral state boundary. A failed or partial short entry is bought back before protective inventory is sold. Reconciliation fails closed on timeouts, missing local positions, unexpected exchange exposure, or unavailable wallet state. Heartbeat failure makes the system unhealthy immediately; a recent successful acknowledgment is required for health.

M12 contains a live adapter but remains disabled in `config/default.yaml`. Startup is always disarmed. Arming requires `mode=LIVE`, `BOS_LIVE__LIVE_TRADING=true`, environment-only credentials, successful exchange-authoritative reconciliation, healthy heartbeat, no kill switch, and the exact explicit phrase `ARM LIVE TRADING` passed to the in-process guard. No dashboard or HTTP arming endpoint exists. A heartbeat, reconciliation, or kill-switch transition disarms immediately. Only bounded limit orders are exposed.
