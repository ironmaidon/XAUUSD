from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from bos.config import LiquiditySettings, StrikeSelectionSettings


class OptionType(StrEnum):
    CALL = "CALL"
    PUT = "PUT"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class OptionMarket:
    product_id: int
    symbol: str
    option_type: OptionType
    strike: float
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    delta: float
    gamma: float = 0
    theta: float = 0
    vega: float = 0
    received_at: datetime = datetime.min.replace(tzinfo=UTC)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def width_pct(self) -> float:
        return (self.ask - self.bid) / self.mid if self.mid > 0 else float("inf")


@dataclass(frozen=True)
class Leg:
    market: OptionMarket
    side: Side


@dataclass(frozen=True)
class DefinedRiskStructure:
    name: str
    legs: tuple[Leg, ...]
    gross_credit: float
    estimated_costs: float
    net_credit: float
    max_profit: float
    max_loss: float
    breakevens: tuple[float, ...]
    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float


class SelectionError(ValueError):
    pass


def validate_market(
    market: OptionMarket,
    quantity: float,
    now: datetime,
    maximum_age_seconds: float,
    maximum_width_pct: float,
    liquidity: LiquiditySettings,
    side: Side,
) -> None:
    age = (now - market.received_at).total_seconds()
    if age < 0 or age > maximum_age_seconds:
        raise SelectionError("STALE_MARKET")
    if market.bid <= 0 or market.ask <= 0 or market.bid >= market.ask:
        raise SelectionError("INVALID_MARKET")
    if market.width_pct > maximum_width_pct:
        raise SelectionError("WIDE_MARKET")
    relevant_size = market.ask_size if side is Side.BUY else market.bid_size
    required = max(
        quantity * liquidity.top_book_multiple, quantity / liquidity.max_book_participation
    )
    if relevant_size < required:
        raise SelectionError("INSUFFICIENT_TOP_BOOK")


def select_short(
    chain: list[OptionMarket],
    option_type: OptionType,
    spot: float,
    expected_move_usd: float,
    swing: float,
    atr14: float,
    settings: StrikeSelectionSettings,
) -> OptionMarket:
    candidates = [
        market
        for market in chain
        if market.option_type is option_type
        and settings.minimum_delta <= abs(market.delta) <= settings.maximum_delta
    ]
    if option_type is OptionType.PUT:
        hard = spot - settings.expected_move_distance * expected_move_usd
        preferred = swing - settings.swing_atr_buffer * atr14
        candidates = [
            market for market in candidates if market.strike <= hard and market.strike < preferred
        ]
    else:
        hard = spot + settings.expected_move_distance * expected_move_usd
        preferred = swing + settings.swing_atr_buffer * atr14
        candidates = [
            market for market in candidates if market.strike >= hard and market.strike > preferred
        ]
    if not candidates:
        raise SelectionError("NO_ACCEPTABLE_SHORT")
    return min(candidates, key=lambda market: abs(abs(market.delta) - settings.target_delta))


def select_wing(
    chain: list[OptionMarket],
    short: OptionMarket,
    expected_move_usd: float,
    settings: StrikeSelectionSettings,
) -> OptionMarket:
    candidates = []
    for market in chain:
        if market.option_type is not short.option_type:
            continue
        width = abs(short.strike - market.strike)
        outward = (
            market.strike < short.strike
            if short.option_type is OptionType.PUT
            else market.strike > short.strike
        )
        if outward and settings.minimum_wing_width <= width <= settings.maximum_wing_width:
            candidates.append(market)
    if not candidates:
        raise SelectionError("NO_PROTECTIVE_WING")
    target = min(
        max(
            settings.minimum_wing_width,
            settings.wing_expected_move_multiplier * expected_move_usd,
        ),
        settings.maximum_wing_width,
    )
    return min(candidates, key=lambda market: abs(abs(short.strike - market.strike) - target))


def build_credit_spread(
    short: OptionMarket, wing: OptionMarket, costs: float = 0
) -> DefinedRiskStructure:
    if short.option_type is not wing.option_type:
        raise SelectionError("MISMATCHED_OPTION_TYPES")
    if short.option_type is OptionType.PUT and wing.strike >= short.strike:
        raise SelectionError("PUT_WING_NOT_PROTECTIVE")
    if short.option_type is OptionType.CALL and wing.strike <= short.strike:
        raise SelectionError("CALL_WING_NOT_PROTECTIVE")
    gross_credit = short.bid - wing.ask
    net_credit = gross_credit - costs
    width = abs(short.strike - wing.strike)
    if net_credit <= 0 or net_credit >= width:
        raise SelectionError("INVALID_CREDIT")
    short_sign, wing_sign = -1.0, 1.0
    breakeven = (
        short.strike - net_credit
        if short.option_type is OptionType.PUT
        else short.strike + net_credit
    )
    return DefinedRiskStructure(
        name="BULL_PUT_SPREAD" if short.option_type is OptionType.PUT else "BEAR_CALL_SPREAD",
        legs=(Leg(wing, Side.BUY), Leg(short, Side.SELL)),
        gross_credit=gross_credit,
        estimated_costs=costs,
        net_credit=net_credit,
        max_profit=net_credit,
        max_loss=width - net_credit,
        breakevens=(breakeven,),
        net_delta=short_sign * short.delta + wing_sign * wing.delta,
        net_gamma=short_sign * short.gamma + wing_sign * wing.gamma,
        net_theta=short_sign * short.theta + wing_sign * wing.theta,
        net_vega=short_sign * short.vega + wing_sign * wing.vega,
    )


def build_iron_condor(
    short_put: OptionMarket,
    put_wing: OptionMarket,
    short_call: OptionMarket,
    call_wing: OptionMarket,
    costs: float = 0,
) -> DefinedRiskStructure:
    put_spread = build_credit_spread(short_put, put_wing)
    call_spread = build_credit_spread(short_call, call_wing)
    put_width = short_put.strike - put_wing.strike
    call_width = call_wing.strike - short_call.strike
    gross = put_spread.gross_credit + call_spread.gross_credit
    net = gross - costs
    if net <= 0 or net >= max(put_width, call_width):
        raise SelectionError("INVALID_CREDIT")
    legs = (
        Leg(put_wing, Side.BUY),
        Leg(call_wing, Side.BUY),
        Leg(short_put, Side.SELL),
        Leg(short_call, Side.SELL),
    )
    signs = (1.0, 1.0, -1.0, -1.0)
    return DefinedRiskStructure(
        name="IRON_CONDOR",
        legs=legs,
        gross_credit=gross,
        estimated_costs=costs,
        net_credit=net,
        max_profit=net,
        max_loss=max(put_width, call_width) - net,
        breakevens=(short_put.strike - net, short_call.strike + net),
        net_delta=sum(sign * leg.market.delta for sign, leg in zip(signs, legs, strict=True)),
        net_gamma=sum(sign * leg.market.gamma for sign, leg in zip(signs, legs, strict=True)),
        net_theta=sum(sign * leg.market.theta for sign, leg in zip(signs, legs, strict=True)),
        net_vega=sum(sign * leg.market.vega for sign, leg in zip(signs, legs, strict=True)),
    )
