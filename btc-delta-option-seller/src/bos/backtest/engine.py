from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from bos.config import BacktestSettings, RiskSettings
from bos.data.quality import DataQuality
from bos.risk import PortfolioRisk, evaluate_portfolio, maximum_loss_per_contract, position_size
from bos.strategy.structures import DefinedRiskStructure, OptionMarket, Side


class ExitReason(StrEnum):
    PROFIT_TARGET = "PROFIT_TARGET"
    PREMIUM_STOP = "PREMIUM_STOP"
    DELTA_STOP = "DELTA_STOP"
    EMERGENCY_DELTA = "EMERGENCY_DELTA"
    TIME_EXIT = "TIME_EXIT"
    END_OF_DATA = "END_OF_DATA"
    MISSING_QUOTE = "MISSING_QUOTE"


@dataclass(frozen=True)
class MarketFrame:
    timestamp: datetime
    quotes: dict[str, OptionMarket]
    quality: DataQuality = DataQuality.EXACT


@dataclass(frozen=True)
class EntryIntent:
    structure: DefinedRiskStructure
    expiry: datetime
    contract_size: float
    settlement_conversion: float = 1.0
    minimum_quantity: float = 1.0
    quantity_step: float = 1.0
    liquidity_maximum: float = float("inf")


@dataclass(frozen=True)
class BacktestTrade:
    structure: str
    entry_time: datetime
    exit_time: datetime
    expiry: datetime
    quantity: float
    entry_credit: float
    exit_debit: float
    fees: float
    net_pnl: float
    exit_reason: ExitReason
    max_loss: float
    quality: DataQuality


@dataclass(frozen=True)
class EquityPoint:
    timestamp: datetime
    equity: float


@dataclass(frozen=True)
class BacktestResult:
    initial_equity: float
    ending_equity: float
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    rejected_entries: tuple[str, ...]
    quality_percentages: dict[DataQuality, float]
    fee_configuration: dict[str, float | bool]


@dataclass
class _OpenPosition:
    intent: EntryIntent
    entry_time: datetime
    quantity: float
    entry_credit_per_contract: float
    entry_fees: float
    quality: DataQuality


StrategyCallback = Callable[[MarketFrame, Sequence[MarketFrame]], EntryIntent | None]


class BacktestEngine:
    def __init__(self, settings: BacktestSettings, risk: RiskSettings) -> None:
        self.settings = settings
        self.risk = risk

    def run(self, frames: Iterable[MarketFrame], strategy: StrategyCallback) -> BacktestResult:
        ordered = list(frames)
        if any(
            right.timestamp <= left.timestamp
            for left, right in zip(ordered, ordered[1:], strict=False)
        ):
            raise ValueError("market frames must be strictly increasing and unique")
        equity = self.settings.initial_equity
        peak = equity
        open_position: _OpenPosition | None = None
        trades: list[BacktestTrade] = []
        history: list[MarketFrame] = []
        equity_curve: list[EquityPoint] = []
        rejected: list[str] = []
        quality_counts: Counter[DataQuality] = Counter()
        daily_pnl: dict[object, float] = {}
        weekly_pnl: dict[object, float] = {}
        consecutive_stops = 0
        kill_switch = False

        for frame in ordered:
            quality_counts[frame.quality] += 1
            history.append(frame)
            if open_position is not None:
                reason = self._exit_reason(open_position, frame)
                if reason is not None:
                    trade = self._close(open_position, frame, reason)
                    trades.append(trade)
                    equity += trade.net_pnl
                    day_key = frame.timestamp.date()
                    week_key = frame.timestamp.isocalendar()[:2]
                    daily_pnl[day_key] = daily_pnl.get(day_key, 0.0) + trade.net_pnl
                    weekly_pnl[week_key] = weekly_pnl.get(week_key, 0.0) + trade.net_pnl
                    if reason in {
                        ExitReason.PREMIUM_STOP,
                        ExitReason.DELTA_STOP,
                        ExitReason.EMERGENCY_DELTA,
                    }:
                        consecutive_stops += 1
                    elif trade.net_pnl > 0:
                        consecutive_stops = 0
                    peak = max(peak, equity)
                    equity_curve.append(EquityPoint(frame.timestamp, equity))
                    open_position = None
                continue

            drawdown = (peak - equity) / peak if peak else 1.0
            risk_decision = evaluate_portfolio(
                PortfolioRisk(
                    equity=equity,
                    open_defined_risk=0,
                    daily_realized_pnl=daily_pnl.get(frame.timestamp.date(), 0.0),
                    weekly_realized_pnl=weekly_pnl.get(frame.timestamp.isocalendar()[:2], 0.0),
                    drawdown=drawdown,
                    consecutive_full_stops=consecutive_stops,
                    open_structures=0,
                    kill_switch_latched=kill_switch,
                ),
                self.risk,
            )
            kill_switch = risk_decision.kill_switch
            if not risk_decision.allowed:
                rejected.extend(risk_decision.reasons)
                continue
            intent = strategy(frame, tuple(history))
            if intent is None:
                continue
            opened, failure = self._open(intent, frame, equity)
            if failure:
                rejected.append(failure)
            else:
                open_position = opened

        if open_position is not None and ordered:
            trade = self._close(open_position, ordered[-1], ExitReason.END_OF_DATA)
            trades.append(trade)
            equity += trade.net_pnl
            equity_curve.append(EquityPoint(ordered[-1].timestamp, equity))

        total = sum(quality_counts.values())
        percentages = {
            quality: (100.0 * quality_counts[quality] / total if total else 0.0)
            for quality in DataQuality
        }
        fee_config = {
            "slippage_bps": self.settings.slippage_bps,
            "option_fee_rate": self.settings.option_fee_rate,
            "gst_rate": self.settings.gst_rate,
            "settlement_fee_rate": self.settings.settlement_fee_rate,
            "partial_fill_ratio": self.settings.partial_fill_ratio,
        }
        return BacktestResult(
            initial_equity=self.settings.initial_equity,
            ending_equity=equity,
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            rejected_entries=tuple(rejected),
            quality_percentages=percentages,
            fee_configuration=fee_config,
        )

    def _open(
        self, intent: EntryIntent, frame: MarketFrame, equity: float
    ) -> tuple[_OpenPosition | None, str | None]:
        quotes = self._quotes(intent.structure, frame)
        if quotes is None:
            return None, "MISSING_ENTRY_QUOTE"
        maximum_quantity = (
            min(
                quote.ask_size if leg.side is Side.BUY else quote.bid_size
                for leg, quote in zip(intent.structure.legs, quotes, strict=True)
            )
            * self.settings.partial_fill_ratio
        )
        maximum_quantity = min(maximum_quantity, intent.liquidity_maximum)
        loss = maximum_loss_per_contract(
            intent.structure.max_loss, intent.contract_size, intent.settlement_conversion
        )
        quantity = position_size(
            equity,
            loss,
            intent.minimum_quantity,
            intent.quantity_step,
            maximum_quantity,
            self.risk,
        )
        if quantity <= 0:
            return None, "QUANTITY_BELOW_MINIMUM"
        gross_credit = self._entry_credit(intent.structure, quotes)
        if gross_credit <= 0:
            return None, "NON_POSITIVE_EXECUTABLE_CREDIT"
        notional = self._notional(quotes, quantity, intent.contract_size)
        fees = self._fees(notional)
        net_credit_total = (
            gross_credit * quantity * intent.contract_size * intent.settlement_conversion - fees
        )
        if net_credit_total <= 0:
            return None, "COSTS_EXCEED_CREDIT"
        credit_per_contract = net_credit_total / quantity
        return (
            _OpenPosition(
                intent=intent,
                entry_time=frame.timestamp,
                quantity=quantity,
                entry_credit_per_contract=credit_per_contract,
                entry_fees=fees,
                quality=frame.quality,
            ),
            None,
        )

    def _exit_reason(self, position: _OpenPosition, frame: MarketFrame) -> ExitReason | None:
        quotes = self._quotes(position.intent.structure, frame)
        if quotes is None:
            return ExitReason.MISSING_QUOTE
        short_deltas = [
            abs(quote.delta)
            for leg, quote in zip(position.intent.structure.legs, quotes, strict=True)
            if leg.side is Side.SELL
        ]
        largest_delta = max(short_deltas, default=0.0)
        if largest_delta >= self.settings.delta_emergency_exit:
            return ExitReason.EMERGENCY_DELTA
        if largest_delta >= self.settings.delta_mandatory_exit:
            return ExitReason.DELTA_STOP
        if frame.timestamp >= position.intent.expiry - timedelta(
            hours=self.settings.time_exit_hours
        ):
            return ExitReason.TIME_EXIT
        debit = self._exit_debit(position.intent.structure, quotes)
        entry = position.entry_credit_per_contract / (
            position.intent.contract_size * position.intent.settlement_conversion
        )
        if debit >= entry * self.settings.premium_stop_multiple:
            return ExitReason.PREMIUM_STOP
        if debit <= entry * (1.0 - self.settings.profit_capture):
            return ExitReason.PROFIT_TARGET
        return None

    def _close(
        self, position: _OpenPosition, frame: MarketFrame, reason: ExitReason
    ) -> BacktestTrade:
        quotes = self._quotes(position.intent.structure, frame)
        if quotes is None:
            return self._conservative_missing_quote_close(position, frame, reason)
        debit = self._exit_debit(position.intent.structure, quotes)
        notional = self._notional(quotes, position.quantity, position.intent.contract_size)
        exit_fees = self._fees(notional)
        conversion = position.intent.settlement_conversion
        exit_total = debit * position.quantity * position.intent.contract_size * conversion
        entry_total = position.entry_credit_per_contract * position.quantity
        pnl = entry_total - exit_total - exit_fees
        quality = (
            position.quality if position.quality is frame.quality else DataQuality.RECONSTRUCTED
        )
        return BacktestTrade(
            structure=position.intent.structure.name,
            entry_time=position.entry_time,
            exit_time=frame.timestamp,
            expiry=position.intent.expiry,
            quantity=position.quantity,
            entry_credit=entry_total,
            exit_debit=exit_total,
            fees=position.entry_fees + exit_fees,
            net_pnl=pnl,
            exit_reason=reason,
            max_loss=position.intent.structure.max_loss
            * position.quantity
            * position.intent.contract_size
            * conversion,
            quality=quality,
        )

    def _conservative_missing_quote_close(
        self, position: _OpenPosition, frame: MarketFrame, reason: ExitReason
    ) -> BacktestTrade:
        conversion = position.intent.settlement_conversion
        maximum_loss = (
            position.intent.structure.max_loss
            * position.quantity
            * position.intent.contract_size
            * conversion
        )
        entry_total = position.entry_credit_per_contract * position.quantity
        return BacktestTrade(
            structure=position.intent.structure.name,
            entry_time=position.entry_time,
            exit_time=frame.timestamp,
            expiry=position.intent.expiry,
            quantity=position.quantity,
            entry_credit=entry_total,
            exit_debit=entry_total + maximum_loss,
            fees=position.entry_fees,
            net_pnl=-maximum_loss,
            exit_reason=reason,
            max_loss=maximum_loss,
            quality=DataQuality.ESTIMATED,
        )

    def _quotes(
        self, structure: DefinedRiskStructure, frame: MarketFrame
    ) -> tuple[OptionMarket, ...] | None:
        try:
            return tuple(frame.quotes[leg.market.symbol] for leg in structure.legs)
        except KeyError:
            return None

    def _entry_credit(
        self, structure: DefinedRiskStructure, quotes: Sequence[OptionMarket]
    ) -> float:
        slip = self.settings.slippage_bps / 10_000
        return sum(
            quote.bid * (1 - slip) if leg.side is Side.SELL else -quote.ask * (1 + slip)
            for leg, quote in zip(structure.legs, quotes, strict=True)
        )

    def _exit_debit(self, structure: DefinedRiskStructure, quotes: Sequence[OptionMarket]) -> float:
        slip = self.settings.slippage_bps / 10_000
        return sum(
            quote.ask * (1 + slip) if leg.side is Side.SELL else -quote.bid * (1 - slip)
            for leg, quote in zip(structure.legs, quotes, strict=True)
        )

    @staticmethod
    def _notional(quotes: Sequence[OptionMarket], quantity: float, contract_size: float) -> float:
        return sum(quote.mid for quote in quotes) * quantity * contract_size

    def _fees(self, notional: float) -> float:
        trading_fee = notional * self.settings.option_fee_rate
        return trading_fee * (1 + self.settings.gst_rate) + (
            notional * self.settings.settlement_fee_rate
        )

    def configuration_snapshot(self) -> dict[str, object]:
        return {
            "backtest": self.settings.model_dump(mode="json"),
            "risk": self.risk.model_dump(mode="json"),
        }
