from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from tikitaka.models import MarketMeta

GAMMA_BASE = "https://gamma-api.polymarket.com"

log = logging.getLogger(__name__)


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        return None


def _extract_token_ids(m: dict[str, Any]) -> list[str]:
    tokens = m.get("clobTokenIds")
    if isinstance(tokens, str):
        try:
            return [str(t) for t in json.loads(tokens)]
        except json.JSONDecodeError:
            return []
    if isinstance(tokens, list):
        return [str(t) for t in tokens]
    return []


class GammaAPI:
    """Client for https://gamma-api.polymarket.com — market discovery."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owns = client is None
        self._client = client or httpx.AsyncClient(base_url=GAMMA_BASE, timeout=15.0)

    async def close(self) -> None:
        if self._owns:
            await self._client.aclose()

    async def fetch_active_markets(self, page_limit: int = 500) -> list[dict[str, Any]]:
        """Paginated fetch of all currently-active markets."""
        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            resp = await self._client.get(
                "/markets",
                params={
                    "closed": "false",
                    "archived": "false",
                    "active": "true",
                    "limit": page_limit,
                    "offset": offset,
                },
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            out.extend(batch)
            if len(batch) < page_limit:
                break
            offset += page_limit
        return out


class MarketCatalog:
    """In-memory cache of market metadata keyed by both market_id and asset_id."""

    def __init__(self) -> None:
        self.by_market: dict[str, MarketMeta] = {}
        self.asset_to_market: dict[str, str] = {}

    def ingest(self, raw: list[dict[str, Any]]) -> list[str]:
        """Merge raw Gamma results into the catalog. Returns newly added market_ids."""
        added: list[str] = []
        for m in raw:
            market_id = str(m.get("conditionId") or m.get("id") or "")
            if not market_id:
                continue
            created = _parse_dt(m.get("createdAt") or m.get("startDate"))
            if created is None:
                continue
            meta = MarketMeta(
                market_id=market_id,
                question=str(m.get("question") or ""),
                slug=m.get("slug"),
                created_at=created,
                end_date=_parse_dt(m.get("endDate")),
            )
            if market_id not in self.by_market:
                added.append(market_id)
            self.by_market[market_id] = meta
            for tid in _extract_token_ids(m):
                self.asset_to_market[tid] = market_id
        return added

    def market_for_asset(self, asset_id: str) -> MarketMeta | None:
        market_id = self.asset_to_market.get(asset_id)
        if market_id is None:
            return None
        return self.by_market.get(market_id)

    def all_asset_ids(self) -> list[str]:
        return list(self.asset_to_market.keys())
