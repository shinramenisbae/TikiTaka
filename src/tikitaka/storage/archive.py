from __future__ import annotations

from datetime import date
from pathlib import Path
from threading import Lock

import pandas as pd

from tikitaka.models import Trade


class ParquetArchive:
    """Append-only daily Parquet archive of all trades.

    Buffers in memory and flushes per-day to data/trades/YYYY-MM-DD.parquet.
    """

    def __init__(self, root: Path, flush_threshold: int = 500) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.flush_threshold = flush_threshold
        self._buffer: dict[date, list[dict[str, object]]] = {}
        self._lock = Lock()

    def append(self, trade: Trade) -> None:
        day = trade.timestamp.date()
        with self._lock:
            self._buffer.setdefault(day, []).append(trade.model_dump(mode="json"))
            if len(self._buffer[day]) >= self.flush_threshold:
                self._flush_day(day)

    def flush(self) -> None:
        with self._lock:
            for day in list(self._buffer.keys()):
                self._flush_day(day)

    def _flush_day(self, day: date) -> None:
        rows = self._buffer.pop(day, [])
        if not rows:
            return
        path = self.root / f"{day.isoformat()}.parquet"
        new_df = pd.DataFrame(rows)
        if path.exists():
            existing = pd.read_parquet(path)
            combined = pd.concat([existing, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["trade_id"], keep="first")
        else:
            combined = new_df
        combined.to_parquet(path, index=False)
