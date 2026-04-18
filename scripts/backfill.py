from __future__ import annotations

import logging
from datetime import datetime, timedelta

from tikitaka.config import Settings
from tikitaka.ingest.data_api import DataAPI
from tikitaka.storage.archive import ParquetArchive
from tikitaka.storage.db import Database

log = logging.getLogger(__name__)

PAGE_SIZE = 500
MAX_PAGES = 200  # safety cap — 100k trades per run


async def run_backfill(settings: Settings, *, days: int) -> None:
    data = DataAPI()
    db = Database(settings.db_path)
    archive = ParquetArchive(settings.parquet_dir)
    cutoff = datetime.utcnow() - timedelta(days=days)
    total = 0
    try:
        for page in range(MAX_PAGES):
            trades = await data.recent_trades(limit=PAGE_SIZE, offset=page * PAGE_SIZE)
            if not trades:
                break
            kept = 0
            for t in trades:
                if t.timestamp < cutoff:
                    continue
                db.upsert_trade(t)
                archive.append(t)
                kept += 1
            total += kept
            log.info("Page %d: %d trades kept (running total %d)", page, kept, total)
            if trades[-1].timestamp < cutoff:
                break
    finally:
        archive.flush()
        await data.close()
        db.close()
    log.info("Backfill complete — %d trades persisted from last %d day(s)", total, days)
