from __future__ import annotations

from tikitaka.config import Settings
from tikitaka.models import ClusterInfo, SignalResult, Trade

NAME = "sybil_cluster"
BASE_SCORE = 30.0
LARGE_CLUSTER_BONUS = 10.0
LARGE_CLUSTER_SIZE = 5


def detect_sybil_cluster(
    trade: Trade,
    cluster: ClusterInfo | None,
    siblings: list[tuple[str, float]],
    settings: Settings,
) -> SignalResult:
    """Flag coordinated action by multiple wallets sharing a non-CEX funder.

    `siblings` is the list of (wallet, summed_notional) for OTHER wallets in
    the same funding cluster that traded the same (market, side) within the
    sybil window — the caller owns that DB query.
    """
    if cluster is None or not cluster.resolved or cluster.is_cex:
        return SignalResult(name=NAME, matched=False)
    if cluster.funding_source is None:
        return SignalResult(name=NAME, matched=False)

    total_wallets = len(siblings) + 1  # include the current trade's wallet
    if total_wallets < settings.sybil_min_cluster_size:
        return SignalResult(name=NAME, matched=False)

    total_notional = trade.notional_usdc + sum(n for _, n in siblings)
    if total_notional < settings.sybil_min_cluster_notional:
        return SignalResult(name=NAME, matched=False)

    score = BASE_SCORE
    if total_wallets >= LARGE_CLUSTER_SIZE:
        score += LARGE_CLUSTER_BONUS
    return SignalResult(
        name=NAME,
        matched=True,
        score=score,
        detail={
            "cluster_size": total_wallets,
            "cluster_notional": round(total_notional, 2),
            "funding_source": cluster.funding_source,
        },
    )
