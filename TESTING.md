# Manual Validation and Optimization

## Release gates

1. Compile `Strategy.pine` in TradingView Pine Editor on the intended XAUUSD feed.
2. Verify the active symbol, `syminfo.pointvalue`, quantity increment, commission, slippage, timezone, and session inputs.
3. Run Bar Replay and Strategy Tester tests before paper trading.
4. Test the webhook receiver with harmless endpoints first; ensure it deduplicates `event_id`.
5. Paper trade the full flow before connecting any execution bridge.

## Session and visual matrix

For Asia, London, New York, and Custom sessions, verify session start/end, OR build/completion, ATR-quality accept/reject, breakout, retest, trade lifecycle, reset, range drawings, dashboard detail modes, and disabled visuals. Repeat on 1m, 3m, 5m, and 15m XAUUSD charts.

## Market-regime matrix

Review trending, ranging, high-volatility, low-volatility, news-spike, fast gap-like bar, and thin-session samples. Confirm that pivots appear only after right-side confirmation, HTF context does not change historical decisions, and wick-only breakouts/retests are treated according to their configured completed-bar rules.

## Strategy Tester order matrix

Test long/short entry; initial stop; TP1 only; TP2 only; TP1 then TP2; TP1 then breakeven; TP1 then trail; stop before TP1; same-bar TP1+TP2; gap through stop; gap through target; stop-only; and an opposite signal while a trade is active. Check that exit IDs, allocation, residual stop coverage, outcome totals, and risk guard counts are coherent.

## Trailing and risk matrix

For ATR, Chandelier, SuperTrend, and Swing modes, test Immediate, After TP1, and R-Multiple activation. Verify the active stop never loosens and remains on the valid side of price/remaining target.

For Risk Percent, Fixed Cash Risk, and Fixed Quantity test tight/wide stops, invalid point value, bad quantity step, minimum/maximum quantity, bad TP allocation, daily/session budget blocks, trade-count blocks, and consecutive-loss blocks. Invalid configurations should be rejected or flagged; never assume an arbitrary broker lot size.

## Alert matrix

Enable one alert class at a time, then test breakout, retest, setup, risk approval, entry, TP1, TP2, breakeven, trail, exit, risk block, liquidity sweep, and FVG creation. Test a multi-event bar and verify one priority-selected dynamic `alert()` message per confirmed bar. Parse Compact, Standard, and Detailed webhook JSON and confirm `event_id` deduplication.

## Strategy Tester caveats

TradingView’s broker emulator may model same-bar fills, partial fills, gap fills, stop/target precedence, and intrabar paths differently from a broker. Use Bar Magnifier where available and appropriate; do not infer live fill quality solely from a backtest.

## Optimization framework

Do not optimize dozens of settings at once or tune only maximum net profit. Start with the following order while keeping Smart Money weights fixed initially:

1. Session and opening-range duration.
2. Range-quality thresholds.
3. Breakout filters.
4. Retest score threshold.
5. Trade qualification threshold.
6. Stop-distance ATR limits.
7. TP R multiples.
8. Trailing mode.

Evaluate Profit Factor, Max Drawdown, Average Trade, Win Rate, Expectancy, trade count, and stability across periods. Use a rolling walk-forward example of 6–12 months training followed by 3 months validation. Neighborhood-test promising parameters (for example, 65/70/75) and prefer stable regions over a single best setting. Validate across multiple years and market regimes.
