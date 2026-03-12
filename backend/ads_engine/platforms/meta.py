"""Meta (Facebook) Ads platform adapter.

Implements every method in PlatformAdapter using the Meta Marketing API v21.0.
All Tier 2 / Tier 3 methods are called ONLY by approval/executor.py — never
directly by AI or automation.

Docs: https://developers.facebook.com/docs/marketing-apis
"""

from __future__ import annotations

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ..models.base import (
    Ad,
    AdCreative,
    AdSet,
    Campaign,
    ClientConfig,
    EntityStatus,
    PerformanceMetrics,
    PerformanceReport,
    Platform,
    Targeting,
)
from .base import PlatformAdapter

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

BASE_URL = "https://graph.facebook.com/v21.0"

# Meta API status strings → our EntityStatus
_STATUS_MAP: dict[str, EntityStatus] = {
    "ACTIVE": EntityStatus.ACTIVE,
    "PAUSED": EntityStatus.PAUSED,
    "ARCHIVED": EntityStatus.ARCHIVED,
    "DELETED": EntityStatus.DELETED,
    "DRAFT": EntityStatus.DRAFT,
    "WITH_ISSUES": EntityStatus.PAUSED,  # treat as paused
    "IN_PROCESS": EntityStatus.DRAFT,
}

# Our EntityStatus → Meta API status string
_STATUS_REVERSE: dict[EntityStatus, str] = {
    EntityStatus.ACTIVE: "ACTIVE",
    EntityStatus.PAUSED: "PAUSED",
    EntityStatus.ARCHIVED: "ARCHIVED",
}

# Performance fields to request from the Insights API
_INSIGHT_FIELDS = [
    "spend",
    "impressions",
    "clicks",
    "actions",          # conversions are inside actions[]
    "cpc",
    "cpm",
    "ctr",
    "purchase_roas",
]

# Retry config
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0  # seconds


class MetaAPIError(Exception):
    """Raised when Meta API returns an error response."""

    def __init__(self, message: str, code: int = 0, subcode: int = 0):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


class MetaAdapter(PlatformAdapter):
    """Meta Marketing API adapter."""

    platform = Platform.META

    def __init__(self, client: ClientConfig, meta_config: dict):
        """
        Args:
            client: ClientConfig loaded from clients/<id>.yaml
            meta_config: section from clients/<id>.yaml under platforms.meta
                         must include: ad_account_id, access_token
        """
        super().__init__(client)
        self._ad_account_id: str = meta_config["ad_account_id"]  # act_XXXXXXXXXX
        self._access_token: str = meta_config["access_token"]
        self._page_id: Optional[str] = meta_config.get("page_id")
        self._pixel_id: Optional[str] = meta_config.get("pixel_id")
        self._http: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def _client(self) -> httpx.AsyncClient:
        """Return (or create) the shared HTTP client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=BASE_URL,
                params={"access_token": self._access_token},
                timeout=30.0,
            )
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ── Low-level request helper ───────────────────────────────────────────────

    async def _get(self, path: str, **params) -> dict:
        """GET with retry + structured error handling."""
        http = await self._client()
        last_exc: Exception = RuntimeError("No attempts made")

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await http.get(path, params=params)
                data = resp.json()

                if "error" in data:
                    err = data["error"]
                    # Rate limit (code 17 or 32) — wait and retry
                    if err.get("code") in (17, 32) and attempt < _MAX_RETRIES:
                        wait = _RETRY_BACKOFF * attempt
                        logger.warning(
                            "Meta rate limit hit (attempt %d/%d), waiting %.0fs",
                            attempt, _MAX_RETRIES, wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise MetaAPIError(
                        err.get("message", "Unknown Meta API error"),
                        code=err.get("code", 0),
                        subcode=err.get("error_subcode", 0),
                    )

                return data

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BACKOFF * attempt)
                    continue
                raise MetaAPIError(f"Request timed out after {_MAX_RETRIES} attempts") from exc

        raise last_exc

    async def _post(self, path: str, data: dict) -> dict:
        """POST with error handling (no retry — write operations should not be retried blindly)."""
        http = await self._client()
        resp = await http.post(path, data={**data, "access_token": self._access_token})
        result = resp.json()
        if "error" in result:
            err = result["error"]
            raise MetaAPIError(
                err.get("message", "Unknown Meta API error"),
                code=err.get("code", 0),
            )
        return result

    # ── Authentication ─────────────────────────────────────────────────────────

    async def authenticate(self) -> bool:
        """Validate the access token by calling /me. Tier 1."""
        try:
            data = await self._get("/me", fields="id,name")
            logger.info("Meta authenticated as: %s (%s)", data.get("name"), data.get("id"))
            return True
        except MetaAPIError as exc:
            logger.error("Meta authentication failed: %s", exc)
            raise

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_status(raw: str) -> EntityStatus:
        return _STATUS_MAP.get(raw.upper(), EntityStatus.PAUSED)

    @staticmethod
    def _parse_datetime(raw: str) -> datetime:
        """Parse Meta's ISO-8601 timestamps."""
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))

    @staticmethod
    def _parse_metrics(insights: list[dict]) -> PerformanceMetrics:
        """Convert a Meta Insights data array into PerformanceMetrics."""
        if not insights:
            return PerformanceMetrics()

        row = insights[0]

        # Conversions live inside actions[]
        conversions = 0
        for action in row.get("actions", []):
            if action.get("action_type") in ("purchase", "offsite_conversion.fb_pixel_purchase"):
                conversions += int(action.get("value", 0))

        # ROAS
        roas = None
        for roas_row in row.get("purchase_roas", []):
            try:
                roas = float(roas_row.get("value", 0))
            except (ValueError, TypeError):
                pass

        return PerformanceMetrics(
            spend=float(row.get("spend", 0)),
            impressions=int(row.get("impressions", 0)),
            clicks=int(row.get("clicks", 0)),
            conversions=conversions,
            cpc=float(row.get("cpc", 0) or 0),
            cpm=float(row.get("cpm", 0) or 0),
            ctr=float(row.get("ctr", 0) or 0),
            roas=roas,
        )

    # ── Read operations — Tier 1 ───────────────────────────────────────────────

    async def get_campaigns(self) -> list[Campaign]:
        """Fetch all campaigns for the ad account. Tier 1."""
        fields = "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time,created_time,updated_time"
        data = await self._get(
            f"/{self._ad_account_id}/campaigns",
            fields=fields,
            limit=100,
        )
        campaigns = []
        for row in data.get("data", []):
            campaigns.append(Campaign(
                id=row["id"],
                client_id=self.client.client_id,
                platform=Platform.META,
                name=row["name"],
                status=self._parse_status(row.get("status", "PAUSED")),
                objective=row.get("objective"),
                daily_budget=float(row["daily_budget"]) / 100 if row.get("daily_budget") else None,
                lifetime_budget=float(row["lifetime_budget"]) / 100 if row.get("lifetime_budget") else None,
                start_date=self._parse_datetime(row["start_time"]) if row.get("start_time") else None,
                end_date=self._parse_datetime(row["stop_time"]) if row.get("stop_time") else None,
                created_at=self._parse_datetime(row["created_time"]),
                updated_at=self._parse_datetime(row["updated_time"]),
            ))

        logger.info("Fetched %d campaigns for %s", len(campaigns), self.client.client_id)
        return campaigns

    async def get_adsets(self, campaign_id: str) -> list[AdSet]:
        """Fetch all ad sets under a campaign. Tier 1."""
        fields = "id,name,status,daily_budget,targeting,created_time,updated_time"
        data = await self._get(
            f"/{campaign_id}/adsets",
            fields=fields,
            limit=100,
        )
        adsets = []
        for row in data.get("data", []):
            raw_targeting = row.get("targeting", {})
            targeting = Targeting(
                age_min=raw_targeting.get("age_min"),
                age_max=raw_targeting.get("age_max"),
                genders=[str(g) for g in raw_targeting.get("genders", [])],
                locations=[
                    loc.get("name", loc.get("key", ""))
                    for loc in raw_targeting.get("geo_locations", {}).get("cities", [])
                    + raw_targeting.get("geo_locations", {}).get("regions", [])
                ],
                interests=[
                    i.get("name", "")
                    for i in raw_targeting.get("flexible_spec", [{}])[0].get("interests", [])
                ],
            ) if raw_targeting else None

            adsets.append(AdSet(
                id=row["id"],
                campaign_id=campaign_id,
                client_id=self.client.client_id,
                platform=Platform.META,
                name=row["name"],
                status=self._parse_status(row.get("status", "PAUSED")),
                daily_budget=float(row["daily_budget"]) / 100 if row.get("daily_budget") else None,
                targeting=targeting,
                created_at=self._parse_datetime(row["created_time"]),
                updated_at=self._parse_datetime(row["updated_time"]),
            ))

        return adsets

    async def get_ads(self, adset_id: str) -> list[Ad]:
        """Fetch all ads under an ad set. Tier 1."""
        fields = "id,name,status,creative{title,body,image_url,call_to_action},created_time,updated_time"
        data = await self._get(
            f"/{adset_id}/ads",
            fields=fields,
            limit=100,
        )

        # Fetch parent adset to get campaign_id
        adset_data = await self._get(f"/{adset_id}", fields="campaign_id")
        campaign_id = adset_data.get("campaign_id", "")

        ads = []
        for row in data.get("data", []):
            raw_creative = row.get("creative", {})
            cta = raw_creative.get("call_to_action", {})
            creative = AdCreative(
                headline=raw_creative.get("title"),
                body=raw_creative.get("body"),
                image_url=raw_creative.get("image_url"),
                call_to_action=cta.get("type") if isinstance(cta, dict) else None,
            ) if raw_creative else None

            ads.append(Ad(
                id=row["id"],
                adset_id=adset_id,
                campaign_id=campaign_id,
                client_id=self.client.client_id,
                platform=Platform.META,
                name=row["name"],
                status=self._parse_status(row.get("status", "PAUSED")),
                creative=creative,
                created_at=self._parse_datetime(row["created_time"]),
                updated_at=self._parse_datetime(row["updated_time"]),
            ))

        return ads

    async def get_campaign_performance(
        self,
        campaign_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> PerformanceReport:
        """Pull Insights for a campaign over a date range. Tier 1."""
        data = await self._get(
            f"/{campaign_id}/insights",
            fields=",".join(_INSIGHT_FIELDS),
            time_range=f'{{"since":"{date_from.strftime("%Y-%m-%d")}","until":"{date_to.strftime("%Y-%m-%d")}"}}'
        )
        metrics = self._parse_metrics(data.get("data", []))
        return PerformanceReport(
            entity_id=campaign_id,
            entity_type="campaign",
            platform=Platform.META,
            client_id=self.client.client_id,
            date_from=date_from,
            date_to=date_to,
            metrics=metrics,
        )

    async def get_adset_performance(
        self,
        adset_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> PerformanceReport:
        """Pull Insights for an ad set over a date range. Tier 1."""
        data = await self._get(
            f"/{adset_id}/insights",
            fields=",".join(_INSIGHT_FIELDS),
            time_range=f'{{"since":"{date_from.strftime("%Y-%m-%d")}","until":"{date_to.strftime("%Y-%m-%d")}"}}'
        )
        metrics = self._parse_metrics(data.get("data", []))
        return PerformanceReport(
            entity_id=adset_id,
            entity_type="adset",
            platform=Platform.META,
            client_id=self.client.client_id,
            date_from=date_from,
            date_to=date_to,
            metrics=metrics,
        )

    # ── Write operations — Tier 2 (called ONLY by executor.py after approval) ──

    async def create_campaign(
        self,
        name: str,
        objective: str,
        daily_budget: float,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Campaign:
        """Create a campaign. Tier 2 — must only be called after human approval."""
        payload: dict[str, Any] = {
            "name": name,
            "objective": objective,
            "status": "PAUSED",           # Always start paused — never go live without review
            "daily_budget": int(daily_budget * 100),  # Meta expects cents
            "special_ad_categories": [],
        }
        if start_date:
            payload["start_time"] = start_date.isoformat()
        if end_date:
            payload["stop_time"] = end_date.isoformat()

        result = await self._post(f"/{self._ad_account_id}/campaigns", payload)
        campaign_id = result["id"]

        # Fetch and return the full campaign object
        campaigns = await self.get_campaigns()
        for c in campaigns:
            if c.id == campaign_id:
                logger.info("Created campaign %s ('%s') for %s", campaign_id, name, self.client.client_id)
                return c

        # Fallback — construct minimal object if not in list yet
        now = datetime.now(timezone.utc)
        return Campaign(
            id=campaign_id,
            client_id=self.client.client_id,
            platform=Platform.META,
            name=name,
            status=EntityStatus.PAUSED,
            objective=objective,
            daily_budget=daily_budget,
            created_at=now,
            updated_at=now,
        )

    async def create_adset(
        self,
        campaign_id: str,
        name: str,
        targeting: Targeting,
        daily_budget: Optional[float] = None,
    ) -> AdSet:
        """Create an ad set. Tier 2 — must only be called after human approval."""
        # Build Meta targeting spec
        targeting_spec: dict[str, Any] = {}
        if targeting.age_min:
            targeting_spec["age_min"] = targeting.age_min
        if targeting.age_max:
            targeting_spec["age_max"] = targeting.age_max
        if targeting.genders:
            targeting_spec["genders"] = [1 if g == "male" else 2 for g in targeting.genders]
        if targeting.locations:
            targeting_spec["geo_locations"] = {
                "cities": [{"name": loc} for loc in targeting.locations]
            }
        if targeting.interests:
            targeting_spec["flexible_spec"] = [
                {"interests": [{"name": i} for i in targeting.interests]}
            ]

        payload: dict[str, Any] = {
            "name": name,
            "campaign_id": campaign_id,
            "targeting": json.dumps(targeting_spec),
            "status": "PAUSED",
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "LINK_CLICKS",
        }
        if daily_budget:
            payload["daily_budget"] = int(daily_budget * 100)
        if self._pixel_id:
            payload["promoted_object"] = f'{{"pixel_id":"{self._pixel_id}","custom_event_type":"PURCHASE"}}'

        result = await self._post(f"/{self._ad_account_id}/adsets", payload)
        adset_id = result["id"]
        logger.info("Created adset %s ('%s') in campaign %s", adset_id, name, campaign_id)

        now = datetime.now(timezone.utc)
        return AdSet(
            id=adset_id,
            campaign_id=campaign_id,
            client_id=self.client.client_id,
            platform=Platform.META,
            name=name,
            status=EntityStatus.PAUSED,
            daily_budget=daily_budget,
            targeting=targeting,
            created_at=now,
            updated_at=now,
        )

    async def create_ad(
        self,
        adset_id: str,
        name: str,
        creative: AdCreative,
    ) -> Ad:
        """Create an ad with a creative. Tier 2 — must only be called after human approval."""
        if not self._page_id:
            raise MetaAPIError("page_id is required in client config to create ads")

        # Step 1: Create ad creative
        story_spec: dict[str, Any] = {
            "page_id": self._page_id,
            "link_data": {
                "message": creative.body or "",
                "link": creative.destination_url or "",
                "name": creative.headline or "",
                "description": creative.description or "",
                "call_to_action": {"type": creative.call_to_action or "LEARN_MORE"},
            },
        }
        if creative.image_url:
            story_spec["link_data"]["picture"] = creative.image_url

        creative_payload: dict[str, Any] = {
            "name": f"{name} Creative",
            "object_story_spec": json.dumps(story_spec),
        }
        creative_result = await self._post(f"/{self._ad_account_id}/adcreatives", creative_payload)
        creative_id = creative_result["id"]

        # Step 2: Create ad referencing the creative
        ad_payload: dict[str, Any] = {
            "name": name,
            "adset_id": adset_id,
            "creative": f'{{"creative_id":"{creative_id}"}}',
            "status": "PAUSED",
        }
        result = await self._post(f"/{self._ad_account_id}/ads", ad_payload)
        ad_id = result["id"]

        # Fetch campaign_id from adset
        adset_data = await self._get(f"/{adset_id}", fields="campaign_id")
        campaign_id = adset_data.get("campaign_id", "")

        logger.info("Created ad %s ('%s') in adset %s", ad_id, name, adset_id)
        now = datetime.now(timezone.utc)
        return Ad(
            id=ad_id,
            adset_id=adset_id,
            campaign_id=campaign_id,
            client_id=self.client.client_id,
            platform=Platform.META,
            name=name,
            status=EntityStatus.PAUSED,
            creative=creative,
            created_at=now,
            updated_at=now,
        )

    async def update_campaign_budget(
        self,
        campaign_id: str,
        new_daily_budget: float,
    ) -> Campaign:
        """Change campaign daily budget. Tier 2 — must only be called after human approval."""
        await self._post(f"/{campaign_id}", {"daily_budget": int(new_daily_budget * 100)})
        logger.info(
            "Updated campaign %s budget to ₹%.2f for %s",
            campaign_id, new_daily_budget, self.client.client_id,
        )
        # Refresh and return updated campaign
        campaigns = await self.get_campaigns()
        for c in campaigns:
            if c.id == campaign_id:
                return c
        raise MetaAPIError(f"Campaign {campaign_id} not found after budget update")

    async def set_campaign_status(
        self,
        campaign_id: str,
        status: EntityStatus,
    ) -> Campaign:
        """Pause or activate a campaign. Tier 2 — must only be called after human approval."""
        meta_status = _STATUS_REVERSE.get(status)
        if not meta_status:
            raise ValueError(f"Cannot set campaign to status {status}")
        await self._post(f"/{campaign_id}", {"status": meta_status})
        logger.info("Set campaign %s status to %s", campaign_id, meta_status)
        campaigns = await self.get_campaigns()
        for c in campaigns:
            if c.id == campaign_id:
                return c
        raise MetaAPIError(f"Campaign {campaign_id} not found after status update")

    async def set_adset_status(
        self,
        adset_id: str,
        status: EntityStatus,
    ) -> AdSet:
        """Pause or activate an ad set. Tier 2 — must only be called after human approval."""
        meta_status = _STATUS_REVERSE.get(status)
        if not meta_status:
            raise ValueError(f"Cannot set adset to status {status}")
        await self._post(f"/{adset_id}", {"status": meta_status})
        logger.info("Set adset %s status to %s", adset_id, meta_status)

        # Fetch parent campaign_id then refresh adsets
        adset_data = await self._get(f"/{adset_id}", fields="campaign_id,name,status,daily_budget,targeting,created_time,updated_time")
        now = datetime.now(timezone.utc)
        return AdSet(
            id=adset_id,
            campaign_id=adset_data.get("campaign_id", ""),
            client_id=self.client.client_id,
            platform=Platform.META,
            name=adset_data.get("name", ""),
            status=self._parse_status(adset_data.get("status", "PAUSED")),
            created_at=self._parse_datetime(adset_data["created_time"]) if adset_data.get("created_time") else now,
            updated_at=now,
        )

    async def update_adset_targeting(
        self,
        adset_id: str,
        targeting: Targeting,
    ) -> AdSet:
        """Modify audience targeting on an ad set. Tier 2 — must only be called after human approval."""
        targeting_spec: dict[str, Any] = {}
        if targeting.age_min:
            targeting_spec["age_min"] = targeting.age_min
        if targeting.age_max:
            targeting_spec["age_max"] = targeting.age_max
        if targeting.genders:
            targeting_spec["genders"] = [1 if g == "male" else 2 for g in targeting.genders]
        if targeting.locations:
            targeting_spec["geo_locations"] = {
                "cities": [{"name": loc} for loc in targeting.locations]
            }
        if targeting.interests:
            targeting_spec["flexible_spec"] = [
                {"interests": [{"name": i} for i in targeting.interests]}
            ]

        await self._post(f"/{adset_id}", {
            "targeting": json.dumps(targeting_spec)
        })
        logger.info("Updated targeting on adset %s", adset_id)
        return await self.set_adset_status(adset_id, EntityStatus.PAUSED)  # re-fetch adset

    # ── Restricted operations — Tier 3 ────────────────────────────────────────

    async def delete_campaign(self, campaign_id: str) -> bool:
        """Permanently delete a campaign. Tier 3 — admin only."""
        await self._post(f"/{campaign_id}", {"status": "DELETED"})
        logger.warning(
            "DELETED campaign %s for client %s", campaign_id, self.client.client_id
        )
        return True

    async def duplicate_campaign(
        self,
        campaign_id: str,
        new_name: str,
    ) -> Campaign:
        """Duplicate a campaign using Meta's copy endpoint. Tier 2."""
        result = await self._post(
            f"/{campaign_id}/copies",
            {
                "deep_copy": "true",
                "status_option": "PAUSED",
                "rename_options": json.dumps({
                    "rename_strategy": "CUSTOMIZED_NAME",
                    "rename_suffix": "",
                    "rename_prefix": new_name,
                }),
            },
        )
        new_id = result.get("copied_campaign_id", result.get("id", ""))
        logger.info("Duplicated campaign %s → %s ('%s')", campaign_id, new_id, new_name)

        campaigns = await self.get_campaigns()
        for c in campaigns:
            if c.id == new_id:
                return c

        now = datetime.now(timezone.utc)
        return Campaign(
            id=new_id,
            client_id=self.client.client_id,
            platform=Platform.META,
            name=new_name,
            status=EntityStatus.PAUSED,
            created_at=now,
            updated_at=now,
        )
