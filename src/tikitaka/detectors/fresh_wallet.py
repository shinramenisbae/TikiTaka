from __future__ import annotations

from tikitaka.config import Settings
from tikitaka.models import SignalResult, Trade, WalletProfile

NAME = "fresh_wallet"
BASE_SCORE = 25.0
SIZE_BUCKET_USDC = 5000.0
SIZE_BUCKET_BONUS = 5.0
MAX_SCORE = 40.0


def detect_fresh_wallet(
    trade: Trade,
    profile: WalletProfile,
    settings: Settings,
) -> SignalResult:
    if trade.notional_usdc < settings.min_trade_usdc:
        return SignalResult(name=NAME, matched=False)
    if profile.tx_count >= settings.fresh_wallet_max_tx:
        return SignalResult(name=NAME, matched=False)

    size_buckets = int(trade.notional_usdc // SIZE_BUCKET_USDC)
    score = min(BASE_SCORE + size_buckets * SIZE_BUCKET_BONUS, MAX_SCORE)
    return SignalResult(
        name=NAME,
        matched=True,
        score=score,
        detail={"tx_count": profile.tx_count, "notional_usdc": trade.notional_usdc},
    )
