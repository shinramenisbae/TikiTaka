from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime

from tikitaka.alert.dedupe import AlertDeduper
from tikitaka.alert.discord import DiscordAlerter
from tikitaka.config import Settings
from tikitaka.detectors.composite import score_trade
from tikitaka.ingest.data_api import DataAPI
from tikitaka.ingest.gamma import GammaAPI, MarketCatalog
from tikitaka.ingest.websocket import CLOBWebSocket
from tikitaka.models import Trade
from tikitaka.profiler.wallet import WalletProfiler
from tikitaka.storage.archive import ParquetArchive
from tikitaka.storage.db import Database

log = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 5.0


class Pipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database(settings.db_path)
        self.archive = ParquetArchive(settings.parquet_dir)
        self.gamma = GammaAPI()
        self.data = DataAPI()
        self.profiler = WalletProfiler(settings.polygon_rpc_url)
        self.alerter = DiscordAlerter(settings.discord_webhook_url)
        self.dedupe = AlertDeduper(self.db, self.alerter, settings.dedupe_window_min)
        self.catalog = MarketCatalog()
        self.ws: CLOBWebSocket | None = None
        self._last_ts: datetime | None = None
        self._ws_task: asyncio.Task[None] | None = None

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.stop()
        if self._ws_task is not None:
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._ws_task, timeout=2.0)
        await self.gamma.close()
        await self.data.close()
        await self.profiler.close()
        await self.alerter.close()
        self.archive.flush()
        self.db.close()

    async def refresh_markets(self) -> None:
        raw = await self.gamma.fetch_active_markets()
        added = self.catalog.ingest(raw)
        log.info(
            "Gamma: %d active markets (%d new)",
            len(self.catalog.by_market),
            len(added),
        )

    async def start_websocket(self) -> None:
        asset_ids = self.catalog.all_asset_ids()[: self.settings.max_assets_per_socket]
        if not asset_ids:
            return
        self.ws = CLOBWebSocket(self.settings.websocket_url, asset_ids)
        self._ws_task = asyncio.create_task(self.ws.run())

    async def poll_once(self) -> int:
        trades = await self.data.recent_trades(limit=500)
        trades.sort(key=lambda t: t.timestamp)
        new_trades = [t for t in trades if self._last_ts is None or t.timestamp > self._last_ts]
        if new_trades:
            self._last_ts = new_trades[-1].timestamp

        processed = 0
        for t in new_trades:
            await self._process_trade(t)
            processed += 1
        return processed

    async def _process_trade(self, trade: Trade) -> None:
        self.db.upsert_trade(trade)
        self.archive.append(trade)

        market = self.catalog.by_market.get(trade.market_id)
        if market is None:
            # unknown market — fetch in next refresh; skip scoring
            return

        profile = await self.profiler.profile(trade.wallet)
        book = self.ws.get_book(trade.asset_id) if self.ws is not None else None
        composite = score_trade(
            trade,
            profile=profile,
            market=market,
            book=book,
            settings=self.settings,
        )
        if composite.alert:
            await self.dedupe.emit(
                trade=trade,
                profile=profile,
                market=market,
                composite=composite,
            )

    async def run(self) -> None:
        await self.refresh_markets()
        await self.start_websocket()
        last_gamma = asyncio.get_event_loop().time()
        while True:
            try:
                count = await self.poll_once()
                if count:
                    log.info("Processed %d new trades", count)
            except Exception:
                log.exception("Poll iteration failed")

            now = asyncio.get_event_loop().time()
            if now - last_gamma >= self.settings.gamma_poll_seconds:
                try:
                    await self.refresh_markets()
                except Exception:
                    log.exception("Gamma refresh failed")
                last_gamma = now

            await asyncio.sleep(POLL_INTERVAL_SEC)
