from __future__ import annotations

import logging

import httpx

from tikitaka.models import ReputationStats
from tikitaka.profiler.cache import TTLCache

DATA_BASE = "https://data-api.polymarket.com"
log = logging.getLogger(__name__)


class ReputationProfiler:
    """Aggregates per-wallet PNL + trade count from Polymarket's Data API.

    Uses:
      - /positions?user=ADDR  → per-position cashPnl, realizedPnl, totalBought
      - /traded?user=ADDR     → total trade count

    Results are TTL-cached (default 1h) because PNL shifts slowly for most
    wallets and the Data API is rate-limited on /positions.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        ttl_seconds: float = 3600,
    ) -> None:
        self._owns = client is None
        self._client = client or httpx.AsyncClient(base_url=DATA_BASE, timeout=15.0)
        self._cache: TTLCache[str, ReputationStats] = TTLCache(ttl_seconds=ttl_seconds)

    async def close(self) -> None:
        if self._owns:
            await self._client.aclose()

    async def fetch(self, wallet: str) -> ReputationStats:
        wallet = wallet.lower()
        cached = self._cache.get(wallet)
        if cached is not None:
            return cached
        stats = await self._compute(wallet)
        self._cache.set(wallet, stats)
        return stats

    async def _compute(self, wallet: str) -> ReputationStats:
        try:
            positions_resp, traded_resp = await self._gather(wallet)
        except httpx.HTTPError as e:
            log.warning("Reputation fetch failed for %s: %s", wallet[:10], e)
            return ReputationStats(wallet=wallet)

        positions = positions_resp if isinstance(positions_resp, list) else []
        cash_pnl = sum(float(p.get("cashPnl") or 0) for p in positions)
        total_bought = sum(float(p.get("totalBought") or 0) for p in positions)
        pct_pnl = (cash_pnl / total_bought * 100.0) if total_bought > 0 else 0.0
        trade_count = 0
        if isinstance(traded_resp, dict):
            trade_count = int(traded_resp.get("traded") or 0)

        return ReputationStats(
            wallet=wallet,
            trade_count=trade_count,
            cash_pnl=cash_pnl,
            pct_pnl=pct_pnl,
            total_bought=total_bought,
        )

    async def _gather(self, wallet: str) -> tuple[object, object]:
        pos = await self._client.get("/positions", params={"user": wallet, "limit": 500})
        tr = await self._client.get("/traded", params={"user": wallet})
        pos.raise_for_status()
        tr.raise_for_status()
        return pos.json(), tr.json()
