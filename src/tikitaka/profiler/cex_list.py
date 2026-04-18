"""Known exchange / bridge hot wallets on Polygon.

Wallets funded from these addresses are NOT clustered — everyone funds from
Binance, so a shared CEX funder means nothing. Extend this list as you
observe false-positive clusters.

Addresses are lowercase-normalized.
"""

from __future__ import annotations

# Format: address -> human-readable label (label is for logging only)
CEX_AND_BRIDGE_ADDRESSES: dict[str, str] = {
    # Binance
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance Hot Wallet",
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance 15",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance 16",
    # Coinbase
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase 2",
    "0xeb2629a2734e272bcc07bda959863f316f4bd4cf": "Coinbase 6",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase 1",
    # Kraken
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken 1",
    "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13": "Kraken 2",
    # OKX
    "0x75e89d5979e4f6fba9f97c104c2f0afb3f1dcb88": "OKX 1",
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX 2",
    # Bybit
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit",
    # Crypto.com
    "0x6262998ced04146fa42253a5c0af90ca02dfd2a3": "Crypto.com",
    # Polymarket deposit helper / relayer
    "0xaaaa1e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9e": "placeholder — update when discovered",
    # Bridges
    "0xf3ce7744b291f29aea57f27e51d7b9a6c7d2e2e3": "Across Polygon Spokepool (check)",
    "0x10c6b61dbf44a083aec3780acf769c77be747e23": "Bungee / Socket (check)",
    "0x3a23f943181408eac424116af7b7790c94cb97a5": "Layerswap (check)",
    # DEX routers — funding via swap is not a Sybil signal
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 SwapRouter",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 SwapRouter02",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch v5 Router",
    "0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff": "QuickSwap Router",
}


def is_cex_or_bridge(addr: str) -> bool:
    return addr.lower() in CEX_AND_BRIDGE_ADDRESSES
