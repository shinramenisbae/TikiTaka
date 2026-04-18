from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Side = Literal["BUY", "SELL"]


class Trade(BaseModel):
    """Normalized trade event from the CLOB WebSocket or Data API backfill."""

    trade_id: str
    wallet: str
    market_id: str                  # condition_id
    asset_id: str                   # outcome token id
    side: Side
    price: float                    # 0..1
    size: float                     # outcome-token units
    notional_usdc: float            # price * size
    timestamp: datetime


class WalletProfile(BaseModel):
    wallet: str
    tx_count: int
    first_seen: datetime | None = None
    funding_source: str | None = None


class MarketMeta(BaseModel):
    market_id: str
    question: str
    created_at: datetime
    end_date: datetime | None = None
    slug: str | None = None


class OrderBookSnapshot(BaseModel):
    asset_id: str
    bid_depth_usdc: float = 0.0     # summed bid-side notional at current best levels
    ask_depth_usdc: float = 0.0


class SignalResult(BaseModel):
    name: str
    matched: bool
    score: float = 0.0
    detail: dict[str, float | str | int | bool] = Field(default_factory=dict)


class CompositeResult(BaseModel):
    composite_score: float
    signals: list[SignalResult]
    alert: bool

    @property
    def matched_signals(self) -> list[SignalResult]:
        return [s for s in self.signals if s.matched]
