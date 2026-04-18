from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta

import pandas as pd
from rich.console import Console
from rich.table import Table

from tikitaka.config import Settings
from tikitaka.detectors.composite import score_trade
from tikitaka.ingest.gamma import GammaAPI, MarketCatalog
from tikitaka.models import Trade, WalletProfile
from tikitaka.profiler.wallet import WalletProfiler

log = logging.getLogger(__name__)


async def run_backtest(settings: Settings, *, days: int) -> None:
    console = Console()
    since = datetime.utcnow() - timedelta(days=days)

    files = sorted(settings.parquet_dir.glob("*.parquet"))
    if not files:
        console.print("[yellow]No parquet archive found — run `tikitaka backfill` first.[/]")
        return

    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df[df["timestamp"] >= since]
    if df.empty:
        console.print("[yellow]No trades within the requested window.[/]")
        return

    console.print(f"Loaded [bold]{len(df):,}[/] trades from {len(files)} parquet file(s).")

    gamma = GammaAPI()
    profiler = WalletProfiler(settings.polygon_rpc_url)
    try:
        raw = await gamma.fetch_active_markets()
    finally:
        await gamma.close()
    catalog = MarketCatalog()
    catalog.ingest(raw)

    signal_counts: Counter[str] = Counter()
    alert_rows: list[dict[str, object]] = []
    missing_market = 0

    try:
        for row in df.to_dict(orient="records"):
            trade = Trade.model_validate(row)
            market = catalog.by_market.get(trade.market_id)
            if market is None:
                missing_market += 1
                continue
            # Backtest-only: skip live RPC, assume established wallet.
            # (Real wallet profiling requires live RPC; use `run` for that.)
            profile = WalletProfile(wallet=trade.wallet, tx_count=9999)
            composite = score_trade(
                trade, profile=profile, market=market, book=None, settings=settings
            )
            for s in composite.matched_signals:
                signal_counts[s.name] += 1
            if composite.alert:
                alert_rows.append(
                    {
                        "ts": trade.timestamp.isoformat(),
                        "wallet": trade.wallet[:10],
                        "market": market.question[:50],
                        "notional": trade.notional_usdc,
                        "score": composite.composite_score,
                    }
                )
    finally:
        await profiler.close()

    t = Table(title="Signal matches (wallet age unknown in backtest)")
    t.add_column("Signal")
    t.add_column("Count", justify="right")
    for name, count in signal_counts.most_common():
        t.add_row(name, f"{count:,}")
    console.print(t)

    console.print(f"Would-fire alerts: [bold]{len(alert_rows)}[/]")
    console.print(f"Trades with unknown market metadata: {missing_market}")

    if alert_rows:
        top = sorted(alert_rows, key=lambda r: -float(r["score"]))[:10]
        t = Table(title="Top 10 scoring trades")
        for col in ("ts", "wallet", "market", "notional", "score"):
            t.add_column(col)
        for r in top:
            t.add_row(
                str(r["ts"]),
                str(r["wallet"]),
                str(r["market"]),
                f"${float(r['notional']):,.0f}",
                f"{float(r['score']):.1f}",
            )
        console.print(t)
