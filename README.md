# TikiTaka

**Polymarket insider & whale scanner** — a Python CLI daemon that subscribes to Polymarket's CLOB WebSocket, applies four detection heuristics, and pushes a deduplicated Discord alert when a composite risk score crosses threshold.

Built as a lean, self-hostable alternative to [polywhaler.com](https://www.polywhaler.com/) (closed-source, paywalled) and a fix for the WebSocket bugs in [pselamy/polymarket-insider-tracker](https://github.com/pselamy/polymarket-insider-tracker) — no Postgres, no Redis, no Docker.

## Features

- **Real-time CLOB WebSocket ingest** with correct subscription format and auto-reconnect
- **Four detection signals** scored on 0–100, combined into a composite score
- **Discord webhook alerts** with rich embeds (wallet, market, signals, score)
- **Dedup window** — same wallet+market within 30 min patches the original alert instead of spamming
- **SQLite + Parquet** — zero-infra local storage
- **Backfill + backtest** modes to calibrate thresholds before going live
- **MIT-licensed, transparent scoring formula**

## Detection Methodology

| Signal | Trigger | Base Score |
|---|---|---|
| **Fresh Wallet (F)** | Trade ≥ $1k USDC AND wallet tx count < 5 | 25 (+5 per $5k size bucket, cap 40) |
| **Whale + Liquidity (W)** | Notional ≥ $10k OR ≥ 2% of same-side visible depth | 20 (+20 if both) |
| **Sniper (S)** | Trade ≥ $1k within 10 min of market creation | 30 (+10 if also F) |
| **Pre-Resolution (P)** | < 6h to close AND notional ≥ $5k AND \|price − 0.5\| > 0.3 | 30 |

**Composite:** `max(F, W, S, P) + 0.3·Σ(other matched)` — alerts fire when composite ≥ 40.

All thresholds are env-tunable (see `.env.example`).

## Quickstart

```bash
# Install uv if needed: https://docs.astral.sh/uv/
uv sync
cp .env.example .env
# edit .env — set DISCORD_WEBHOOK_URL at minimum

# Backfill the last 7 days of trades
uv run tikitaka backfill --days 7

# Backtest to see how many alerts would fire (calibrate thresholds)
uv run tikitaka backtest --days 7

# Run the live scanner
uv run tikitaka run
```

## Architecture

```
src/tikitaka/
├── ingest/       # Gamma API + Data API + CLOB WebSocket
├── profiler/     # Wallet age / funding source via Polygon RPC
├── detectors/    # Four signals + composite scoring
├── alert/        # Discord webhook + dedup
├── storage/      # SQLite + Parquet archive
└── pipeline.py   # Orchestration
```

## API References

- [Polymarket CLOB WebSocket](https://agentbets.ai/guides/polymarket-websocket-guide/) — `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- [Polymarket Gamma API](https://docs.polymarket.com/quickstart/reference/endpoints) — `https://gamma-api.polymarket.com` (market discovery)
- [Polymarket Data API](https://docs.polymarket.com/quickstart/reference/endpoints) — `https://data-api.polymarket.com` (historical activity)

## License

MIT — see [LICENSE](./LICENSE).

## Disclaimer

Flagged patterns are probabilistic indicators, not proof of insider trading. This tool is for research and personal use.
