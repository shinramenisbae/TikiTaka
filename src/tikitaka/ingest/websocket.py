from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from tikitaka.models import OrderBookSnapshot

log = logging.getLogger(__name__)

PING_INTERVAL = 10.0
RECONNECT_BACKOFF = [1.0, 2.0, 5.0, 10.0, 30.0]


def build_subscription(asset_ids: Iterable[str]) -> dict[str, Any]:
    """Correct CLOB market-channel subscription payload.

    Fixes pselamy issue #89 — keys must be `assets_ids` (plural) and `type`
    must be `"market"`. Reference: Polymarket WebSocket guide.
    """
    return {
        "assets_ids": list(asset_ids),
        "type": "market",
    }


def _depth_from_levels(levels: list[dict[str, Any]], top_n: int = 5) -> float:
    """Sum notional (price * size) over the top N best levels.

    Each level has 'price' and 'size' as strings. Polymarket sizes are in
    outcome-token units which redeem for $1 — so price * size ≈ USDC notional.
    """
    total = 0.0
    for level in levels[:top_n]:
        try:
            total += float(level["price"]) * float(level["size"])
        except (KeyError, ValueError, TypeError):
            continue
    return total


class CLOBWebSocket:
    """Subscribes to the CLOB market channel and maintains orderbook snapshots.

    Usage:
        ws = CLOBWebSocket(url, asset_ids=[...])
        asyncio.create_task(ws.run())
        book = ws.get_book(asset_id)
    """

    def __init__(self, url: str, asset_ids: list[str]) -> None:
        self.url = url
        self.asset_ids = asset_ids
        self.books: dict[str, OrderBookSnapshot] = {}
        self._conn: ClientConnection | None = None
        self._stop = asyncio.Event()

    def get_book(self, asset_id: str) -> OrderBookSnapshot | None:
        return self.books.get(asset_id)

    async def run(self) -> None:
        attempt = 0
        while not self._stop.is_set():
            try:
                async with websockets.connect(self.url, ping_interval=None) as conn:
                    self._conn = conn
                    attempt = 0
                    await conn.send(json.dumps(build_subscription(self.asset_ids)))
                    await asyncio.gather(
                        self._heartbeat(conn),
                        self._consume(conn),
                    )
            except Exception as e:
                if self._stop.is_set():
                    break
                delay = RECONNECT_BACKOFF[min(attempt, len(RECONNECT_BACKOFF) - 1)]
                log.warning("WebSocket error, reconnecting in %.1fs: %s", delay, e)
                attempt += 1
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        self._stop.set()
        if self._conn is not None:
            await self._conn.close()

    async def _heartbeat(self, conn: ClientConnection) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(PING_INTERVAL)
            try:
                await conn.send("PING")
            except Exception:
                return

    async def _consume(self, conn: ClientConnection) -> None:
        async for raw in conn:
            if raw == "PONG" or raw == b"PONG":
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self._handle(msg)

    def _handle(self, msg: Any) -> None:
        events = msg if isinstance(msg, list) else [msg]
        for ev in events:
            if not isinstance(ev, dict):
                continue
            event_type = ev.get("event_type") or ev.get("type")
            asset_id = ev.get("asset_id") or ev.get("market")
            if not asset_id:
                continue
            if event_type == "book":
                self.books[str(asset_id)] = OrderBookSnapshot(
                    asset_id=str(asset_id),
                    bid_depth_usdc=_depth_from_levels(ev.get("bids") or []),
                    ask_depth_usdc=_depth_from_levels(ev.get("asks") or []),
                )
