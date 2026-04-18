from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tikitaka.config import Settings
from tikitaka.models import MarketMeta, OrderBookSnapshot, Trade, WalletProfile


@pytest.fixture
def settings() -> Settings:
    return Settings(discord_webhook_url="https://example.invalid/webhook")


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 4, 18, 12, 0, 0)


@pytest.fixture
def market(now: datetime) -> MarketMeta:
    return MarketMeta(
        market_id="0xmarket",
        question="Will X happen?",
        created_at=now - timedelta(days=30),
        end_date=now + timedelta(days=7),
    )


@pytest.fixture
def fresh_wallet() -> WalletProfile:
    return WalletProfile(wallet="0xnew", tx_count=2)


@pytest.fixture
def established_wallet() -> WalletProfile:
    return WalletProfile(wallet="0xold", tx_count=500)


def make_trade(
    *,
    now: datetime,
    wallet: str = "0xnew",
    notional: float = 5000.0,
    price: float = 0.5,
    side: str = "BUY",
    market_id: str = "0xmarket",
) -> Trade:
    return Trade(
        trade_id=f"t-{wallet}-{notional}-{price}",
        wallet=wallet,
        market_id=market_id,
        asset_id="0xasset",
        side=side,  # type: ignore[arg-type]
        price=price,
        size=notional / max(price, 0.001),
        notional_usdc=notional,
        timestamp=now,
    )


@pytest.fixture
def thin_book() -> OrderBookSnapshot:
    return OrderBookSnapshot(asset_id="0xasset", bid_depth_usdc=10_000, ask_depth_usdc=10_000)


@pytest.fixture
def deep_book() -> OrderBookSnapshot:
    return OrderBookSnapshot(asset_id="0xasset", bid_depth_usdc=1_000_000, ask_depth_usdc=1_000_000)
