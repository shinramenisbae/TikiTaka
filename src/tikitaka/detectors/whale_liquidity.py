from __future__ import annotations

from tikitaka.config import Settings
from tikitaka.models import OrderBookSnapshot, SignalResult, Trade

NAME = "whale_liquidity"
BASE_SCORE = 20.0
BOTH_BONUS = 20.0


def detect_whale_liquidity(
    trade: Trade,
    book: OrderBookSnapshot | None,
    settings: Settings,
) -> SignalResult:
    whale = trade.notional_usdc >= settings.whale_notional_usdc

    # Liquidity-impact: trade notional as fraction of same-side visible depth.
    # Buys consume the ask side (counterparty liquidity). Sells consume the bid side.
    liquidity = False
    impact_pct = 0.0
    if book is not None:
        depth = book.ask_depth_usdc if trade.side == "BUY" else book.bid_depth_usdc
        if depth > 0:
            impact_pct = trade.notional_usdc / depth
            liquidity = impact_pct >= settings.liquidity_impact_pct

    if not (whale or liquidity):
        return SignalResult(name=NAME, matched=False)

    score = BASE_SCORE + (BOTH_BONUS if whale and liquidity else 0.0)
    return SignalResult(
        name=NAME,
        matched=True,
        score=score,
        detail={
            "notional_usdc": trade.notional_usdc,
            "impact_pct": round(impact_pct, 4),
            "whale": whale,
            "liquidity": liquidity,
        },
    )
