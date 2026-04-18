from __future__ import annotations

from datetime import datetime

from tikitaka.config import Settings
from tikitaka.detectors.reputation import detect_reputation
from tikitaka.models import ReputationStats

from .conftest import make_trade


def _stats(
    *,
    trade_count: int = 100,
    pct_pnl: float = 80.0,
    cash_pnl: float = 2000.0,
    total_bought: float = 2500.0,
) -> ReputationStats:
    return ReputationStats(
        wallet="0xnew",
        trade_count=trade_count,
        cash_pnl=cash_pnl,
        pct_pnl=pct_pnl,
        total_bought=total_bought,
    )


def test_matches_high_pnl_high_trade_count(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=250.0)
    result = detect_reputation(trade, _stats(), settings)
    assert result.matched
    assert result.score == 20.0


def test_high_pnl_bonus(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=250.0)
    result = detect_reputation(trade, _stats(pct_pnl=300.0), settings)
    assert result.matched
    assert result.score == 30.0


def test_no_reputation_record(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=250.0)
    result = detect_reputation(trade, None, settings)
    assert not result.matched


def test_below_trade_floor(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=50.0)
    result = detect_reputation(trade, _stats(), settings)
    assert not result.matched


def test_too_few_trades(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=250.0)
    result = detect_reputation(trade, _stats(trade_count=10), settings)
    assert not result.matched


def test_pnl_below_threshold(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=250.0)
    result = detect_reputation(trade, _stats(pct_pnl=10.0), settings)
    assert not result.matched
