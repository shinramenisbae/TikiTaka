from __future__ import annotations

from datetime import datetime

from tikitaka.config import Settings
from tikitaka.detectors.sybil_cluster import detect_sybil_cluster
from tikitaka.models import ClusterInfo

from .conftest import make_trade


def _cluster(
    *,
    resolved: bool = True,
    is_cex: bool = False,
    funder: str | None = "0xfunder",
) -> ClusterInfo:
    return ClusterInfo(
        wallet="0xnew",
        funding_source=funder,
        is_cex=is_cex,
        resolved=resolved,
    )


def test_matches_three_wallet_cluster(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=2000.0)
    siblings = [("0xa", 2000.0), ("0xb", 2000.0)]
    result = detect_sybil_cluster(trade, _cluster(), siblings, settings)
    assert result.matched
    assert result.score == 30.0
    assert result.detail["cluster_size"] == 3


def test_large_cluster_bonus(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=1500.0)
    siblings = [("0xa", 1000.0), ("0xb", 1000.0), ("0xc", 1000.0), ("0xd", 1000.0)]
    result = detect_sybil_cluster(trade, _cluster(), siblings, settings)
    assert result.matched
    assert result.score == 40.0


def test_cex_cluster_ignored(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=2000.0)
    siblings = [("0xa", 2000.0), ("0xb", 2000.0)]
    result = detect_sybil_cluster(trade, _cluster(is_cex=True), siblings, settings)
    assert not result.matched


def test_unresolved_cluster_ignored(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=2000.0)
    siblings = [("0xa", 2000.0), ("0xb", 2000.0)]
    result = detect_sybil_cluster(trade, _cluster(resolved=False), siblings, settings)
    assert not result.matched


def test_missing_funder_ignored(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=2000.0)
    siblings = [("0xa", 2000.0), ("0xb", 2000.0)]
    result = detect_sybil_cluster(trade, _cluster(funder=None), siblings, settings)
    assert not result.matched


def test_no_cluster_record(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=2000.0)
    result = detect_sybil_cluster(trade, None, [], settings)
    assert not result.matched


def test_below_cluster_size(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=3000.0)
    siblings = [("0xa", 3000.0)]  # size=2 with caller
    result = detect_sybil_cluster(trade, _cluster(), siblings, settings)
    assert not result.matched


def test_below_cluster_notional(settings: Settings, now: datetime) -> None:
    trade = make_trade(now=now, notional=500.0)
    siblings = [("0xa", 500.0), ("0xb", 500.0)]  # total=1500 < 5000
    result = detect_sybil_cluster(trade, _cluster(), siblings, settings)
    assert not result.matched
