# Architecture

## Data flow

```text
M2 Session / Opening Range
  -> M3 Trend / Structure
  -> M4 Breakout
  -> M5 Retest
  -> M6 Smart Money Context
  -> M7 Setup Score / Qualification
  -> M8 Risk Approval
  -> M9 Order Execution / Management
  -> M10 Monitoring
  -> M11 Alerts
```

M10 observes state only. M11 consumes one-bar events and emits a single prioritized alert; neither module controls a trade.

## State ownership

| Owner | Persistent state it owns |
| --- | --- |
| M2 | Session lifecycle, opening range, range statistics, session trade lock |
| M3 | Trend direction/strength/score, market structure, confirmed swings |
| M4 | Breakout state, direction, distance, score, failure counters/events |
| M5 | Retest state, level, attempt/retry state, quality, failure counters/events |
| M6 | Liquidity levels, sweep context, bounded FVG/OB arrays, premium/discount, SMC score |
| M7 | Qualified setup state, trade bias, score display state |
| M8 | Frozen initial risk context, size, targets, guard state |
| M9 | Actual position lifecycle, protective stop, partial-fill/outcome tracking |
| M10 | Tables, optional labels, plots, backgrounds |
| M11 | Alert event selection and last-alert diagnostics |

Persistent values are reassigned in main execution scope. Calculation helpers return values/tuples rather than mutating a module’s global state.

## Non-repainting policy

- Signal and lifecycle transitions use completed bars (`barstate.isconfirmed`).
- All three `request.security()` calls set `gaps = barmerge.gaps_off` and `lookahead = barmerge.lookahead_off`.
- The HTF EMA request uses the configured HTF and returns fast/slow EMA together in one call.
- Daily and weekly liquidity requests use `high[1]`, `low[1]`, and `close[1]`, so only completed periods are used.
- Market-structure and swing-trailing pivots use symmetric left/right pivot lengths. A pivot is intentionally available only after its configured right-side bars have closed.
- There is no `lookahead_on` request.

## Resource and performance boundaries

- The opening-range box, three lines, and labels are created once and reused.
- Trend and qualified-setup score labels are bounded to one reusable label per purpose/direction.
- FVG and order-block arrays have configurable caps (1–20), expire/inactivate zones, and guard loops with nonzero sizes.
- The dashboard is one fixed 2 x 96 table and updates only on the last bar.
- Webhook payload strings are constructed only when a selected alert event is dispatched.

## Risk and execution boundaries

M8 freezes the initial stop, quantity, targets, and risk context at qualification. M9 accepts only one-bar final M8 approval events, uses stable entry/exit IDs, has `pyramiding = 0`, and tracks fills from `strategy.position_size` and `strategy.closedtrades`. Partial exits use the configured target allocations; the remaining position is protected when breakeven or trailing updates occur.

The script validates positive/ordered initial stop and targets, quantity bounds/step, target allocation, and guard limits. Quantity is still feed-specific: verify `syminfo.pointvalue` and broker lot conversion outside Pine.

## Webhook schema v1

The compact, standard, and detailed forms use the same stable field names; non-applicable numeric values are serialized as JSON `null`.

| Field | Meaning |
| --- | --- |
| `event`, `action` | Event taxonomy and requested action |
| `strategy`, `version`, `schema_version` | Integration identity; schema version is `1` |
| `symbol`, `timeframe`, `timestamp` | Chart identity and confirmed bar close time |
| `direction`, `price`, `score` | Directional context and event price/score |
| `entry`, `stop`, `tp1`, `tp2`, `quantity`, `risk_pct` | Available M8/M9 execution context |
| `exit_reason`, `pnl`, `r_multiple` | Populated for completed trade outcomes where meaningful |
| `event_id` | Idempotency key: strategy id, symbol, timeframe, bar index, and event |

No webhook URL, token, or password belongs in source. A receiver must reject malformed, duplicate, mismatched-symbol, invalid-quantity, or stale events.
