"""Core Pydantic models shared across all platform adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class Platform(str, Enum):
    META = "meta"
    GOOGLE = "google"
    TIKTOK = "tiktok"


class EntityStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    DRAFT = "draft"
    DELETED = "deleted"


class ActionTier(int, Enum):
    AUTO = 1        # Execute immediately, no approval needed
    APPROVE = 2     # Human must approve before execution
    RESTRICTED = 3  # Admin-only, extra confirmation required


# ── Performance ───────────────────────────────────────────────────────────────


class PerformanceMetrics(BaseModel):
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    cpc: float = 0.0          # Cost per click
    cpm: float = 0.0          # Cost per 1000 impressions
    ctr: float = 0.0          # Click-through rate (%)
    roas: Optional[float] = None  # Return on ad spend


class PerformanceReport(BaseModel):
    entity_id: str
    entity_type: str           # "campaign" | "adset" | "ad"
    platform: Platform
    client_id: str
    date_from: datetime
    date_to: datetime
    metrics: PerformanceMetrics
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Campaign ──────────────────────────────────────────────────────────────────


class Campaign(BaseModel):
    id: str
    client_id: str
    platform: Platform
    name: str
    status: EntityStatus
    objective: Optional[str] = None   # CONVERSIONS, TRAFFIC, AWARENESS...
    daily_budget: Optional[float] = None
    lifetime_budget: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Populated on demand
    metrics: Optional[PerformanceMetrics] = None


# ── AdSet ─────────────────────────────────────────────────────────────────────


class Targeting(BaseModel):
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    genders: Optional[list[str]] = None       # ["male", "female"]
    locations: Optional[list[str]] = None     # City/region names
    interests: Optional[list[str]] = None
    lookalike_audiences: Optional[list[str]] = None
    custom_audiences: Optional[list[str]] = None
    radius_km: Optional[int] = None


class AdSet(BaseModel):
    id: str
    campaign_id: str
    client_id: str
    platform: Platform
    name: str
    status: EntityStatus
    daily_budget: Optional[float] = None
    targeting: Optional[Targeting] = None
    created_at: datetime
    updated_at: datetime
    metrics: Optional[PerformanceMetrics] = None


# ── Ad ────────────────────────────────────────────────────────────────────────


class AdCreative(BaseModel):
    headline: Optional[str] = None
    body: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    call_to_action: Optional[str] = None      # BOOK_NOW, LEARN_MORE, SHOP_NOW...
    destination_url: Optional[str] = None


class Ad(BaseModel):
    id: str
    adset_id: str
    campaign_id: str
    client_id: str
    platform: Platform
    name: str
    status: EntityStatus
    creative: Optional[AdCreative] = None
    created_at: datetime
    updated_at: datetime
    metrics: Optional[PerformanceMetrics] = None


# ── Client ────────────────────────────────────────────────────────────────────


class ClientConfig(BaseModel):
    client_id: str
    name: str
    industry: Optional[str] = None
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"
    max_daily_spend: Optional[float] = None
    ai_context: Optional[str] = None          # Injected into every Claude prompt
