from __future__ import annotations

import logging
from typing import Any

import httpx

from tikitaka.models import CompositeResult, MarketMeta, Trade, WalletProfile

log = logging.getLogger(__name__)


def _score_color(score: float) -> int:
    if score >= 70:
        return 0xD9342B  # red
    if score >= 55:
        return 0xE67E22  # orange
    return 0xF1C40F      # yellow


def _market_url(market: MarketMeta) -> str:
    if market.slug:
        return f"https://polymarket.com/event/{market.slug}"
    return f"https://polymarket.com/market/{market.market_id}"


def _wallet_url(wallet: str) -> str:
    return f"https://polygonscan.com/address/{wallet}"


def build_embed(
    trade: Trade,
    profile: WalletProfile,
    market: MarketMeta,
    composite: CompositeResult,
    event_count: int = 1,
) -> dict[str, Any]:
    signal_lines = [
        f"• **{s.name}** — {s.score:.0f}" for s in composite.matched_signals
    ]
    title_prefix = f"🚨 Insider signal · composite {composite.composite_score:.0f}"
    if event_count > 1:
        title_prefix += f" · x{event_count}"
    return {
        "title": title_prefix,
        "description": f"**{market.question or market.market_id}**",
        "url": _market_url(market),
        "color": _score_color(composite.composite_score),
        "fields": [
            {"name": "Side", "value": trade.side, "inline": True},
            {
                "name": "Notional",
                "value": f"${trade.notional_usdc:,.0f}",
                "inline": True,
            },
            {"name": "Price", "value": f"{trade.price:.3f}", "inline": True},
            {
                "name": "Wallet",
                "value": f"[{trade.wallet[:10]}…]({_wallet_url(trade.wallet)})"
                f" (tx count: {profile.tx_count})",
                "inline": False,
            },
            {
                "name": "Signals",
                "value": "\n".join(signal_lines) or "—",
                "inline": False,
            },
        ],
        "timestamp": trade.timestamp.isoformat() + "Z",
        "footer": {"text": "TikiTaka"},
    }


class DiscordAlerter:
    def __init__(self, webhook_url: str, client: httpx.AsyncClient | None = None) -> None:
        self.webhook_url = webhook_url
        self._owns = client is None
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        if self._owns:
            await self._client.aclose()

    async def post(self, embed: dict[str, Any]) -> str | None:
        """POST a new webhook message. Returns the Discord message id on success."""
        if not self.webhook_url:
            log.info("Discord webhook not configured — skipping post")
            return None
        resp = await self._client.post(
            self.webhook_url,
            params={"wait": "true"},
            json={"embeds": [embed]},
        )
        if resp.status_code >= 300:
            log.warning("Discord post failed %s: %s", resp.status_code, resp.text[:200])
            return None
        return str(resp.json().get("id"))

    async def patch(self, message_id: str, embed: dict[str, Any]) -> bool:
        """Edit an existing webhook message (used for dedup updates)."""
        if not self.webhook_url or not message_id:
            return False
        url = f"{self.webhook_url}/messages/{message_id}"
        resp = await self._client.patch(url, json={"embeds": [embed]})
        if resp.status_code >= 300:
            log.warning("Discord patch failed %s: %s", resp.status_code, resp.text[:200])
            return False
        return True
