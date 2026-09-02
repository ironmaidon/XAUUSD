# Backtesting

Historical acquisition begins at M2 and the event-driven backtester at M7. Future results must identify `EXACT`, `RECONSTRUCTED`, and `ESTIMATED` observations, avoid lookahead, and preserve the exact fee/slippage configuration.

The M2 downloader chunks `/v2/history/candles` requests at the documented 2,000-candle limit, deduplicates timestamps, and stores both SQL and Zstandard-compressed Parquet. `MARK:<symbol>` is supported without fabricating unavailable bid/ask or Greeks. Expired BTC options are discovered with cursor pagination and `states=expired,settled`.

## M7 event-driven engine

Market frames must be strictly timestamp-increasing and unique. On each frame, the strategy callback receives only the current frame and the history available through that timestamp. This lets backtests call the same production indicator, volatility, regime, selection, scoring, and risk functions without giving them future observations.

Entries and exits are valued from executable top-of-book prices plus configured basis-point slippage. Multi-leg quantity is capped by the least-liquid leg and one common fill quantity, so a simulated partial fill cannot create naked exposure. Position size uses the production maximum-loss risk function. Entry/exit fees, GST, settlement-fee configuration, and the partial-fill assumption are copied into each result for reproducibility.

Exit priority is emergency delta, mandatory delta, time exit, premium stop, then profit target. Time exits use the actual expiry timestamp. Portfolio evaluation applies daily and weekly realized-loss limits, maximum drawdown, consecutive-stop latching, and the single-structure constraint. A missing exit quote is not replaced with an entry mark: the result is labeled `ESTIMATED` and conservatively charged the complete defined maximum loss.

Every result reports the percentage of input frames in each data-quality class. A trade spanning unlike quality classes is labeled `RECONSTRUCTED`.

## M8 walk-forward and Monte Carlo

Walk-forward folds contain separate rolling training, validation, and out-of-sample slices. Candidate parameters are ranked using the training slice only. The selected parameters are then evaluated—without reselection—on validation and out-of-sample observations. Reports include every fold's selected parameters and scores, mean validation/OOS scores, and the fraction of positive OOS folds. The splitter refuses incomplete folds and never optimizes over the complete dataset.

Parameter-stability analysis works over arbitrary grids, including short delta, VRP, IV percentile, DTE, expected-move multiplier, wing width, profit target, delta stop, and premium stop. Each point is compared with immediately adjacent values along one dimension at a time. A profitable point whose available neighbors all lose is explicitly flagged as isolated and unstable.

Monte Carlo bootstraps the historical trade-PnL distribution with replacement using a local seeded random generator. It reports the median equity path, fifth-percentile ending equity, median ending equity, 95th-percentile maximum drawdown, probability of breaching the configured drawdown, and median/95th/max consecutive-loss streaks. These are distributional research estimates, not forecasts or profitability promises.
