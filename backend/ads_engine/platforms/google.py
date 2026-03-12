"""Google Ads platform adapter.

Implements every method in PlatformAdapter using the Google Ads API v18.
All Tier 2 / Tier 3 methods are called ONLY by approval/executor.py — never
directly by AI or automation.

Docs: https://developers.google.com/google-ads/api/docs/start

Credentials required in .env:
  GOOGLE_ADS_DEVELOPER_TOKEN
  GOOGLE_ADS_CLIENT_ID
  GOOGLE_ADS_CLIENT_SECRET
  GOOGLE_ADS_REFRESH_TOKEN

Customer ID set in config/clients/<id>.yaml under platforms.google.customer_id.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

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
from ..core.config import get_settings
from .base import PlatformAdapter

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_MICROS = 1_000_000  # 1 currency unit = 1,000,000 micros (Google Ads convention)

# Google Ads CampaignStatus / AdGroupStatus → our EntityStatus
_CAMPAIGN_STATUS_MAP: dict[str, EntityStatus] = {
    "ENABLED": EntityStatus.ACTIVE,
    "PAUSED": EntityStatus.PAUSED,
    "REMOVED": EntityStatus.DELETED,
    "UNKNOWN": EntityStatus.PAUSED,
    "UNSPECIFIED": EntityStatus.PAUSED,
}

_ADGROUP_STATUS_MAP: dict[str, EntityStatus] = {
    "ENABLED": EntityStatus.ACTIVE,
    "PAUSED": EntityStatus.PAUSED,
    "REMOVED": EntityStatus.DELETED,
    "UNKNOWN": EntityStatus.PAUSED,
    "UNSPECIFIED": EntityStatus.PAUSED,
}

# Our EntityStatus → Google Ads status string (for writes)
_CAMPAIGN_STATUS_REVERSE: dict[EntityStatus, str] = {
    EntityStatus.ACTIVE: "ENABLED",
    EntityStatus.PAUSED: "PAUSED",
}

_ADGROUP_STATUS_REVERSE: dict[EntityStatus, str] = {
    EntityStatus.ACTIVE: "ENABLED",
    EntityStatus.PAUSED: "PAUSED",
}

# Objective string → Google AdvertisingChannelType
_OBJECTIVE_TO_CHANNEL = {
    "SEARCH": "SEARCH",
    "DISPLAY": "DISPLAY",
    "VIDEO": "VIDEO",
    "SHOPPING": "SHOPPING",
}


# ── Custom error ──────────────────────────────────────────────────────────────


class GoogleAdsAPIError(Exception):
    """Raised when the Google Ads API returns an error."""

    def __init__(self, message: str, request_id: str = ""):
        super().__init__(message)
        self.request_id = request_id


# ── Adapter ───────────────────────────────────────────────────────────────────


class GoogleAdapter(PlatformAdapter):
    """Google Ads API adapter.

    Uses the ``google-ads`` Python client library, which handles OAuth 2.0
    token refresh automatically. All money values in the Google Ads API are
    stored in micros (1/1,000,000 of the currency unit).
    """

    platform = Platform.GOOGLE

    def __init__(self, client: ClientConfig, google_config: dict):
        """
        Args:
            client:        ClientConfig loaded from clients/<id>.yaml
            google_config: Section from clients/<id>.yaml under platforms.google.
                           Must include: customer_id
        """
        super().__init__(client)
        self._customer_id: str = str(google_config["customer_id"]).replace("-", "")
        # Lazy-initialised in _get_client() — allows tests to inject a mock directly.
        self._gads_client: Any = None

    # ── Client lifecycle ──────────────────────────────────────────────────────

    def _get_client(self) -> Any:
        """Return (or create) the GoogleAdsClient. Lazy init."""
        if self._gads_client is not None:
            return self._gads_client

        try:
            from google.ads.googleads.client import GoogleAdsClient  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "google-ads package is not installed. "
                "Run: pip install 'google-ads>=23.0.0'"
            ) from exc

        settings = get_settings()
        if not settings.google_ads_developer_token:
            raise GoogleAdsAPIError(
                "GOOGLE_ADS_DEVELOPER_TOKEN is not set in .env"
            )

        self._gads_client = GoogleAdsClient.load_from_dict(
            {
                "developer_token": settings.google_ads_developer_token,
                "client_id": settings.google_ads_client_id or "",
                "client_secret": settings.google_ads_client_secret or "",
                "refresh_token": settings.google_ads_refresh_token or "",
                "use_proto_plus": True,
            }
        )
        return self._gads_client

    # ── Service accessors ─────────────────────────────────────────────────────

    def _ga_service(self) -> Any:
        return self._get_client().get_service("GoogleAdsService")

    def _campaign_service(self) -> Any:
        return self._get_client().get_service("CampaignService")

    def _budget_service(self) -> Any:
        return self._get_client().get_service("CampaignBudgetService")

    def _adgroup_service(self) -> Any:
        return self._get_client().get_service("AdGroupService")

    def _adgroup_ad_service(self) -> Any:
        return self._get_client().get_service("AdGroupAdService")

    # ── Error handling ────────────────────────────────────────────────────────

    @staticmethod
    def _wrap_error(exc: Exception) -> None:
        """Re-raise Google API exceptions as GoogleAdsAPIError."""
        try:
            from google.ads.googleads.errors import GoogleAdsException  # type: ignore
            if isinstance(exc, GoogleAdsException):
                messages = [e.message for e in exc.failure.errors]
                raise GoogleAdsAPIError(
                    "; ".join(messages) or str(exc),
                    request_id=exc.request_id,
                ) from exc
        except ImportError:
            pass
        if not isinstance(exc, (GoogleAdsAPIError, ValueError)):
            raise GoogleAdsAPIError(str(exc)) from exc
        raise exc

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _to_float(micros: int) -> float:
        return micros / _MICROS

    @staticmethod
    def _to_micros(amount: float) -> int:
        return int(amount * _MICROS)

    @staticmethod
    def _map_status(raw: str, mapping: dict[str, EntityStatus]) -> EntityStatus:
        return mapping.get(raw.upper(), EntityStatus.PAUSED)

    @staticmethod
    def _parse_date(raw: str) -> Optional[datetime]:
        """Parse Google Ads date string ('YYYY-MM-DD') → UTC datetime."""
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    # ── Authentication ────────────────────────────────────────────────────────

    async def authenticate(self) -> bool:
        """Validate credentials with a lightweight customer query. Tier 1."""
        try:
            ga = self._ga_service()
            query = (
                "SELECT customer.id, customer.descriptive_name "
                "FROM customer LIMIT 1"
            )
            response = ga.search(customer_id=self._customer_id, query=query)
            for row in response:
                logger.info(
                    "Google Ads authenticated — account: %s (%s)",
                    row.customer.descriptive_name,
                    row.customer.id,
                )
                break
            return True
        except Exception as exc:
            logger.error("Google Ads authentication failed: %s", exc)
            self._wrap_error(exc)
            return False  # unreachable — _wrap_error always raises

    # ── Read operations — Tier 1 ──────────────────────────────────────────────

    async def get_campaigns(self) -> list[Campaign]:
        """Fetch all non-removed campaigns for the account. Tier 1."""
        query = """
            SELECT
              campaign.id,
              campaign.name,
              campaign.status,
              campaign.advertising_channel_type,
              campaign_budget.amount_micros,
              campaign.start_date,
              campaign.end_date
            FROM campaign
            WHERE campaign.status != 'REMOVED'
            ORDER BY campaign.name
        """
        try:
            ga = self._ga_service()
            response = ga.search(customer_id=self._customer_id, query=query)
            campaigns = []
            now = datetime.now(timezone.utc)
            for row in response:
                c = row.campaign
                channel = c.advertising_channel_type.name
                campaigns.append(Campaign(
                    id=str(c.id),
                    client_id=self.client.client_id,
                    platform=Platform.GOOGLE,
                    name=c.name,
                    status=self._map_status(c.status.name, _CAMPAIGN_STATUS_MAP),
                    objective=channel if channel not in ("UNKNOWN", "UNSPECIFIED") else None,
                    daily_budget=self._to_float(row.campaign_budget.amount_micros),
                    start_date=self._parse_date(c.start_date),
                    end_date=self._parse_date(c.end_date),
                    created_at=now,
                    updated_at=now,
                ))
            logger.info(
                "Fetched %d Google campaigns for %s",
                len(campaigns),
                self.client.client_id,
            )
            return campaigns
        except Exception as exc:
            self._wrap_error(exc)
            return []  # unreachable

    async def get_adsets(self, campaign_id: str) -> list[AdSet]:
        """Fetch all non-removed ad groups under a campaign. Tier 1."""
        query = f"""
            SELECT
              ad_group.id,
              ad_group.name,
              ad_group.status,
              ad_group.cpc_bid_micros
            FROM ad_group
            WHERE campaign.id = {campaign_id}
              AND ad_group.status != 'REMOVED'
        """
        try:
            ga = self._ga_service()
            response = ga.search(customer_id=self._customer_id, query=query)
            adgroups = []
            now = datetime.now(timezone.utc)
            for row in response:
                ag = row.ad_group
                adgroups.append(AdSet(
                    id=str(ag.id),
                    campaign_id=campaign_id,
                    client_id=self.client.client_id,
                    platform=Platform.GOOGLE,
                    name=ag.name,
                    status=self._map_status(ag.status.name, _ADGROUP_STATUS_MAP),
                    created_at=now,
                    updated_at=now,
                ))
            return adgroups
        except Exception as exc:
            self._wrap_error(exc)
            return []

    async def get_ads(self, adset_id: str) -> list[Ad]:
        """Fetch all non-removed ads under an ad group. Tier 1."""
        query = f"""
            SELECT
              ad_group_ad.ad.id,
              ad_group_ad.ad.name,
              ad_group_ad.status,
              ad_group_ad.ad.responsive_search_ad.headlines,
              ad_group_ad.ad.responsive_search_ad.descriptions,
              ad_group_ad.ad.final_urls,
              ad_group.campaign_id
            FROM ad_group_ad
            WHERE ad_group.id = {adset_id}
              AND ad_group_ad.status != 'REMOVED'
        """
        try:
            ga = self._ga_service()
            response = ga.search(customer_id=self._customer_id, query=query)
            ads = []
            now = datetime.now(timezone.utc)
            for row in response:
                ad = row.ad_group_ad.ad
                rsa = ad.responsive_search_ad

                headline = rsa.headlines[0].text if rsa.headlines else None
                body = rsa.descriptions[0].text if rsa.descriptions else None
                url = ad.final_urls[0] if ad.final_urls else None

                creative = AdCreative(
                    headline=headline,
                    body=body,
                    destination_url=url,
                ) if (headline or body) else None

                ads.append(Ad(
                    id=str(ad.id),
                    adset_id=adset_id,
                    campaign_id=str(row.ad_group.campaign_id),
                    client_id=self.client.client_id,
                    platform=Platform.GOOGLE,
                    name=ad.name or f"Ad {ad.id}",
                    status=self._map_status(
                        row.ad_group_ad.status.name, _ADGROUP_STATUS_MAP
                    ),
                    creative=creative,
                    created_at=now,
                    updated_at=now,
                ))
            return ads
        except Exception as exc:
            self._wrap_error(exc)
            return []

    async def get_campaign_performance(
        self,
        campaign_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> PerformanceReport:
        """Pull aggregated metrics for a campaign. Tier 1."""
        df = date_from.strftime("%Y-%m-%d")
        dt = date_to.strftime("%Y-%m-%d")
        query = f"""
            SELECT
              metrics.cost_micros,
              metrics.impressions,
              metrics.clicks,
              metrics.conversions,
              metrics.conversions_value,
              metrics.average_cpc,
              metrics.ctr
            FROM campaign
            WHERE campaign.id = {campaign_id}
              AND segments.date BETWEEN '{df}' AND '{dt}'
        """
        try:
            ga = self._ga_service()
            response = ga.search(customer_id=self._customer_id, query=query)
            metrics = self._aggregate_metrics(list(response))
            return PerformanceReport(
                entity_id=campaign_id,
                entity_type="campaign",
                platform=Platform.GOOGLE,
                client_id=self.client.client_id,
                date_from=date_from,
                date_to=date_to,
                metrics=metrics,
            )
        except Exception as exc:
            self._wrap_error(exc)
            raise

    async def get_adset_performance(
        self,
        adset_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> PerformanceReport:
        """Pull aggregated metrics for an ad group. Tier 1."""
        df = date_from.strftime("%Y-%m-%d")
        dt = date_to.strftime("%Y-%m-%d")
        query = f"""
            SELECT
              metrics.cost_micros,
              metrics.impressions,
              metrics.clicks,
              metrics.conversions,
              metrics.conversions_value,
              metrics.average_cpc,
              metrics.ctr
            FROM ad_group
            WHERE ad_group.id = {adset_id}
              AND segments.date BETWEEN '{df}' AND '{dt}'
        """
        try:
            ga = self._ga_service()
            response = ga.search(customer_id=self._customer_id, query=query)
            metrics = self._aggregate_metrics(list(response))
            return PerformanceReport(
                entity_id=adset_id,
                entity_type="adset",
                platform=Platform.GOOGLE,
                client_id=self.client.client_id,
                date_from=date_from,
                date_to=date_to,
                metrics=metrics,
            )
        except Exception as exc:
            self._wrap_error(exc)
            raise

    def _aggregate_metrics(self, rows: list) -> PerformanceMetrics:
        """Sum up metrics across all GAQL result rows."""
        total_cost = 0
        total_impressions = 0
        total_clicks = 0
        total_conversions = 0.0
        total_conv_value = 0.0
        total_cpc_micros = 0
        total_ctr = 0.0
        count = 0

        for row in rows:
            m = row.metrics
            total_cost += m.cost_micros
            total_impressions += m.impressions
            total_clicks += m.clicks
            total_conversions += m.conversions
            total_conv_value += m.conversions_value
            total_cpc_micros += m.average_cpc
            total_ctr += m.ctr
            count += 1

        spend = self._to_float(total_cost)
        cpc = self._to_float(total_cpc_micros // count) if count else 0.0
        # Google's ctr is a decimal ratio (0.012 = 1.2%) — convert to percentage
        ctr = (total_ctr / count * 100) if count else 0.0
        cpm = (spend / total_impressions * 1000) if total_impressions else 0.0
        roas = (total_conv_value / spend) if spend > 0 and total_conv_value > 0 else None

        return PerformanceMetrics(
            spend=spend,
            impressions=total_impressions,
            clicks=total_clicks,
            conversions=int(total_conversions),
            cpc=cpc,
            cpm=cpm,
            ctr=ctr,
            roas=roas,
        )

    # ── Write operations — Tier 2 (called ONLY by executor.py after approval) ─

    async def create_campaign(
        self,
        name: str,
        objective: str,
        daily_budget: float,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Campaign:
        """Create a campaign. Tier 2 — must only be called after human approval.

        Always created as PAUSED — never goes live without a separate activate action.
        """
        gads = self._get_client()
        try:
            # Step 1: Create a campaign budget resource
            budget_service = self._budget_service()
            budget_op = gads.get_type("CampaignBudgetOperation")
            budget = budget_op.create
            budget.name = f"{name} Budget"
            budget.amount_micros = self._to_micros(daily_budget)
            budget.delivery_method = gads.enums.BudgetDeliveryMethodEnum.STANDARD
            budget_resp = budget_service.mutate_campaign_budgets(
                customer_id=self._customer_id, operations=[budget_op]
            )
            budget_resource = budget_resp.results[0].resource_name

            # Step 2: Create the campaign referencing the budget
            campaign_service = self._campaign_service()
            op = gads.get_type("CampaignOperation")
            c = op.create
            c.name = name
            c.status = gads.enums.CampaignStatusEnum.PAUSED
            c.campaign_budget = budget_resource
            channel = _OBJECTIVE_TO_CHANNEL.get(objective.upper(), "SEARCH")
            c.advertising_channel_type = gads.enums.AdvertisingChannelTypeEnum[channel]
            c.manual_cpc.enhanced_cpc_enabled = True
            if start_date:
                c.start_date = start_date.strftime("%Y%m%d")
            if end_date:
                c.end_date = end_date.strftime("%Y%m%d")

            resp = campaign_service.mutate_campaigns(
                customer_id=self._customer_id, operations=[op]
            )
            new_id = resp.results[0].resource_name.split("/")[-1]
            logger.info(
                "Created Google campaign %s ('%s') for %s",
                new_id, name, self.client.client_id,
            )
            now = datetime.now(timezone.utc)
            return Campaign(
                id=new_id,
                client_id=self.client.client_id,
                platform=Platform.GOOGLE,
                name=name,
                status=EntityStatus.PAUSED,
                objective=objective,
                daily_budget=daily_budget,
                start_date=start_date,
                end_date=end_date,
                created_at=now,
                updated_at=now,
            )
        except Exception as exc:
            self._wrap_error(exc)
            raise

    async def create_adset(
        self,
        campaign_id: str,
        name: str,
        targeting: Targeting,
        daily_budget: Optional[float] = None,
    ) -> AdSet:
        """Create an ad group. Tier 2 — must only be called after human approval.

        Note: Google Ads audience targeting (location, interests, age) is set at
        the campaign level via campaign criteria, not at the ad group level.
        """
        gads = self._get_client()
        try:
            campaign_service = self._campaign_service()
            adgroup_service = self._adgroup_service()
            op = gads.get_type("AdGroupOperation")
            ag = op.create
            ag.name = name
            ag.status = gads.enums.AdGroupStatusEnum.PAUSED
            ag.campaign = campaign_service.campaign_path(self._customer_id, campaign_id)
            ag.cpc_bid_micros = self._to_micros(5.0)  # ₹5 default CPC bid

            resp = adgroup_service.mutate_ad_groups(
                customer_id=self._customer_id, operations=[op]
            )
            new_id = resp.results[0].resource_name.split("/")[-1]
            logger.info(
                "Created Google ad group %s ('%s') in campaign %s",
                new_id, name, campaign_id,
            )
            now = datetime.now(timezone.utc)
            return AdSet(
                id=new_id,
                campaign_id=campaign_id,
                client_id=self.client.client_id,
                platform=Platform.GOOGLE,
                name=name,
                status=EntityStatus.PAUSED,
                targeting=targeting,
                created_at=now,
                updated_at=now,
            )
        except Exception as exc:
            self._wrap_error(exc)
            raise

    async def create_ad(
        self,
        adset_id: str,
        name: str,
        creative: AdCreative,
    ) -> Ad:
        """Create a Responsive Search Ad. Tier 2 — must only be called after human approval."""
        gads = self._get_client()
        try:
            adgroup_service = self._adgroup_service()
            adgroup_ad_service = self._adgroup_ad_service()
            op = gads.get_type("AdGroupAdOperation")
            aga = op.create
            aga.status = gads.enums.AdGroupAdStatusEnum.PAUSED
            aga.ad_group = adgroup_service.ad_group_path(self._customer_id, adset_id)

            rsa = aga.ad.responsive_search_ad

            # Headlines — RSA requires ≥3, max 30 chars each
            raw_headlines = [creative.headline] if creative.headline else []
            while len(raw_headlines) < 3:
                raw_headlines.append("Get Your Tickets Now")
            for text in raw_headlines[:15]:
                asset = gads.get_type("AdTextAsset")
                asset.text = text[:30]
                rsa.headlines.append(asset)

            # Descriptions — RSA requires ≥2, max 90 chars each
            raw_descs = [creative.body] if creative.body else []
            while len(raw_descs) < 2:
                raw_descs.append("Book now. Limited tickets available.")
            for text in raw_descs[:4]:
                asset = gads.get_type("AdTextAsset")
                asset.text = text[:90]
                rsa.descriptions.append(asset)

            if creative.destination_url:
                aga.ad.final_urls.append(creative.destination_url)

            resp = adgroup_ad_service.mutate_ad_group_ads(
                customer_id=self._customer_id, operations=[op]
            )
            new_id = resp.results[0].resource_name.split("/")[-1]
            logger.info(
                "Created Google ad %s ('%s') in ad group %s", new_id, name, adset_id
            )
            now = datetime.now(timezone.utc)
            return Ad(
                id=new_id,
                adset_id=adset_id,
                campaign_id="",  # Not returned by create — fetch separately if needed
                client_id=self.client.client_id,
                platform=Platform.GOOGLE,
                name=name,
                status=EntityStatus.PAUSED,
                creative=creative,
                created_at=now,
                updated_at=now,
            )
        except Exception as exc:
            self._wrap_error(exc)
            raise

    async def update_campaign_budget(
        self,
        campaign_id: str,
        new_daily_budget: float,
    ) -> Campaign:
        """Update the shared budget attached to a campaign. Tier 2."""
        gads = self._get_client()
        try:
            # Look up the campaign's budget resource name
            query = f"""
                SELECT campaign.campaign_budget
                FROM campaign
                WHERE campaign.id = {campaign_id}
            """
            ga = self._ga_service()
            budget_resource = None
            for row in ga.search(customer_id=self._customer_id, query=query):
                budget_resource = row.campaign.campaign_budget
                break

            if not budget_resource:
                raise GoogleAdsAPIError(f"Campaign {campaign_id} not found")

            budget_service = self._budget_service()
            op = gads.get_type("CampaignBudgetOperation")
            b = op.update
            b.resource_name = budget_resource
            b.amount_micros = self._to_micros(new_daily_budget)
            op.update_mask.paths.append("amount_micros")
            budget_service.mutate_campaign_budgets(
                customer_id=self._customer_id, operations=[op]
            )
            logger.info(
                "Updated Google campaign %s budget to ₹%.2f for %s",
                campaign_id, new_daily_budget, self.client.client_id,
            )
            now = datetime.now(timezone.utc)
            return Campaign(
                id=campaign_id,
                client_id=self.client.client_id,
                platform=Platform.GOOGLE,
                name="",
                status=EntityStatus.PAUSED,
                daily_budget=new_daily_budget,
                created_at=now,
                updated_at=now,
            )
        except Exception as exc:
            self._wrap_error(exc)
            raise

    async def set_campaign_status(
        self,
        campaign_id: str,
        status: EntityStatus,
    ) -> Campaign:
        """Enable or pause a campaign. Tier 2."""
        google_status = _CAMPAIGN_STATUS_REVERSE.get(status)
        if not google_status:
            raise ValueError(f"Cannot set campaign to status {status!r}")
        gads = self._get_client()
        try:
            campaign_service = self._campaign_service()
            op = gads.get_type("CampaignOperation")
            c = op.update
            c.resource_name = campaign_service.campaign_path(
                self._customer_id, campaign_id
            )
            c.status = gads.enums.CampaignStatusEnum[google_status]
            op.update_mask.paths.append("status")
            campaign_service.mutate_campaigns(
                customer_id=self._customer_id, operations=[op]
            )
            logger.info("Set Google campaign %s → %s", campaign_id, google_status)
            now = datetime.now(timezone.utc)
            return Campaign(
                id=campaign_id,
                client_id=self.client.client_id,
                platform=Platform.GOOGLE,
                name="",
                status=status,
                created_at=now,
                updated_at=now,
            )
        except Exception as exc:
            self._wrap_error(exc)
            raise

    async def set_adset_status(
        self,
        adset_id: str,
        status: EntityStatus,
    ) -> AdSet:
        """Enable or pause an ad group. Tier 2."""
        google_status = _ADGROUP_STATUS_REVERSE.get(status)
        if not google_status:
            raise ValueError(f"Cannot set ad group to status {status!r}")
        gads = self._get_client()
        try:
            adgroup_service = self._adgroup_service()
            op = gads.get_type("AdGroupOperation")
            ag = op.update
            ag.resource_name = adgroup_service.ad_group_path(
                self._customer_id, adset_id
            )
            ag.status = gads.enums.AdGroupStatusEnum[google_status]
            op.update_mask.paths.append("status")
            adgroup_service.mutate_ad_groups(
                customer_id=self._customer_id, operations=[op]
            )
            logger.info("Set Google ad group %s → %s", adset_id, google_status)
            now = datetime.now(timezone.utc)
            return AdSet(
                id=adset_id,
                campaign_id="",
                client_id=self.client.client_id,
                platform=Platform.GOOGLE,
                name="",
                status=status,
                created_at=now,
                updated_at=now,
            )
        except Exception as exc:
            self._wrap_error(exc)
            raise

    async def update_adset_targeting(
        self,
        adset_id: str,
        targeting: Targeting,
    ) -> AdSet:
        """Update audience targeting.

        Google Ads manages targeting at the campaign level via campaign criteria
        (location, age, gender, topic, keyword lists). Ad-group level targeting
        adjustments (bid modifiers) are a separate API call.
        This method records the intent and logs a manual action note.
        Tier 2.
        """
        logger.info(
            "update_adset_targeting: ad group %s — Google Ads audience targeting "
            "is campaign-level. Use Google Ads UI or Campaign Criterion API for "
            "location/age/interest changes.",
            adset_id,
        )
        now = datetime.now(timezone.utc)
        return AdSet(
            id=adset_id,
            campaign_id="",
            client_id=self.client.client_id,
            platform=Platform.GOOGLE,
            name="",
            status=EntityStatus.PAUSED,
            targeting=targeting,
            created_at=now,
            updated_at=now,
        )

    # ── Restricted operations — Tier 3 ────────────────────────────────────────

    async def delete_campaign(self, campaign_id: str) -> bool:
        """Permanently remove a campaign. Tier 3 — admin only."""
        gads = self._get_client()
        try:
            campaign_service = self._campaign_service()
            op = gads.get_type("CampaignOperation")
            op.remove = campaign_service.campaign_path(
                self._customer_id, campaign_id
            )
            campaign_service.mutate_campaigns(
                customer_id=self._customer_id, operations=[op]
            )
            logger.warning(
                "REMOVED Google campaign %s for client %s",
                campaign_id, self.client.client_id,
            )
            return True
        except Exception as exc:
            self._wrap_error(exc)
            return False

    async def duplicate_campaign(
        self,
        campaign_id: str,
        new_name: str,
    ) -> Campaign:
        """Duplicate a campaign.

        Google Ads has no native copy endpoint (unlike Meta). We fetch the
        source campaign's budget and channel type, then create a new campaign
        with the same settings. Ad groups and ads must be copied separately.
        Tier 2.
        """
        try:
            query = f"""
                SELECT
                  campaign.advertising_channel_type,
                  campaign_budget.amount_micros
                FROM campaign
                WHERE campaign.id = {campaign_id}
            """
            ga = self._ga_service()
            source_budget = 1000.0
            source_objective = "SEARCH"
            for row in ga.search(customer_id=self._customer_id, query=query):
                source_budget = self._to_float(row.campaign_budget.amount_micros)
                source_objective = row.campaign.advertising_channel_type.name
                break

            logger.info(
                "Duplicating Google campaign %s → '%s'", campaign_id, new_name
            )
            return await self.create_campaign(
                name=new_name,
                objective=source_objective,
                daily_budget=source_budget,
            )
        except Exception as exc:
            self._wrap_error(exc)
            raise
