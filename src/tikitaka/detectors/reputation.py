from __future__ import annotations

from tikitaka.config import Settings
from tikitaka.models import ReputationStats, SignalResult, Trade

NAME = "reputation"
BASE_SCORE = 20.0
HIGH_PNL_BONUS = 10.0
HIGH_PNL_PCT = 200.0


def detect_reputation(
    trade: Trade,
    reputation: ReputationStats | None,
    settings: Settings,
) -> SignalResult:
    """Flag modest trades placed by wallets with a track record.

    A high trade count + high percent PNL implies the wallet has been right more
    often than not. Pair that with a trade that clears the reputation floor
    (default $100, below the whale bar) and it's worth surfacing even though no
    other signal would fire.
    """
    if reputation is None:
        return SignalResult(name=NAME, matched=False)
    if trade.notional_usdc < settings.reputation_min_trade_usdc:
        return SignalResult(name=NAME, matched=False)
    if reputation.trade_count < settings.reputation_min_trades:
        return SignalResult(name=NAME, matched=False)
    if reputation.pct_pnl < settings.reputation_min_pct_pnl:
        return SignalResult(name=NAME, matched=False)

    score = BASE_SCORE
    if reputation.pct_pnl >= HIGH_PNL_PCT:
        score += HIGH_PNL_BONUS
    return SignalResult(
        name=NAME,
        matched=True,
        score=score,
        detail={
            "trade_count": reputation.trade_count,
            "pct_pnl": round(reputation.pct_pnl, 2),
            "cash_pnl": round(reputation.cash_pnl, 2),
        },
    )
