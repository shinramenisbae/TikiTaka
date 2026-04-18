from __future__ import annotations

from datetime import timedelta

from tikitaka.config import Settings
from tikitaka.models import MarketMeta, SignalResult, Trade, WalletProfile

NAME = "sniper"
BASE_SCORE = 30.0
FRESH_WALLET_BONUS = 10.0


def detect_sniper(
    trade: Trade,
    market: MarketMeta,
    profile: WalletProfile | None,
    settings: Settings,
) -> SignalResult:
    if trade.notional_usdc < settings.min_trade_usdc:
        return SignalResult(name=NAME, matched=False)

    age = trade.timestamp - market.created_at
    if age > timedelta(minutes=settings.sniper_window_min) or age.total_seconds() < 0:
        return SignalResult(name=NAME, matched=False)

    bonus = 0.0
    if profile is not None and profile.tx_count < settings.fresh_wallet_max_tx:
        bonus = FRESH_WALLET_BONUS

    return SignalResult(
        name=NAME,
        matched=True,
        score=BASE_SCORE + bonus,
        detail={
            "market_age_seconds": int(age.total_seconds()),
            "notional_usdc": trade.notional_usdc,
        },
    )
