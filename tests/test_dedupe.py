from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from tests.conftest import make_trade
from tikitaka.alert.dedupe import AlertDeduper
from tikitaka.alert.discord import DiscordAlerter
from tikitaka.config import Settings
from tikitaka.detectors.composite import score_trade
from tikitaka.models import MarketMeta, WalletProfile
from tikitaka.storage.db import Database


class FakeAlerter(DiscordAlerter):
    def __init__(self) -> None:
        self.posts: list[dict] = []
        self.patches: list[tuple[str, dict]] = []

    async def post(self, embed: dict) -> str | None:  # type: ignore[override]
        self.posts.append(embed)
        return f"msg-{len(self.posts)}"

    async def patch(self, message_id: str, embed: dict) -> bool:  # type: ignore[override]
        self.patches.append((message_id, embed))
        return True

    async def close(self) -> None:  # type: ignore[override]
        return None


@pytest.mark.asyncio
async def test_dedupe_patches_within_window(
    tmp_path: Path, settings: Settings, now
) -> None:
    db = Database(tmp_path / "test.db")
    alerter = FakeAlerter()
    dedupe = AlertDeduper(db, alerter, window_min=30)

    market = MarketMeta(
        market_id="0xm",
        question="q",
        created_at=now - timedelta(days=10),
        end_date=now + timedelta(hours=2),
    )
    profile = WalletProfile(wallet="0xwallet", tx_count=1)
    trade1 = make_trade(now=now, wallet="0xwallet", notional=20_000, price=0.9)
    trade2 = make_trade(now=now, wallet="0xwallet", notional=25_000, price=0.91)
    trade2 = trade2.model_copy(update={"trade_id": "trade2"})

    comp1 = score_trade(trade1, profile=profile, market=market, book=None, settings=settings)
    comp2 = score_trade(trade2, profile=profile, market=market, book=None, settings=settings)
    assert comp1.alert and comp2.alert

    await dedupe.emit(trade=trade1, profile=profile, market=market, composite=comp1)
    await dedupe.emit(trade=trade2, profile=profile, market=market, composite=comp2)

    assert len(alerter.posts) == 1, "only one POST expected; the second should PATCH"
    assert len(alerter.patches) == 1
    assert alerter.patches[0][0] == "msg-1"

    db.close()
