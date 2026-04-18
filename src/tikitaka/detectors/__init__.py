from tikitaka.detectors.composite import score_trade
from tikitaka.detectors.fresh_wallet import detect_fresh_wallet
from tikitaka.detectors.pre_resolution import detect_pre_resolution
from tikitaka.detectors.reputation import detect_reputation
from tikitaka.detectors.sniper import detect_sniper
from tikitaka.detectors.sybil_cluster import detect_sybil_cluster
from tikitaka.detectors.whale_liquidity import detect_whale_liquidity

__all__ = [
    "detect_fresh_wallet",
    "detect_pre_resolution",
    "detect_reputation",
    "detect_sniper",
    "detect_sybil_cluster",
    "detect_whale_liquidity",
    "score_trade",
]
