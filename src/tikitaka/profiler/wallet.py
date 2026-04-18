from __future__ import annotations

import asyncio
import logging

import httpx

from tikitaka.models import WalletProfile
from tikitaka.profiler.cache import TTLCache

log = logging.getLogger(__name__)


class WalletProfiler:
    """Looks up wallet tx count via Polygon JSON-RPC. TTL-cached."""

    def __init__(self, rpc_url: str, client: httpx.AsyncClient | None = None) -> None:
        self.rpc_url = rpc_url
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._cache: TTLCache[str, WalletProfile] = TTLCache()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def profile(self, wallet: str) -> WalletProfile:
        wallet = wallet.lower()
        cached = self._cache.get(wallet)
        if cached is not None:
            return cached
        tx_count = await self._get_tx_count(wallet)
        profile = WalletProfile(wallet=wallet, tx_count=tx_count)
        self._cache.set(wallet, profile)
        return profile

    async def _get_tx_count(self, wallet: str) -> int:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_getTransactionCount",
            "params": [wallet, "latest"],
        }
        for attempt in range(3):
            try:
                resp = await self._client.post(self.rpc_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if "result" in data:
                    return int(data["result"], 16)
                log.warning("RPC error for %s: %s", wallet, data.get("error"))
            except httpx.HTTPError as e:
                log.warning("RPC request failed (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(0.5 * (2**attempt))
        return 9999  # fail open: treat as established wallet so we don't false-alert
