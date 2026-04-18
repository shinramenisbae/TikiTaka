from __future__ import annotations

from tikitaka.config import Settings
from tikitaka.detectors.fresh_wallet import detect_fresh_wallet
from tikitaka.detectors.pre_resolution import detect_pre_resolution
from tikitaka.detectors.reputation import detect_reputation
from tikitaka.detectors.sniper import detect_sniper
from tikitaka.detectors.sybil_cluster import detect_sybil_cluster
from tikitaka.detectors.whale_liquidity import detect_whale_liquidity
from tikitaka.models import (
    ClusterInfo,
    CompositeResult,
    MarketMeta,
    OrderBookSnapshot,
    ReputationStats,
    SignalResult,
    Trade,
    WalletProfile,
)

SECONDARY_WEIGHT = 0.3


def compose(signals: list[SignalResult], threshold: float) -> CompositeResult:
    matched = [s for s in signals if s.matched]
    if not matched:
        return CompositeResult(composite_score=0.0, signals=signals, alert=False)

    top = max(s.score for s in matched)
    rest = sum(s.score for s in matched) - top
    composite = top + SECONDARY_WEIGHT * rest
    return CompositeResult(
        composite_score=round(composite, 2),
        signals=signals,
        alert=composite >= threshold,
    )


def score_trade(
    trade: Trade,
    *,
    profile: WalletProfile,
    market: MarketMeta,
    book: OrderBookSnapshot | None,
    settings: Settings,
    reputation: ReputationStats | None = None,
    cluster: ClusterInfo | None = None,
    cluster_siblings: list[tuple[str, float]] | None = None,
) -> CompositeResult:
    signals = [
        detect_fresh_wallet(trade, profile, settings),
        detect_whale_liquidity(trade, book, settings),
        detect_sniper(trade, market, profile, settings),
        detect_pre_resolution(trade, market, settings),
        detect_reputation(trade, reputation, settings),
        detect_sybil_cluster(trade, cluster, cluster_siblings or [], settings),
    ]
    return compose(signals, settings.composite_threshold)
