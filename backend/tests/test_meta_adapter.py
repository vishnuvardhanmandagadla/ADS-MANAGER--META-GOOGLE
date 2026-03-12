"""Unit tests for the Meta platform adapter.

Uses httpx's MockTransport so no real API calls are made.
Run with: pytest tests/test_meta_adapter.py -v
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ads_engine.models.base import (
    AdCreative,
    EntityStatus,
    Platform,
    Targeting,
    ClientConfig,
)
from ads_engine.platforms.meta import MetaAdapter, MetaAPIError


# ── Fixtures ───────────────────────────────────────────────────────────────────


def make_client() -> ClientConfig:
    return ClientConfig(
        client_id="tickets99",
        name="Tickets99",
        currency="INR",
        timezone="Asia/Kolkata",
    )


def make_meta_config(
    ad_account_id: str = "act_123456789",
    access_token: str = "test_token",
    page_id: str = "page_123",
    pixel_id: str = "pixel_456",
) -> dict:
    return {
        "ad_account_id": ad_account_id,
        "access_token": access_token,
        "page_id": page_id,
        "pixel_id": pixel_id,
    }


def make_adapter() -> MetaAdapter:
    return MetaAdapter(make_client(), make_meta_config())


def mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=data)


# ── Authentication ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authenticate_success():
    adapter = make_adapter()
    with patch.object(adapter, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"id": "123", "name": "Test User"}
        result = await adapter.authenticate()
    assert result is True
    mock_get.assert_called_once_with("/me", fields="id,name")


@pytest.mark.asyncio
async def test_authenticate_failure():
    adapter = make_adapter()
    with patch.object(adapter, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = MetaAPIError("Invalid OAuth access token", code=190)
        with pytest.raises(MetaAPIError, match="Invalid OAuth"):
            await adapter.authenticate()


# ── get_campaigns ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_campaigns_returns_list():
    adapter = make_adapter()
    raw = {
        "data": [
            {
                "id": "cam_001",
                "name": "Hyderabad Events",
                "status": "ACTIVE",
                "objective": "LINK_CLICKS",
                "daily_budget": "350000",   # Meta sends paise (×100)
                "created_time": "2024-01-10T10:00:00+0000",
                "updated_time": "2024-01-11T08:00:00+0000",
            },
            {
                "id": "cam_002",
                "name": "Chennai Weekend",
                "status": "PAUSED",
                "objective": "CONVERSIONS",
                "created_time": "2024-01-12T10:00:00+0000",
                "updated_time": "2024-01-12T10:00:00+0000",
            },
        ]
    }
    with patch.object(adapter, "_get", new_callable=AsyncMock, return_value=raw):
        campaigns = await adapter.get_campaigns()

    assert len(campaigns) == 2
    assert campaigns[0].id == "cam_001"
    assert campaigns[0].name == "Hyderabad Events"
    assert campaigns[0].status == EntityStatus.ACTIVE
    assert campaigns[0].daily_budget == 3500.0   # 350000 / 100
    assert campaigns[0].platform == Platform.META
    assert campaigns[0].client_id == "tickets99"

    assert campaigns[1].status == EntityStatus.PAUSED
    assert campaigns[1].daily_budget is None


@pytest.mark.asyncio
async def test_get_campaigns_empty():
    adapter = make_adapter()
    with patch.object(adapter, "_get", new_callable=AsyncMock, return_value={"data": []}):
        campaigns = await adapter.get_campaigns()
    assert campaigns == []


# ── get_adsets ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_adsets():
    adapter = make_adapter()
    raw = {
        "data": [
            {
                "id": "ads_001",
                "name": "Lookalike 1%",
                "status": "ACTIVE",
                "daily_budget": "180000",
                "targeting": {
                    "age_min": 18,
                    "age_max": 35,
                    "geo_locations": {"cities": [{"name": "Hyderabad"}]},
                    "flexible_spec": [{"interests": [{"name": "Concerts"}]}],
                },
                "created_time": "2024-01-10T10:00:00+0000",
                "updated_time": "2024-01-10T10:00:00+0000",
            }
        ]
    }
    with patch.object(adapter, "_get", new_callable=AsyncMock, return_value=raw):
        adsets = await adapter.get_adsets("cam_001")

    assert len(adsets) == 1
    adset = adsets[0]
    assert adset.id == "ads_001"
    assert adset.campaign_id == "cam_001"
    assert adset.daily_budget == 1800.0
    assert adset.targeting.age_min == 18
    assert adset.targeting.age_max == 35
    assert "Hyderabad" in adset.targeting.locations
    assert "Concerts" in adset.targeting.interests


# ── Performance metrics ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_campaign_performance():
    adapter = make_adapter()
    raw = {
        "data": [
            {
                "spend": "12400.50",
                "impressions": "85000",
                "clicks": "3200",
                "cpc": "3.875",
                "cpm": "145.89",
                "ctr": "3.76",
                "actions": [
                    {"action_type": "purchase", "value": "47"},
                    {"action_type": "link_click", "value": "3200"},
                ],
                "purchase_roas": [{"value": "4.2"}],
            }
        ]
    }
    with patch.object(adapter, "_get", new_callable=AsyncMock, return_value=raw):
        report = await adapter.get_campaign_performance(
            "cam_001",
            datetime(2024, 1, 1),
            datetime(2024, 1, 7),
        )

    assert report.entity_id == "cam_001"
    assert report.entity_type == "campaign"
    assert report.metrics.spend == 12400.50
    assert report.metrics.clicks == 3200
    assert report.metrics.conversions == 47
    assert report.metrics.cpc == 3.875
    assert report.metrics.roas == 4.2


@pytest.mark.asyncio
async def test_get_campaign_performance_no_data():
    adapter = make_adapter()
    with patch.object(adapter, "_get", new_callable=AsyncMock, return_value={"data": []}):
        report = await adapter.get_campaign_performance(
            "cam_001", datetime(2024, 1, 1), datetime(2024, 1, 7)
        )
    assert report.metrics.spend == 0.0
    assert report.metrics.clicks == 0
    assert report.metrics.roas is None


# ── Status updates ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_campaign_status_active():
    adapter = make_adapter()
    refreshed_campaign = {
        "data": [{
            "id": "cam_001",
            "name": "Hyderabad Events",
            "status": "ACTIVE",
            "objective": "LINK_CLICKS",
            "created_time": "2024-01-10T10:00:00+0000",
            "updated_time": "2024-01-11T08:00:00+0000",
        }]
    }
    with patch.object(adapter, "_post", new_callable=AsyncMock, return_value={"success": True}):
        with patch.object(adapter, "_get", new_callable=AsyncMock, return_value=refreshed_campaign):
            campaign = await adapter.set_campaign_status("cam_001", EntityStatus.ACTIVE)

    assert campaign.status == EntityStatus.ACTIVE


@pytest.mark.asyncio
async def test_set_campaign_status_invalid():
    adapter = make_adapter()
    with pytest.raises(ValueError, match="Cannot set campaign to status"):
        await adapter.set_campaign_status("cam_001", EntityStatus.DELETED)


# ── Budget update ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_campaign_budget():
    adapter = make_adapter()
    refreshed = {
        "data": [{
            "id": "cam_001",
            "name": "Hyderabad Events",
            "status": "ACTIVE",
            "daily_budget": "350000",
            "created_time": "2024-01-10T10:00:00+0000",
            "updated_time": "2024-01-11T08:00:00+0000",
        }]
    }
    with patch.object(adapter, "_post", new_callable=AsyncMock, return_value={"success": True}):
        with patch.object(adapter, "_get", new_callable=AsyncMock, return_value=refreshed):
            campaign = await adapter.update_campaign_budget("cam_001", 3500.0)

    assert campaign.daily_budget == 3500.0


# ── Error handling ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_meta_api_error_propagates():
    adapter = make_adapter()
    with patch.object(adapter, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = MetaAPIError("Unsupported get request", code=100)
        with pytest.raises(MetaAPIError) as exc_info:
            await adapter.get_campaigns()
    assert exc_info.value.code == 100


# ── Parse helpers ──────────────────────────────────────────────────────────────


def test_parse_status_known_values():
    assert MetaAdapter._parse_status("ACTIVE") == EntityStatus.ACTIVE
    assert MetaAdapter._parse_status("PAUSED") == EntityStatus.PAUSED
    assert MetaAdapter._parse_status("ARCHIVED") == EntityStatus.ARCHIVED
    assert MetaAdapter._parse_status("DELETED") == EntityStatus.DELETED


def test_parse_status_unknown_defaults_to_paused():
    assert MetaAdapter._parse_status("UNKNOWN_FUTURE_STATUS") == EntityStatus.PAUSED


def test_parse_metrics_empty():
    metrics = MetaAdapter._parse_metrics([])
    assert metrics.spend == 0.0
    assert metrics.clicks == 0
    assert metrics.roas is None


def test_parse_metrics_full():
    row = {
        "spend": "5000",
        "impressions": "30000",
        "clicks": "1500",
        "cpc": "3.33",
        "cpm": "166.67",
        "ctr": "5.0",
        "actions": [{"action_type": "purchase", "value": "25"}],
        "purchase_roas": [{"value": "3.8"}],
    }
    metrics = MetaAdapter._parse_metrics([row])
    assert metrics.spend == 5000.0
    assert metrics.conversions == 25
    assert metrics.roas == 3.8
