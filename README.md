# XAUUSD Institutional Framework

Version 1.0.0 is a production release candidate for a Pine Script v6 XAUUSD strategy. It combines a configured session/opening-range workflow with trend, breakout, retest, Smart Money context, scoring, risk, execution, monitoring, and event-driven alerts. It is not live-broker certified and makes no performance claim.

## Philosophy

The strategy waits for an eligible session and opening range, evaluates a confirmed breakout and retest in the context of trend and liquidity, qualifies the setup, applies fixed initial-risk controls, and then manages only an actual position. The objective is deterministic, reviewable behavior rather than parameter-maximized backtest results.

## Modules

| Milestone | Responsibility |
| --- | --- |
| M1 | Core framework, shared utilities, logging, drawing base |
| M2 | Sessions, opening range, range statistics |
| M3 | EMA/HTF EMA, VWAP, ADX/DMI, confirmed market structure |
| M4 | Confirmed opening-range breakouts and failure lifecycle |
| M5 | Retest lifecycle, quality, confirmation, failure/retry controls |
| M6 | Prior-period liquidity, equal levels, sweeps, FVGs, order blocks, premium/discount |
| M7 | Directional setup scoring and qualification |
| M8 | Initial stop, sizing, targets, risk guards |
| M9 | Orders, partial exits, breakeven, trailing, outcomes |
| M10 | Dashboard and optional chart presentation |
| M11 | Confirmed-bar alerts and webhook payloads |

See [ARCHITECTURE.md](ARCHITECTURE.md) for ownership and data flow, and [TESTING.md](TESTING.md) for the required validation plan.

## Installation and use

1. In TradingView, open Pine Editor and paste the contents of `Strategy.pine`.
2. Save, then add it to an XAUUSD chart from the specific feed intended for testing.
3. Compile in Pine Editor before relying on any result. Resolve any TradingView-specific diagnostic first.
4. Begin with Bar Replay and Strategy Tester on 1m, 3m, 5m, and 15m charts.
5. Configure sessions, risk controls, commission, slippage, and symbol assumptions for the selected feed.

Important: `strategy()` uses `process_orders_on_close = true`, `calc_on_every_tick = false`, `calc_on_order_fills = false`, and `pyramiding = 0`. Commission and slippage are not invented in the source; configure realistic broker/feed assumptions in Strategy Properties before evaluating results.

## Key configuration areas

- Sessions and Opening Range: active session, timezone, OR duration, and ATR-quality bounds.
- Trend / Breakout / Retest: confirmed-bar filters and thresholds; pivot-based structure is intentionally delayed by its right-side pivot length.
- Smart Money: bounded FVG and order-block collections, completed prior day/week levels, and confirmed sweeps.
- Risk and trade management: initial stop mode, position sizing, target allocation, daily/session guards, breakeven, and trailing policy.
- Dashboard and alerts: visual diagnostics are optional; webhook dispatch is event-driven.

The Detailed dashboard includes a release configuration indicator for OR bounds, sweep penetration bounds, stop-distance bounds, quantity settings, and two-target allocation. It is diagnostic only; risk/order guards remain the enforcement mechanism.

## Alerts and webhooks

Enable the M11 inputs, then create a TradingView strategy alert using **Any alert() function call** for dynamic messages. The script emits at most one prioritized confirmed-bar event per bar. Native strategy order-fill alerts are configured separately in TradingView if required.

Webhook payloads contain no credentials. The receiving service must validate the symbol, side, quantity, idempotency key, price assumptions, and broker mapping before it submits an order. The stable v1 schema is documented in [ARCHITECTURE.md](ARCHITECTURE.md).

## XAUUSD quantity warning

`strategy` quantity and `syminfo.pointvalue` describe TradingView’s selected symbol/feed economics. They do **not** establish a universal XAUUSD lot convention. The script intentionally does not assume 100 oz per lot. Verify the broker’s contract size, minimum increment, point value, and quantity conversion independently before automation.

## Backtesting and limitations

Strategy Tester is a broker emulator. Same-bar stop/target precedence, gaps, partial fills, bar granularity, and order-fill modeling can differ from live execution. Use Bar Magnifier where available and appropriate, test multiple market regimes, and paper trade before considering a live bridge. Backtest profitability is not evidence of future performance or safe automation.

## Release status

This release candidate completed a static audit and requires two manual gates:

- Manual TradingView Pine Editor compilation and realtime alert validation are required.
- Manual TradingView Strategy Tester and Bar Replay validation are required.
