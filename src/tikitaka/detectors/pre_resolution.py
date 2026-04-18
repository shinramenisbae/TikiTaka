from __future__ import annotations

from datetime import timedelta

from tikitaka.config import Settings
from tikitaka.models import MarketMeta, SignalResult, Trade

NAME = "pre_resolution"
BASE_SCORE = 30.0


def detect_pre_resolution(
    trade: Trade,
    market: MarketMeta,
    settings: Settings,
) -> SignalResult:
    if market.end_date is None:
        return SignalResult(name=NAME, matched=False)
    if trade.notional_usdc < settings.pre_resolution_min_usdc:
        return SignalResult(name=NAME, matched=False)

    time_to_close = market.end_date - trade.timestamp
    if time_to_close > timedelta(hours=settings.pre_resolution_window_hours):
        return SignalResult(name=NAME, matched=False)
    if time_to_close.total_seconds() < 0:
        return SignalResult(name=NAME, matched=False)

    edge = abs(trade.price - 0.5)
    if edge < settings.pre_resolution_price_edge:
        return SignalResult(name=NAME, matched=False)

    return SignalResult(
        name=NAME,
        matched=True,
        score=BASE_SCORE,
        detail={
            "hours_to_close": round(time_to_close.total_seconds() / 3600, 2),
            "price": trade.price,
            "notional_usdc": trade.notional_usdc,
        },
    )
