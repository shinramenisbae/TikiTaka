from __future__ import annotations

from datetime import timedelta

from tests.conftest import make_trade
from tikitaka.config import Settings
from tikitaka.detectors import (
    detect_fresh_wallet,
    detect_pre_resolution,
    detect_sniper,
    detect_whale_liquidity,
)
from tikitaka.models import MarketMeta, OrderBookSnapshot, WalletProfile


def test_fresh_wallet_fires_on_small_new_wallet(
    settings: Settings, fresh_wallet: WalletProfile, now
) -> None:
    trade = make_trade(now=now, notional=1500)
    result = detect_fresh_wallet(trade, fresh_wallet, settings)
    assert result.matched is True
    assert result.score == 25.0


def test_fresh_wallet_size_bonus(
    settings: Settings, fresh_wallet: WalletProfile, now
) -> None:
    trade = make_trade(now=now, notional=20_000)  # 4 buckets of $5k → +20, capped at 40
    result = detect_fresh_wallet(trade, fresh_wallet, settings)
    assert result.matched is True
    assert result.score == 40.0  # capped


def test_fresh_wallet_skips_established(
    settings: Settings, established_wallet: WalletProfile, now
) -> None:
    trade = make_trade(now=now, notional=5000)
    assert detect_fresh_wallet(trade, established_wallet, settings).matched is False


def test_fresh_wallet_skips_below_min(
    settings: Settings, fresh_wallet: WalletProfile, now
) -> None:
    trade = make_trade(now=now, notional=500)
    assert detect_fresh_wallet(trade, fresh_wallet, settings).matched is False


def test_whale_notional_alone(settings: Settings, deep_book: OrderBookSnapshot, now) -> None:
    trade = make_trade(now=now, notional=12_000)
    r = detect_whale_liquidity(trade, deep_book, settings)
    assert r.matched is True
    assert r.score == 20.0  # whale only, no liquidity bonus


def test_whale_plus_liquidity_bonus(
    settings: Settings, thin_book: OrderBookSnapshot, now
) -> None:
    trade = make_trade(now=now, notional=12_000, side="BUY")
    # $12k / $10k ask depth = 120% impact, huge — both conditions match
    r = detect_whale_liquidity(trade, thin_book, settings)
    assert r.matched is True
    assert r.score == 40.0


def test_liquidity_only(settings: Settings, thin_book: OrderBookSnapshot, now) -> None:
    # 1500 / 10000 = 15% > 2% threshold → liquidity-impact alone triggers
    trade = make_trade(now=now, notional=1500, side="BUY")
    r = detect_whale_liquidity(trade, thin_book, settings)
    assert r.matched is True
    assert r.score == 20.0


def test_sniper_fires_in_window(settings: Settings, now, fresh_wallet: WalletProfile) -> None:
    market = MarketMeta(
        market_id="0xm", question="q", created_at=now - timedelta(minutes=5)
    )
    trade = make_trade(now=now, notional=2000)
    r = detect_sniper(trade, market, fresh_wallet, settings)
    assert r.matched is True
    assert r.score == 40.0  # base + fresh-wallet bonus


def test_sniper_outside_window(settings: Settings, now, fresh_wallet: WalletProfile) -> None:
    market = MarketMeta(
        market_id="0xm", question="q", created_at=now - timedelta(hours=2)
    )
    trade = make_trade(now=now, notional=2000)
    assert detect_sniper(trade, market, fresh_wallet, settings).matched is False


def test_pre_resolution_fires(settings: Settings, now) -> None:
    market = MarketMeta(
        market_id="0xm",
        question="q",
        created_at=now - timedelta(days=10),
        end_date=now + timedelta(hours=3),
    )
    trade = make_trade(now=now, notional=8000, price=0.85)
    r = detect_pre_resolution(trade, market, settings)
    assert r.matched is True
    assert r.score == 30.0


def test_pre_resolution_skip_when_price_is_flat(settings: Settings, now) -> None:
    market = MarketMeta(
        market_id="0xm",
        question="q",
        created_at=now - timedelta(days=10),
        end_date=now + timedelta(hours=3),
    )
    trade = make_trade(now=now, notional=8000, price=0.55)  # edge = 0.05 < 0.3
    assert detect_pre_resolution(trade, market, settings).matched is False


def test_pre_resolution_skip_if_window_too_wide(settings: Settings, now) -> None:
    market = MarketMeta(
        market_id="0xm",
        question="q",
        created_at=now - timedelta(days=10),
        end_date=now + timedelta(days=2),
    )
    trade = make_trade(now=now, notional=8000, price=0.85)
    assert detect_pre_resolution(trade, market, settings).matched is False
