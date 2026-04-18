from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tikitaka.models import CompositeResult, Trade


def _now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat()

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id        TEXT PRIMARY KEY,
    wallet          TEXT NOT NULL,
    market_id       TEXT NOT NULL,
    asset_id        TEXT NOT NULL,
    side            TEXT NOT NULL,
    price           REAL NOT NULL,
    size            REAL NOT NULL,
    notional_usdc   REAL NOT NULL,
    timestamp       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_wallet ON trades(wallet);
CREATE INDEX IF NOT EXISTS idx_trades_market ON trades(market_id);
CREATE INDEX IF NOT EXISTS idx_trades_ts     ON trades(timestamp);

CREATE TABLE IF NOT EXISTS wallets (
    wallet          TEXT PRIMARY KEY,
    tx_count        INTEGER NOT NULL,
    first_seen      TEXT,
    funding_source  TEXT,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS markets (
    market_id       TEXT PRIMARY KEY,
    question        TEXT NOT NULL,
    slug            TEXT,
    created_at      TEXT NOT NULL,
    end_date        TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet              TEXT NOT NULL,
    market_id           TEXT NOT NULL,
    trade_id            TEXT NOT NULL,
    composite_score     REAL NOT NULL,
    signals_json        TEXT NOT NULL,
    discord_message_id  TEXT,
    first_alert_ts      TEXT NOT NULL,
    last_update_ts      TEXT NOT NULL,
    event_count         INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_alerts_dedupe
    ON alerts(wallet, market_id, first_alert_ts);
"""


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- trades -----------------------------------------------------------
    def upsert_trade(self, trade: Trade) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO trades
            (trade_id, wallet, market_id, asset_id, side, price, size, notional_usdc, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.trade_id,
                trade.wallet,
                trade.market_id,
                trade.asset_id,
                trade.side,
                trade.price,
                trade.size,
                trade.notional_usdc,
                trade.timestamp.isoformat(),
            ),
        )

    # --- alerts / dedupe --------------------------------------------------
    def find_recent_alert(
        self, wallet: str, market_id: str, window: timedelta
    ) -> tuple[int, str | None, int] | None:
        cutoff = (datetime.now(UTC).replace(tzinfo=None) - window).isoformat()
        row = self.conn.execute(
            """
            SELECT id, discord_message_id, event_count FROM alerts
            WHERE wallet = ? AND market_id = ? AND first_alert_ts >= ?
            ORDER BY first_alert_ts DESC LIMIT 1
            """,
            (wallet, market_id, cutoff),
        ).fetchone()
        return row

    def insert_alert(
        self,
        *,
        wallet: str,
        market_id: str,
        trade_id: str,
        composite: CompositeResult,
        discord_message_id: str | None,
    ) -> int:
        now = _now_iso()
        cur = self.conn.execute(
            """
            INSERT INTO alerts
            (wallet, market_id, trade_id, composite_score, signals_json,
             discord_message_id, first_alert_ts, last_update_ts, event_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                wallet,
                market_id,
                trade_id,
                composite.composite_score,
                composite.model_dump_json(),
                discord_message_id,
                now,
                now,
            ),
        )
        return int(cur.lastrowid or 0)

    def bump_alert(self, alert_id: int, composite: CompositeResult) -> None:
        self.conn.execute(
            """
            UPDATE alerts
               SET last_update_ts = ?,
                   composite_score = MAX(composite_score, ?),
                   signals_json = ?,
                   event_count = event_count + 1
             WHERE id = ?
            """,
            (
                _now_iso(),
                composite.composite_score,
                composite.model_dump_json(),
                alert_id,
            ),
        )
