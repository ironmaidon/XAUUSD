# Strategy Specification

Strategy implementation begins after M1. The authoritative V1 rules are the master build brief: defined-risk BTC option credit structures only, no naked shorts, 4H confirmed-candle signals, and one active V1 structure. No strategy constants are implemented during transport milestones.

## M3 analytics

`RV20` uses the sample standard deviation of the latest 20 daily log returns and `sqrt(365)` annualization. ATM IV averages valid exchange call/put mark IV values; if neither is valid it returns no value rather than an estimate. IV percentile counts historical observations strictly below the current value. Expected move is `spot × ATM_IV × sqrt(DTE/365)` and is not a guaranteed boundary.

The 4H indicator snapshot contains EMA20, EMA50, Wilder ATR14, Wilder ADX14, 20-bar swing extremes, and EMA20 slope normalized by current close. Callers must pass confirmed closed candles; a minimum of 50 bars is enforced.

## M4 regime engine

Extreme conditions have priority over every tradeable classification. ADX above 35, a consistently measured absolute 24-hour move above 2.5 ATR, or a volatility-shock signal produces `EXTREME → NO_TRADE`. Clean trend rules map bullish to a bull put spread and bearish to a bear call spread. Low-ADX, compressed, flat-slope conditions map to `NEUTRAL → IRON_CONDOR`; everything else is explicitly `AMBIGUOUS → NO_TRADE`. Decisions include machine-readable reasons.
