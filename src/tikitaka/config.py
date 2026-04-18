from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_webhook_url: str = Field(default="", description="Discord webhook for alerts")
    polygon_rpc_url: str = Field(default="https://polygon-rpc.com")

    min_trade_usdc: float = 1000.0
    whale_notional_usdc: float = 10000.0
    liquidity_impact_pct: float = 0.02
    fresh_wallet_max_tx: int = 5
    sniper_window_min: int = 10
    pre_resolution_window_hours: int = 6
    pre_resolution_min_usdc: float = 5000.0
    pre_resolution_price_edge: float = 0.3
    composite_threshold: float = 40.0
    dedupe_window_min: int = 30

    db_path: Path = Path("data/tikitaka.db")
    parquet_dir: Path = Path("data/trades")

    gamma_poll_seconds: int = 60
    websocket_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    max_assets_per_socket: int = 500


def load_settings() -> Settings:
    return Settings()
