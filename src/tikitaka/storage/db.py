from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tikitaka.models import ClusterInfo, CompositeResult, ReputationStats, Trade


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

CREATE TABLE IF NOT EXISTS wallet_clusters (
    wallet          TEXT PRIMARY KEY,
    funding_source  TEXT,
    is_cex          INTEGER NOT NULL DEFAULT 0,
    resolved        INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_clusters_funder
    ON wallet_clusters(funding_source);

CREATE TABLE IF NOT EXISTS wallet_reputation (
    wallet          TEXT PRIMARY KEY,
    trade_count     INTEGER NOT NULL,
    cash_pnl        REAL NOT NULL,
    pct_pnl         REAL NOT NULL,
    total_bought    REAL NOT NULL,
    updated_at      TEXT NOT NULL
);
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

    # --- wallet clusters / reputation ------------------------------------
    def upsert_cluster(self, info: ClusterInfo) -> None:
        self.conn.execute(
            """
            INSERT INTO wallet_clusters
                (wallet, funding_source, is_cex, resolved, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                funding_source = excluded.funding_source,
                is_cex         = excluded.is_cex,
                resolved       = excluded.resolved,
                updated_at     = excluded.updated_at
            """,
            (
                info.wallet,
                info.funding_source,
                1 if info.is_cex else 0,
                1 if info.resolved else 0,
                _now_iso(),
            ),
        )

    def upsert_reputation(self, stats: ReputationStats) -> None:
        self.conn.execute(
            """
            INSERT INTO wallet_reputation
                (wallet, trade_count, cash_pnl, pct_pnl, total_bought, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                trade_count  = excluded.trade_count,
                cash_pnl     = excluded.cash_pnl,
                pct_pnl      = excluded.pct_pnl,
                total_bought = excluded.total_bought,
                updated_at   = excluded.updated_at
            """,
            (
                stats.wallet,
                stats.trade_count,
                stats.cash_pnl,
                stats.pct_pnl,
                stats.total_bought,
                _now_iso(),
            ),
        )

    def cluster_siblings_recent(
        self,
        funding_source: str,
        market_id: str,
        side: str,
        window: timedelta,
        exclude_wallet: str,
    ) -> list[tuple[str, float]]:
        """Return (wallet, summed_notional) for wallets sharing `funding_source`
        that traded (market_id, side) within `window`, excluding the caller.
        """
        cutoff = (datetime.now(UTC).replace(tzinfo=None) - window).isoformat()
        rows = self.conn.execute(
            """
            SELECT t.wallet, SUM(t.notional_usdc) AS total
              FROM trades t
              JOIN wallet_clusters c ON c.wallet = t.wallet
             WHERE c.funding_source = ?
               AND c.is_cex = 0
               AND t.market_id = ?
               AND t.side = ?
               AND t.wallet != ?
               AND t.timestamp >= ?
             GROUP BY t.wallet
            """,
            (funding_source, market_id, side, exclude_wallet, cutoff),
        ).fetchall()
        return [(str(w), float(n)) for w, n in rows]

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
