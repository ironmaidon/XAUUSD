# Live Trading Safety

M1 has no order placement implementation and therefore cannot trade. Enabling the configuration gate does not add that capability.

Future live operation requires both `BOS_LIVE__LIVE_TRADING=true` and a manual, in-memory arm action after successful heartbeat and exchange-authoritative reconciliation. Every startup resets armed state to false. No secret is accepted through CLI arguments or configuration files. Protective legs must fill before short legs; these controls belong to M11–M12 and must be failure-injection tested before any live implementation.

