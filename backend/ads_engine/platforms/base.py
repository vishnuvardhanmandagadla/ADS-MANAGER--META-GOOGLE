"""Abstract base class that every platform adapter must implement.

Platform adapters (Meta, Google, TikTok) inherit from PlatformAdapter and
implement every abstract method. The rest of the system always talks to this
interface — never to a platform SDK directly.

Tier annotations on each method tell the approval system whether a call
can run automatically (Tier 1) or needs a human ✅ first (Tier 2/3).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from ..models.base import (
    Ad,
    AdCreative,
    AdSet,
    Campaign,
    ClientConfig,
    EntityStatus,
    PerformanceReport,
    Platform,
    Targeting,
)


class PlatformAdapter(ABC):
    """Common interface for all ad platform integrations."""

    platform: Platform  # Set by each subclass

    def __init__(self, client: ClientConfig):
        self.client = client

    # ── Authentication ─────────────────────────────────────────────────────

    @abstractmethod
    async def authenticate(self) -> bool:
        """Validate credentials. Called at startup and before any API call.
        Returns True if authenticated, raises on failure.
        Tier 1 — auto.
        """

    # ── Read operations (Tier 1 — auto, no approval needed) ────────────────

    @abstractmethod
    async def get_campaigns(self) -> list[Campaign]:
        """Fetch all campaigns for this client account. Tier 1."""

    @abstractmethod
    async def get_adsets(self, campaign_id: str) -> list[AdSet]:
        """Fetch all ad sets under a campaign. Tier 1."""

    @abstractmethod
    async def get_ads(self, adset_id: str) -> list[Ad]:
        """Fetch all ads under an ad set. Tier 1."""

    @abstractmethod
    async def get_campaign_performance(
        self,
        campaign_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> PerformanceReport:
        """Pull performance metrics for a campaign. Tier 1."""

    @abstractmethod
    async def get_adset_performance(
        self,
        adset_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> PerformanceReport:
        """Pull performance metrics for an ad set. Tier 1."""

    # ── Write operations (Tier 2 — require human approval) ─────────────────
    # NOTE: These must NEVER be called directly by AI or automation.
    #       They are called only by approval/executor.py after a human ✅.

    @abstractmethod
    async def create_campaign(
        self,
        name: str,
        objective: str,
        daily_budget: float,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Campaign:
        """Create a new campaign. Tier 2 — requires approval."""

    @abstractmethod
    async def create_adset(
        self,
        campaign_id: str,
        name: str,
        targeting: Targeting,
        daily_budget: Optional[float] = None,
    ) -> AdSet:
        """Create a new ad set. Tier 2 — requires approval."""

    @abstractmethod
    async def create_ad(
        self,
        adset_id: str,
        name: str,
        creative: AdCreative,
    ) -> Ad:
        """Create and publish an ad. Tier 2 — requires approval."""

    @abstractmethod
    async def update_campaign_budget(
        self,
        campaign_id: str,
        new_daily_budget: float,
    ) -> Campaign:
        """Change campaign daily budget. Tier 2 — requires approval."""

    @abstractmethod
    async def set_campaign_status(
        self,
        campaign_id: str,
        status: EntityStatus,
    ) -> Campaign:
        """Pause or activate a campaign. Tier 2 — requires approval."""

    @abstractmethod
    async def set_adset_status(
        self,
        adset_id: str,
        status: EntityStatus,
    ) -> AdSet:
        """Pause or activate an ad set. Tier 2 — requires approval."""

    @abstractmethod
    async def update_adset_targeting(
        self,
        adset_id: str,
        targeting: Targeting,
    ) -> AdSet:
        """Modify audience targeting. Tier 2 — requires approval."""

    # ── Restricted operations (Tier 3 — admin only) ────────────────────────

    @abstractmethod
    async def delete_campaign(self, campaign_id: str) -> bool:
        """Permanently delete a campaign. Tier 3 — admin only."""

    @abstractmethod
    async def duplicate_campaign(
        self,
        campaign_id: str,
        new_name: str,
    ) -> Campaign:
        """Duplicate a campaign with all ad sets and ads. Tier 2."""

    # ── Helpers ────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} client={self.client.client_id}>"
