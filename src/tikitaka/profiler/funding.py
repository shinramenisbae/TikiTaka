from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import httpx

from tikitaka.models import ClusterInfo
from tikitaka.profiler.cex_list import is_cex_or_bridge

log = logging.getLogger(__name__)

# Polygon mainnet USDC contracts. The Data API reports trades against USDC,
# but users may fund either the bridged or native variant.
USDC_CONTRACTS = [
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",  # USDC.e (bridged)
    "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359",  # USDC (native)
]

# keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Polygon produces ~1 block every 2s.
BLOCKS_PER_DAY = 43_200


def _pad_address(addr: str) -> str:
    """Left-pad a 20-byte address to 32 bytes for topic matching."""
    return "0x" + addr.lower().removeprefix("0x").rjust(64, "0")


def _decode_from_topic(topic: str) -> str:
    return "0x" + topic.lower().removeprefix("0x").removeprefix("0" * 24)


class FundingResolver:
    """Finds a wallet's first USDC inbound funder on Polygon.

    Strategy: paginated eth_getLogs over the USDC Transfer topic filtered by
    `to == wallet`. Walks backwards in time in chunks; keeps the earliest
    result in the scanned window. If nothing is found in
    `lookback_days`, the wallet is treated as its own cluster (unresolved).

    Rate-limited via an internal semaphore (default 3 concurrent RPC calls).
    """

    def __init__(
        self,
        rpc_url: str,
        *,
        lookback_days: int = 30,
        client: httpx.AsyncClient | None = None,
        concurrency: int = 3,
    ) -> None:
        self.rpc_url = rpc_url
        self.lookback_days = lookback_days
        self._owns = client is None
        self._client = client or httpx.AsyncClient(timeout=20.0)
        self._sem = asyncio.Semaphore(concurrency)

    async def close(self) -> None:
        if self._owns:
            await self._client.aclose()

    async def resolve(self, wallet: str) -> ClusterInfo:
        wallet = wallet.lower()
        try:
            async with self._sem:
                funder = await self._find_first_funder(wallet)
        except httpx.HTTPError as e:
            log.warning("Funding RPC failed for %s: %s", wallet[:10], e)
            return ClusterInfo(wallet=wallet, resolved=False)

        if funder is None:
            return ClusterInfo(wallet=wallet, resolved=True)
        return ClusterInfo(
            wallet=wallet,
            funding_source=funder,
            is_cex=is_cex_or_bridge(funder),
            resolved=True,
        )

    async def _find_first_funder(self, wallet: str) -> str | None:
        latest_hex = await self._rpc("eth_blockNumber", [])
        if not isinstance(latest_hex, str):
            return None
        latest = int(latest_hex, 16)
        oldest = max(0, latest - self.lookback_days * BLOCKS_PER_DAY)

        # Scan in 10k-block chunks starting from `oldest` moving forward until
        # we find the first match (so the result really is the earliest within
        # the scanned window).
        chunk = 10_000
        to_topic = _pad_address(wallet)
        for usdc in USDC_CONTRACTS:
            start = oldest
            while start <= latest:
                end = min(start + chunk - 1, latest)
                logs = await self._rpc(
                    "eth_getLogs",
                    [
                        {
                            "address": usdc,
                            "fromBlock": hex(start),
                            "toBlock": hex(end),
                            "topics": [TRANSFER_TOPIC, None, to_topic],
                        }
                    ],
                )
                if isinstance(logs, list) and logs:
                    first = min(logs, key=lambda e: int(e["blockNumber"], 16))
                    return _decode_from_topic(first["topics"][1])
                start = end + 1
        return None

    async def _rpc(self, method: str, params: list[object]) -> object:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        resp = await self._client.post(self.rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise httpx.HTTPError(f"RPC error: {data['error']}")
        return data.get("result")


def cluster_window() -> timedelta:
    return timedelta(minutes=10)
