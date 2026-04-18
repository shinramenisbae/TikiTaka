from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from tikitaka.models import Trade

DATA_BASE = "https://data-api.polymarket.com"

log = logging.getLogger(__name__)


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _coerce_trade(row: dict[str, Any]) -> Trade | None:
    wallet = row.get("proxyWallet") or row.get("user") or row.get("maker")
    market_id = row.get("conditionId") or row.get("market")
    asset_id = row.get("asset") or row.get("tokenId") or row.get("token")
    side_raw = (row.get("side") or "").upper()
    ts_raw = row.get("timestamp")

    if not (wallet and market_id and asset_id and ts_raw):
        return None
    side = "BUY" if side_raw.startswith("B") else "SELL"
    try:
        ts = datetime.fromtimestamp(int(ts_raw), tz=UTC).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None

    price = _to_float(row.get("price"))
    size = _to_float(row.get("size") or row.get("amount"))
    notional = _to_float(row.get("usdcSize")) or price * size
    if notional <= 0:
        return None

    return Trade(
        trade_id=str(row.get("transactionHash") or f"{wallet}:{asset_id}:{ts_raw}"),
        wallet=str(wallet).lower(),
        market_id=str(market_id),
        asset_id=str(asset_id),
        side=side,
        price=price,
        size=size,
        notional_usdc=notional,
        timestamp=ts,
    )


class DataAPI:
    """Client for https://data-api.polymarket.com — historical activity."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owns = client is None
        self._client = client or httpx.AsyncClient(base_url=DATA_BASE, timeout=20.0)

    async def close(self) -> None:
        if self._owns:
            await self._client.aclose()

    async def recent_trades(
        self, *, limit: int = 500, offset: int = 0, min_size: float = 0.0
    ) -> list[Trade]:
        params: dict[str, str | float | int] = {
            "limit": limit,
            "offset": offset,
            "takerOnly": "false",
        }
        resp = await self._client.get("/trades", params=params)
        resp.raise_for_status()
        raw = resp.json()
        if not isinstance(raw, list):
            return []
        trades = [_coerce_trade(r) for r in raw]
        filtered = [t for t in trades if t is not None]
        if min_size > 0:
            filtered = [t for t in filtered if t.notional_usdc >= min_size]
        return filtered
