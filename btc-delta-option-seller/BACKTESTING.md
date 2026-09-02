# Backtesting

Historical acquisition begins at M2 and the event-driven backtester at M7. Future results must identify `EXACT`, `RECONSTRUCTED`, and `ESTIMATED` observations, avoid lookahead, and preserve the exact fee/slippage configuration.

The M2 downloader chunks `/v2/history/candles` requests at the documented 2,000-candle limit, deduplicates timestamps, and stores both SQL and Zstandard-compressed Parquet. `MARK:<symbol>` is supported without fabricating unavailable bid/ask or Greeks. Expired BTC options are discovered with cursor pagination and `states=expired,settled`.
