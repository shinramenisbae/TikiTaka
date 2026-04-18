from __future__ import annotations

from datetime import timedelta

from tests.conftest import make_trade
from tikitaka.config import Settings
from tikitaka.detectors.composite import compose, score_trade
from tikitaka.models import MarketMeta, OrderBookSnapshot, SignalResult, WalletProfile


def test_compose_single_signal_below_threshold(settings: Settings) -> None:
    signals = [SignalResult(name="x", matched=True, score=30)]
    result = compose(signals, threshold=40)
    assert result.composite_score == 30
    assert result.alert is False


def test_compose_stacks_secondary_at_30pct(settings: Settings) -> None:
    signals = [
        SignalResult(name="a", matched=True, score=30),
        SignalResult(name="b", matched=True, score=30),
    ]
    # top=30, rest=30, composite = 30 + 0.3 * 30 = 39
    result = compose(signals, threshold=40)
    assert result.composite_score == 39.0
    assert result.alert is False


def test_compose_fires_above_threshold(settings: Settings) -> None:
    signals = [
        SignalResult(name="a", matched=True, score=40),
        SignalResult(name="b", matched=True, score=20),
    ]
    # 40 + 0.3 * 20 = 46
    result = compose(signals, threshold=40)
    assert result.composite_score == 46.0
    assert result.alert is True


def test_score_trade_end_to_end_fires(settings: Settings, now) -> None:
    """A fresh wallet, whale-sized, pre-resolution, high-conviction buy — ringer case."""
    market = MarketMeta(
        market_id="0xm",
        question="q",
        created_at=now - timedelta(days=10),
        end_date=now + timedelta(hours=2),
    )
    profile = WalletProfile(wallet="0xn", tx_count=1)
    trade = make_trade(now=now, notional=20_000, price=0.9, side="BUY")
    book = OrderBookSnapshot(asset_id="0xasset", bid_depth_usdc=50_000, ask_depth_usdc=50_000)

    result = score_trade(trade, profile=profile, market=market, book=book, settings=settings)
    assert result.alert is True
    matched_names = {s.name for s in result.matched_signals}
    assert {"fresh_wallet", "whale_liquidity", "pre_resolution"} <= matched_names


def test_score_trade_quiet_on_boring_trade(settings: Settings, now) -> None:
    market = MarketMeta(
        market_id="0xm",
        question="q",
        created_at=now - timedelta(days=30),
        end_date=now + timedelta(days=30),
    )
    profile = WalletProfile(wallet="0xold", tx_count=500)
    trade = make_trade(now=now, notional=200, price=0.51)
    result = score_trade(trade, profile=profile, market=market, book=None, settings=settings)
    assert result.alert is False
    assert all(not s.matched for s in result.signals)
