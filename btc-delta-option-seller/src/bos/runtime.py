from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any

from bos.config import ExchangeSettings, Settings
from bos.dashboard.models import CandidateView, DashboardSnapshot, RiskView, VolatilityView
from bos.dashboard.state import DashboardState
from bos.exchange.models import Candle, OptionQuote
from bos.exchange.rest import DeltaRestClient
from bos.exchange.services import DeltaOptionChainService, DeltaProductService, DeltaWalletService
from bos.execution.models import OrderRequest
from bos.execution.paper import PaperExecutionProvider
from bos.risk import PortfolioRisk, evaluate_portfolio, position_size
from bos.strategy.indicators import calculate_indicators
from bos.strategy.regime import RegimeInput, Structure, classify_regime
from bos.strategy.scoring import entry_score
from bos.strategy.structures import (
    DefinedRiskStructure,
    OptionMarket,
    OptionType,
    SelectionError,
    Side,
    build_credit_spread,
    build_iron_condor,
    select_short,
    select_wing,
    validate_market,
)
from bos.strategy.volatility import expected_move, realized_volatility, vrp_ratio
from bos.strategy.zero_dte import (
    StrangleSelection,
    entry_window,
    forced_exit_due,
    local_date,
    notional_capped_quantity,
    premium_stop_due,
    select_lowest_available_delta,
)


class PaperTradingRuntime:
    """Continuously evaluates Delta market data and routes eligible trades to paper execution."""

    def __init__(self, settings: Settings, exchange: ExchangeSettings, dashboard: DashboardState):
        self.settings = settings
        self.exchange = exchange
        self.dashboard = dashboard
        self.paper = PaperExecutionProvider(settings.paper)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._entered = False
        self._trade_date: date | None = None
        self._strangle: StrangleSelection | None = None
        self._entry_credit = 0.0
        self._quantity = 0.0
        self._exit_submitted = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not self.running:
            self._stop.clear()
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                await self._publish_error(error)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=15)
            except TimeoutError:
                pass

    async def tick(self) -> None:
        now = datetime.now(UTC)
        end = int(time.time())
        async with DeltaRestClient(self.exchange) as client:
            products = DeltaProductService(client)
            ticker = await products.get_ticker("BTCUSD")
            price_value = ticker.spot_price or ticker.mark_price or ticker.close
            if price_value is None:
                raise ValueError("BTCUSD_PRICE_MISSING")
            spot = float(price_value)
            candles = await client.request(
                "GET",
                "/v2/history/candles",
                list[Candle],
                params={
                    "symbol": "BTCUSD",
                    "resolution": "4h",
                    "start": end - 86400 * 40,
                    "end": end,
                },
            )
            chain = await DeltaOptionChainService(products).load()
            wallet = await DeltaWalletService(client).balances()

        markets, chain_iv, target_expiry, dte = self._markets(chain, spot, now)
        equity, available = self._account(wallet)
        snapshot = await self._evaluate_zero_dte(
            spot, candles, markets, chain_iv, target_expiry, dte, equity, available, now
        )
        await self.dashboard.publish(snapshot)

    async def _evaluate_zero_dte(
        self,
        spot: float,
        candles: list[Candle],
        markets: list[OptionMarket],
        chain_iv: float | None,
        target_expiry: datetime | None,
        dte: float,
        equity: float,
        available: float,
        now: datetime,
    ) -> DashboardSnapshot:
        _, snapshot = await self.dashboard.get()
        today = local_date(now)
        if self._trade_date != today:
            self._trade_date = today
            self._strangle = None
            self._entry_credit = 0
            self._quantity = 0
            self._exit_submitted = False
        for market in markets:
            self.paper.on_quote(market, now)

        reasons: list[str] = []
        selection: StrangleSelection | None = None
        try:
            selection = select_lowest_available_delta(markets)
        except ValueError as error:
            reasons.append(str(error))

        entry_due = entry_window(now, self._strangle is not None)
        if entry_due and selection:
            quantity = notional_capped_quantity(equity, spot)
            if quantity > 0 and selection.entry_credit > 0:
                self._strangle = selection
                self._entry_credit = selection.entry_credit
                self._quantity = quantity
                for index, market in enumerate((selection.call, selection.put)):
                    self.paper.submit(
                        OrderRequest(
                            f"0dte-{today:%Y%m%d}-entry-{index}",
                            market.product_id,
                            market.symbol,
                            Side.SELL,
                            quantity,
                            market.bid,
                        ),
                        now,
                    )
                reasons.append("PAPER_STRANGLE_ENTRY_SUBMITTED")
            else:
                reasons.append("NOTIONAL_OR_PREMIUM_GATE")
        elif self._strangle and not self._exit_submitted:
            by_symbol = {market.symbol: market for market in markets}
            call = by_symbol.get(self._strangle.call.symbol)
            put = by_symbol.get(self._strangle.put.symbol)
            stop = bool(call and put and premium_stop_due(self._entry_credit, call.ask, put.ask))
            timed = forced_exit_due(now)
            if stop or timed:
                reason = "PREMIUM_STOP" if stop else "TIME_EXIT_1630_IST"
                if call and put:
                    for index, market in enumerate((call, put)):
                        self.paper.submit(
                            OrderRequest(
                                f"0dte-{today:%Y%m%d}-exit-{index}",
                                market.product_id,
                                market.symbol,
                                Side.BUY,
                                self._quantity,
                                market.ask,
                                reduce_only=True,
                            ),
                            now,
                        )
                    self._exit_submitted = True
                    reasons.append(reason)
                else:
                    reasons.append("EXIT_QUOTE_MISSING")
            else:
                reasons.append("MONITORING_OPEN_STRANGLE")
        else:
            reasons.append("WAITING_FOR_0800_IST" if not self._strangle else "EXIT_SUBMITTED")

        closes = [float(c.close) for c in candles]
        rv = realized_volatility(closes, self.settings.volatility.rv_window, 6 * 365)
        move = expected_move(spot, chain_iv, dte) if chain_iv else None
        shown = self._strangle or selection
        score_components = {
            "call_delta": abs(shown.call.delta) * 100 if shown else 0,
            "put_delta": abs(shown.put.delta) * 100 if shown else 0,
            "gross_notional_cap_x": 10,
        }
        snapshot.status.btc_price = spot
        snapshot.status.connection = "CONNECTED"
        snapshot.status.paper_trading_active = True
        snapshot.status.regime = "0DTE_STRANGLE"
        snapshot.status.entry_score = 0
        snapshot.status.target_expiry = target_expiry
        snapshot.status.dte = dte
        snapshot.status.heartbeat_healthy = True
        snapshot.status.volatility = VolatilityView(
            atm_iv=chain_iv,
            rv20=rv,
            vrp=vrp_ratio(chain_iv, rv) if chain_iv else None,
            expected_move_usd=move.usd if move else None,
        )
        snapshot.candles = [
            {
                "time": c.time,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
            }
            for c in candles[-120:]
        ]
        snapshot.option_chain = [self._market_view(market) for market in markets]
        snapshot.candidate = CandidateView(
            structure="SHORT_STRANGLE_0DTE" if shown else None,
            strikes=[shown.put.strike, shown.call.strike] if shown else [],
            deltas=[shown.put.delta, shown.call.delta] if shown else [],
            net_credit=self._entry_credit or (shown.entry_credit if shown else None),
            quantity=self._quantity or None,
            eligible=entry_due and shown is not None,
            reasons=reasons,
            score_components=score_components,
        )
        snapshot.risk = RiskView(
            account_equity_inr=equity,
            available_funds_inr=available,
            margin_usage_pct=(
                min(100, 2 * spot * 0.001 * self._quantity / equity * 100)
                if equity and self._quantity
                else 0
            ),
            kill_switches=[],
        )
        snapshot.orders = [self._order_view(order) for order in self.paper.orders.values()]
        snapshot.fills = [asdict(fill) for fill in self.paper.fills]
        snapshot.positions = self._positions()
        snapshot.logs = [
            {
                "time": now.isoformat(),
                "level": "INFO",
                "event": "ZERO_DTE_EVALUATION",
                "reason": " · ".join(reasons),
            }
        ]
        return snapshot

    async def _evaluate(
        self,
        spot: float,
        candles: list[Candle],
        markets: list[OptionMarket],
        chain_iv: float | None,
        target_expiry: datetime | None,
        dte: float,
        equity: float,
        available: float,
        now: datetime,
    ) -> DashboardSnapshot:
        _, previous = await self.dashboard.get()
        closes = [float(c.close) for c in candles]
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        indicators = calculate_indicators(highs, lows, closes)
        rv = realized_volatility(closes, self.settings.volatility.rv_window)
        move = expected_move(spot, chain_iv, dte) if chain_iv else None
        regime = classify_regime(
            RegimeInput(
                close=closes[-1],
                ema20=indicators.ema20,
                ema50=indicators.ema50,
                normalized_ema20_slope=indicators.normalized_ema20_slope,
                atr14=indicators.atr14,
                adx14=indicators.adx14,
                absolute_24h_move=abs(closes[-1] - closes[-7]),
            ),
            self.settings.regime,
        )
        risk_state = PortfolioRisk(equity, 0, 0, 0, 0, 0, int(self._entered))
        risk = evaluate_portfolio(risk_state, self.settings.risk)
        structure: DefinedRiskStructure | None = None
        reasons = list(regime.reasons)
        if move and regime.structure is not Structure.NO_TRADE:
            try:
                structure = self._structure(regime.structure, markets, spot, move.usd, indicators)
                for leg in structure.legs:
                    validate_market(
                        leg.market,
                        0.001,
                        now,
                        self.settings.market_data.max_quote_age_seconds,
                        self.settings.liquidity.short_max_width_pct
                        if leg.side is Side.SELL
                        else self.settings.liquidity.wing_max_width_pct,
                        self.settings.liquidity,
                        leg.side,
                    )
            except SelectionError as error:
                reasons.append(str(error))
        else:
            reasons.append("IV_OR_REGIME_GATE")
        components = {
            "vrp": min(vrp_ratio(chain_iv, rv) / self.settings.volatility.vrp_minimum, 1)
            if chain_iv
            else 0,
            "iv_percentile": 0.5 if chain_iv else 0,
            "regime_quality": 1 if regime.structure is not Structure.NO_TRADE else 0,
            "liquidity": 1 if markets else 0,
            "credit_efficiency": 1 if structure and structure.net_credit > 0 else 0,
            "volatility_stability": 1,
            "skew_alignment": 0.5,
        }
        scored = entry_score(components, bool(structure and risk.allowed))
        quantity = 0.0
        if structure and equity > 0:
            quantity = position_size(
                equity, structure.max_loss, 0.001, 0.001, 1, self.settings.risk
            )
        eligible = scored.eligible and quantity > 0 and not self._entered
        if eligible and structure:
            self._submit(structure, quantity, now)
            self._entered = True
            reasons.append("PAPER_ENTRY_SUBMITTED")
        for market in markets:
            self.paper.on_quote(market, now)
        candidate = CandidateView(
            structure=structure.name if structure else None,
            strikes=[leg.market.strike for leg in structure.legs] if structure else [],
            deltas=[leg.market.delta for leg in structure.legs] if structure else [],
            net_credit=structure.net_credit if structure else None,
            wing_width=(structure.max_loss + structure.net_credit) if structure else None,
            credit_ratio=(
                structure.net_credit / (structure.max_loss + structure.net_credit)
                if structure
                else None
            ),
            max_loss=structure.max_loss if structure else None,
            risk_pct=(structure.max_loss * quantity / equity * 100)
            if structure and equity
            else None,
            quantity=quantity or None,
            entry_score=scored.total,
            eligible=eligible,
            reasons=reasons,
            score_components=scored.components,
        )
        previous.status.btc_price = spot
        previous.status.connection = "CONNECTED"
        previous.status.paper_trading_active = True
        previous.status.regime = regime.regime.value
        previous.status.entry_score = scored.total
        previous.status.dte = dte
        previous.status.target_expiry = target_expiry
        previous.status.heartbeat_healthy = True
        previous.status.volatility = VolatilityView(
            atm_iv=chain_iv,
            rv20=rv,
            vrp=vrp_ratio(chain_iv, rv) if chain_iv else None,
            expected_move_usd=move.usd if move else None,
        )
        previous.candles = [
            {
                "time": c.time,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
            }
            for c in candles[-120:]
        ]
        previous.option_chain = [self._market_view(m) for m in markets]
        previous.candidate = candidate
        previous.risk = RiskView(
            account_equity_inr=equity,
            available_funds_inr=available,
            open_defined_risk_pct=0,
            kill_switches=list(risk.reasons),
        )
        previous.orders = [self._order_view(order) for order in self.paper.orders.values()]
        previous.fills = [asdict(fill) for fill in self.paper.fills]
        previous.positions = self._positions()
        previous.backtests = [
            {
                "status": "AVAILABLE_ON_DEMAND",
                "engine": "event-driven",
                "note": "Research backtests are isolated from the running paper session",
            }
        ]
        previous.logs = [
            {
                "time": now.isoformat(),
                "level": "INFO",
                "event": "PAPER_EVALUATION",
                "reason": " · ".join(reasons),
            }
        ]
        return previous

    def _markets(
        self, quotes: list[OptionQuote], spot: float, now: datetime
    ) -> tuple[list[OptionMarket], float | None, datetime | None, float]:
        valid_expiries = sorted(
            {
                quote.product.settlement_time
                for quote in quotes
                if quote.product.settlement_time
                and quote.product.settlement_time > now
                and local_date(quote.product.settlement_time) == local_date(now)
            },
            key=lambda value: value,
        )
        target_expiry = valid_expiries[0] if valid_expiries else None
        if target_expiry is None:
            return [], None, None, 0.01
        output = []
        iv_candidates: list[tuple[float, float]] = []
        for quote in quotes:
            if target_expiry and quote.product.settlement_time != target_expiry:
                continue
            raw = quote.ticker.model_dump()
            option = OptionType.CALL if "call" in quote.product.contract_type else OptionType.PUT
            if (
                quote.product.strike_price is None
                or quote.ticker.best_bid is None
                or quote.ticker.best_ask is None
                or quote.ticker.greeks is None
                or quote.ticker.greeks.delta is None
            ):
                continue
            output.append(
                OptionMarket(
                    quote.product.id,
                    quote.product.symbol,
                    option,
                    float(quote.product.strike_price),
                    float(quote.ticker.best_bid),
                    float(quote.ticker.best_ask),
                    float(raw.get("bid_size") or 100),
                    float(raw.get("ask_size") or 100),
                    float(quote.ticker.greeks.delta),
                    float(quote.ticker.greeks.gamma or 0),
                    float(quote.ticker.greeks.theta or 0),
                    float(quote.ticker.greeks.vega or 0),
                    now,
                )
            )
            if quote.ticker.mark_vol and quote.ticker.mark_vol > 0:
                value = float(quote.ticker.mark_vol)
                iv_candidates.append(
                    (
                        abs(float(quote.product.strike_price) - spot),
                        value / 100 if value > 3 else value,
                    )
                )
        iv = min(iv_candidates, default=(0, 0), key=lambda item: item[0])[1] or None
        dte = max((target_expiry - now).total_seconds() / 86400, 0.01) if target_expiry else 14.0
        return output, iv, target_expiry, dte

    def _structure(
        self,
        kind: Structure,
        markets: list[OptionMarket],
        spot: float,
        move: float,
        indicators: Any,
    ) -> DefinedRiskStructure:
        def spread(option_type: OptionType, swing: float) -> DefinedRiskStructure:
            short = select_short(
                markets,
                option_type,
                spot,
                move,
                swing,
                indicators.atr14,
                self.settings.strike_selection,
            )
            wing = select_wing(markets, short, move, self.settings.strike_selection)
            return build_credit_spread(short, wing)

        if kind is Structure.BULL_PUT_SPREAD:
            return spread(OptionType.PUT, indicators.swing_low20)
        if kind is Structure.BEAR_CALL_SPREAD:
            return spread(OptionType.CALL, indicators.swing_high20)
        put = spread(OptionType.PUT, indicators.swing_low20)
        call = spread(OptionType.CALL, indicators.swing_high20)
        return build_iron_condor(
            put.legs[1].market, put.legs[0].market, call.legs[1].market, call.legs[0].market
        )

    def _submit(self, structure: DefinedRiskStructure, quantity: float, now: datetime) -> None:
        for index, leg in enumerate(structure.legs):
            limit = leg.market.ask if leg.side is Side.BUY else leg.market.bid
            self.paper.submit(
                OrderRequest(
                    f"paper-{int(now.timestamp())}-{index}",
                    leg.market.product_id,
                    leg.market.symbol,
                    leg.side,
                    quantity,
                    limit,
                ),
                now,
            )

    @staticmethod
    def _account(wallet: list[dict[str, object]]) -> tuple[float, float]:
        for row in wallet:
            if str(row.get("asset_symbol", "")).upper() in {"INR", "USD", "USDT"}:
                equity = float(str(row.get("balance") or row.get("total_balance") or 0))
                available = float(
                    str(row.get("available_balance") or row.get("available_funds") or equity)
                )
                return equity, available
        return 0, 0

    @staticmethod
    def _market_view(market: OptionMarket) -> dict[str, object]:
        return {
            "symbol": market.symbol,
            "type": market.option_type.value,
            "strike": market.strike,
            "bid": market.bid,
            "ask": market.ask,
            "delta": market.delta,
            "width_pct": round(market.width_pct * 100, 2),
        }

    @staticmethod
    def _order_view(order: Any) -> dict[str, object]:
        return {
            "order_id": order.order_id,
            "symbol": order.request.symbol,
            "side": order.request.side.value,
            "quantity": order.request.quantity,
            "limit_price": order.request.limit_price,
            "state": order.state.value,
            "filled_quantity": order.filled_quantity,
        }

    def _positions(self) -> list[dict[str, object]]:
        positions: dict[str, dict[str, object]] = {}
        for fill in self.paper.fills:
            current = positions.setdefault(
                fill.symbol,
                {
                    "symbol": fill.symbol,
                    "product_id": fill.product_id,
                    "net_quantity": 0.0,
                    "simulated": True,
                },
            )
            signed = fill.quantity if fill.side is Side.BUY else -fill.quantity
            current["net_quantity"] = float(str(current["net_quantity"])) + signed
        return list(positions.values())

    async def _publish_error(self, error: Exception) -> None:
        _, snapshot = await self.dashboard.get()
        snapshot.status.connection = "DEGRADED"
        snapshot.status.heartbeat_healthy = False
        snapshot.candidate.reasons = [f"RUNTIME_ERROR:{type(error).__name__}"]
        snapshot.logs = [
            {
                "time": datetime.now(UTC).isoformat(),
                "level": "ERROR",
                "event": type(error).__name__,
                "message": str(error)[:200],
            }
        ]
        await self.dashboard.publish(snapshot)
