from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from tikitaka.alert.discord import DiscordAlerter, build_embed
from tikitaka.models import CompositeResult, MarketMeta, Trade, WalletProfile
from tikitaka.storage.db import Database

log = logging.getLogger(__name__)


class AlertDeduper:
    """Suppresses duplicate alerts for the same (wallet, market) within a window.

    On a duplicate, we PATCH the original Discord message with the updated composite
    score and event count rather than posting a new one.
    """

    def __init__(
        self,
        db: Database,
        alerter: DiscordAlerter,
        window_min: int,
    ) -> None:
        self.db = db
        self.alerter = alerter
        self.window = timedelta(minutes=window_min)

    async def emit(
        self,
        *,
        trade: Trade,
        profile: WalletProfile,
        market: MarketMeta,
        composite: CompositeResult,
    ) -> None:
        if not composite.alert:
            return

        existing = self.db.find_recent_alert(trade.wallet, trade.market_id, self.window)
        if existing is not None:
            alert_id, message_id, event_count = existing
            new_count = event_count + 1
            embed = build_embed(trade, profile, market, composite, event_count=new_count)
            patched = False
            if message_id:
                patched = await self.alerter.patch(message_id, embed)
            self.db.bump_alert(alert_id, composite)
            log.info(
                "Dedup hit wallet=%s market=%s patched=%s count=%d",
                trade.wallet[:10],
                trade.market_id[:10],
                patched,
                new_count,
            )
            return

        embed = build_embed(trade, profile, market, composite, event_count=1)
        message_id = await self.alerter.post(embed)
        self.db.insert_alert(
            wallet=trade.wallet,
            market_id=trade.market_id,
            trade_id=trade.trade_id,
            composite=composite,
            discord_message_id=message_id,
        )
        log.info(
            "Alert wallet=%s market=%s score=%.1f",
            trade.wallet[:10],
            trade.market_id[:10],
            composite.composite_score,
        )

    # Exposed for tests
    def _embed(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return build_embed(*args, **kwargs)
