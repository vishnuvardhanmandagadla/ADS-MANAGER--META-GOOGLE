"""Tests for Phase 8 — Google Ads platform adapter.

All Google Ads API calls are mocked — zero real API calls.
The adapter's lazy _get_client() is bypassed by injecting mock_client directly
onto the adapter instance: adapter._gads_client = mock_client.

Run with: pytest tests/test_google_adapter.py -v
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

from ads_engine.models.base import (
    AdCreative,
    ClientConfig,
    EntityStatus,
    Platform,
    Targeting,
)
from ads_engine.platforms.google import GoogleAdapter, GoogleAdsAPIError


# ── Fixtures ───────────────────────────────────────────────────────────────────


def make_client_config() -> ClientConfig:
    return ClientConfig(
        client_id="tickets99",
        name="Tickets99",
        currency="INR",
    )


def make_google_config(customer_id: str = "1234567890") -> dict:
    return {"customer_id": customer_id}


def make_adapter(mock_client: MagicMock | None = None) -> GoogleAdapter:
    """Create a GoogleAdapter with an injected mock client."""
    adapter = GoogleAdapter(
        client=make_client_config(),
        google_config=make_google_config(),
    )
    if mock_client is not None:
        adapter._gads_client = mock_client
    return adapter


def mock_row(**kwargs) -> MagicMock:
    """Build a MagicMock GAQL row with nested dot-path attribute assignment.

    Example:
        row = mock_row(**{"campaign.id": 1, "campaign.name": "X"})
        assert row.campaign.id == 1
    """
    row = MagicMock()
    for path, value in kwargs.items():
        parts = path.split(".")
        obj = row
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)
    return row


def mock_metrics_row(
    cost_micros: int = 3_000_000_000,
    impressions: int = 80_000,
    clicks: int = 1_000,
    conversions: float = 25.0,
    conversions_value: float = 12_000.0,
    average_cpc: int = 3_000_000,
    ctr: float = 0.0125,
) -> MagicMock:
    row = MagicMock()
    m = row.metrics
    m.cost_micros = cost_micros
    m.impressions = impressions
    m.clicks = clicks
    m.conversions = conversions
    m.conversions_value = conversions_value
    m.average_cpc = average_cpc
    m.ctr = ctr
    return row


# ── Helpers ────────────────────────────────────────────────────────────────────


def test_micros_to_float():
    assert GoogleAdapter._to_float(3_000_000_000) == pytest.approx(3000.0)
    assert GoogleAdapter._to_float(0) == 0.0


def test_float_to_micros():
    assert GoogleAdapter._to_micros(3000.0) == 3_000_000_000
    assert GoogleAdapter._to_micros(0.0) == 0


def test_parse_status_known_values():
    assert GoogleAdapter._map_status("ENABLED", {"ENABLED": EntityStatus.ACTIVE}) == EntityStatus.ACTIVE
    assert GoogleAdapter._map_status("PAUSED", {"PAUSED": EntityStatus.PAUSED}) == EntityStatus.PAUSED


def test_parse_status_unknown_defaults_to_paused():
    from ads_engine.platforms.google import _CAMPAIGN_STATUS_MAP
    result = GoogleAdapter._map_status("SOMETHING_WEIRD", _CAMPAIGN_STATUS_MAP)
    assert result == EntityStatus.PAUSED


def test_parse_date_valid():
    dt = GoogleAdapter._parse_date("2025-01-15")
    assert dt is not None
    assert dt.year == 2025
    assert dt.month == 1
    assert dt.day == 15


def test_parse_date_empty():
    assert GoogleAdapter._parse_date("") is None
    assert GoogleAdapter._parse_date(None) is None  # type: ignore


# ── Authentication ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authenticate_success():
    mock_client = MagicMock()
    row = mock_row(**{
        "customer.id": 1234567890,
        "customer.descriptive_name": "Tickets99",
    })
    mock_client.get_service.return_value.search.return_value = [row]

    adapter = make_adapter(mock_client)
    result = await adapter.authenticate()
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_failure():
    mock_client = MagicMock()
    mock_client.get_service.return_value.search.side_effect = RuntimeError("OAuth failed")

    adapter = make_adapter(mock_client)
    with pytest.raises(GoogleAdsAPIError):
        await adapter.authenticate()


# ── get_campaigns ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_campaigns_returns_list():
    mock_client = MagicMock()
    rows = [
        mock_row(**{
            "campaign.id": 1001,
            "campaign.name": "Chennai Events",
            "campaign.status.name": "ENABLED",
            "campaign.advertising_channel_type.name": "SEARCH",
            "campaign_budget.amount_micros": 3_000_000_000,
            "campaign.start_date": "2025-01-01",
            "campaign.end_date": "",
        }),
        mock_row(**{
            "campaign.id": 1002,
            "campaign.name": "Hyderabad Concerts",
            "campaign.status.name": "PAUSED",
            "campaign.advertising_channel_type.name": "DISPLAY",
            "campaign_budget.amount_micros": 1_500_000_000,
            "campaign.start_date": "",
            "campaign.end_date": "",
        }),
    ]
    mock_client.get_service.return_value.search.return_value = rows

    adapter = make_adapter(mock_client)
    campaigns = await adapter.get_campaigns()

    assert len(campaigns) == 2
    assert campaigns[0].name == "Chennai Events"
    assert campaigns[0].status == EntityStatus.ACTIVE
    assert campaigns[0].daily_budget == pytest.approx(3000.0)
    assert campaigns[0].platform == Platform.GOOGLE
    assert campaigns[0].client_id == "tickets99"
    assert campaigns[1].status == EntityStatus.PAUSED


@pytest.mark.asyncio
async def test_get_campaigns_empty():
    mock_client = MagicMock()
    mock_client.get_service.return_value.search.return_value = []

    adapter = make_adapter(mock_client)
    campaigns = await adapter.get_campaigns()
    assert campaigns == []


@pytest.mark.asyncio
async def test_get_campaigns_injects_client_id():
    mock_client = MagicMock()
    row = mock_row(**{
        "campaign.id": 1001,
        "campaign.name": "Test",
        "campaign.status.name": "ENABLED",
        "campaign.advertising_channel_type.name": "SEARCH",
        "campaign_budget.amount_micros": 1_000_000_000,
        "campaign.start_date": "",
        "campaign.end_date": "",
    })
    mock_client.get_service.return_value.search.return_value = [row]

    adapter = make_adapter(mock_client)
    campaigns = await adapter.get_campaigns()
    assert all(c.client_id == "tickets99" for c in campaigns)


# ── get_adsets ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_adsets():
    mock_client = MagicMock()
    rows = [
        mock_row(**{
            "ad_group.id": 201,
            "ad_group.name": "Broad Match Group",
            "ad_group.status.name": "ENABLED",
            "ad_group.cpc_bid_micros": 5_000_000,
        }),
    ]
    mock_client.get_service.return_value.search.return_value = rows

    adapter = make_adapter(mock_client)
    adsets = await adapter.get_adsets("1001")

    assert len(adsets) == 1
    assert adsets[0].name == "Broad Match Group"
    assert adsets[0].status == EntityStatus.ACTIVE
    assert adsets[0].campaign_id == "1001"
    assert adsets[0].platform == Platform.GOOGLE


# ── get_campaign_performance ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_campaign_performance():
    mock_client = MagicMock()
    mock_client.get_service.return_value.search.return_value = [mock_metrics_row()]

    adapter = make_adapter(mock_client)
    date_from = datetime(2025, 3, 1, tzinfo=timezone.utc)
    date_to = datetime(2025, 3, 7, tzinfo=timezone.utc)
    report = await adapter.get_campaign_performance("1001", date_from, date_to)

    assert report.entity_id == "1001"
    assert report.entity_type == "campaign"
    assert report.platform == Platform.GOOGLE
    assert report.metrics.spend == pytest.approx(3000.0)
    assert report.metrics.impressions == 80_000
    assert report.metrics.clicks == 1_000
    assert report.metrics.conversions == 25
    assert report.metrics.roas == pytest.approx(12_000.0 / 3000.0)
    # CTR: 0.0125 * 100 = 1.25%
    assert report.metrics.ctr == pytest.approx(1.25)


@pytest.mark.asyncio
async def test_get_campaign_performance_no_data():
    mock_client = MagicMock()
    mock_client.get_service.return_value.search.return_value = []

    adapter = make_adapter(mock_client)
    date_from = datetime(2025, 3, 1, tzinfo=timezone.utc)
    date_to = datetime(2025, 3, 7, tzinfo=timezone.utc)
    report = await adapter.get_campaign_performance("1001", date_from, date_to)

    assert report.metrics.spend == 0.0
    assert report.metrics.clicks == 0
    assert report.metrics.roas is None


# ── set_campaign_status ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_campaign_status_paused():
    mock_client = MagicMock()
    mock_op = MagicMock()
    mock_client.get_type.return_value = mock_op
    mock_client.get_service.return_value.campaign_path.return_value = (
        "customers/123/campaigns/1001"
    )

    adapter = make_adapter(mock_client)
    campaign = await adapter.set_campaign_status("1001", EntityStatus.PAUSED)

    assert campaign.status == EntityStatus.PAUSED
    assert campaign.id == "1001"
    mock_client.get_service.return_value.mutate_campaigns.assert_called_once()


@pytest.mark.asyncio
async def test_set_campaign_status_enabled():
    mock_client = MagicMock()
    mock_op = MagicMock()
    mock_client.get_type.return_value = mock_op
    mock_client.get_service.return_value.campaign_path.return_value = (
        "customers/123/campaigns/1001"
    )

    adapter = make_adapter(mock_client)
    campaign = await adapter.set_campaign_status("1001", EntityStatus.ACTIVE)
    assert campaign.status == EntityStatus.ACTIVE


@pytest.mark.asyncio
async def test_set_campaign_status_invalid():
    mock_client = MagicMock()
    adapter = make_adapter(mock_client)
    with pytest.raises(ValueError):
        await adapter.set_campaign_status("1001", EntityStatus.DELETED)


# ── update_campaign_budget ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_campaign_budget():
    mock_client = MagicMock()
    # search returns a row with campaign_budget resource name
    budget_row = MagicMock()
    budget_row.campaign.campaign_budget = "customers/123/campaignBudgets/456"
    mock_client.get_service.return_value.search.return_value = iter([budget_row])

    adapter = make_adapter(mock_client)
    campaign = await adapter.update_campaign_budget("1001", 5000.0)

    assert campaign.daily_budget == pytest.approx(5000.0)
    mock_client.get_service.return_value.mutate_campaign_budgets.assert_called_once()


@pytest.mark.asyncio
async def test_update_campaign_budget_not_found():
    mock_client = MagicMock()
    mock_client.get_service.return_value.search.return_value = iter([])

    adapter = make_adapter(mock_client)
    with pytest.raises(GoogleAdsAPIError, match="not found"):
        await adapter.update_campaign_budget("9999", 5000.0)


# ── delete_campaign ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_campaign():
    mock_client = MagicMock()
    mock_client.get_service.return_value.campaign_path.return_value = (
        "customers/123/campaigns/1001"
    )

    adapter = make_adapter(mock_client)
    result = await adapter.delete_campaign("1001")

    assert result is True
    mock_client.get_service.return_value.mutate_campaigns.assert_called_once()


# ── aggregate_metrics ──────────────────────────────────────────────────────────


def test_aggregate_metrics_multiple_rows():
    adapter = make_adapter()
    rows = [
        mock_metrics_row(
            cost_micros=1_000_000_000, impressions=40_000, clicks=500,
            conversions=10.0, conversions_value=5000.0, average_cpc=2_000_000, ctr=0.0125,
        ),
        mock_metrics_row(
            cost_micros=2_000_000_000, impressions=40_000, clicks=500,
            conversions=15.0, conversions_value=7000.0, average_cpc=4_000_000, ctr=0.0125,
        ),
    ]
    metrics = adapter._aggregate_metrics(rows)
    assert metrics.spend == pytest.approx(3000.0)
    assert metrics.impressions == 80_000
    assert metrics.clicks == 1_000
    assert metrics.conversions == 25
    assert metrics.roas == pytest.approx(12_000.0 / 3000.0)
