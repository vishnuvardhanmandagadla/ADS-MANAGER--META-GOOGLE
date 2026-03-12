"""Tests for Phase 9 — WhatsApp notifications + webhook handler.

All HTTP calls are mocked — zero real API calls.
Run with: pytest tests/test_notifications.py -v
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from ads_engine.approval.action import ActionStatus, ActionType, PendingAction
from ads_engine.approval.policies import ApprovalPolicy
from ads_engine.approval.queue import init_queue
from ads_engine.models.base import Platform
from ads_engine.notifications.whatsapp import WhatsAppClient, DigestStats, _normalise_phone
from ads_engine.notifications.dispatcher import NotificationDispatcher


# ── Fixtures ───────────────────────────────────────────────────────────────────


def make_action(
    action_type: ActionType = ActionType.PAUSE_CAMPAIGN,
    tier: int = 2,
    status: ActionStatus = ActionStatus.PENDING,
) -> PendingAction:
    now = datetime.now(timezone.utc)
    return PendingAction(
        client_id="tickets99",
        platform=Platform.META,
        action_type=action_type,
        tier=tier,
        description="Pause 'Chennai Events — Broad Audience'",
        reason="CPC 3x above target",
        estimated_impact="Save ₹3,000/day",
        status=status,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=24),
        payload={"campaign_id": "camp_001"},
    )


def make_settings(
    wa_token: str = "test_token",
    wa_phone_id: str = "1234567890",
    admin_phone: str = "+919876543210",
    verify_token: str = "my_verify_token",
) -> MagicMock:
    s = MagicMock()
    s.whatsapp_api_token = wa_token
    s.whatsapp_phone_number_id = wa_phone_id
    s.admin_whatsapp = admin_phone
    s.whatsapp_verify_token = verify_token
    return s


@pytest.fixture
def queue(tmp_path):
    safety = {
        "spend_limits": {
            "max_daily_spend_per_client": 50000,
            "max_single_budget_change": 10000,
            "require_approval_above": 5000,
            "max_new_campaigns_per_day": 5,
        },
        "approval": {"cool_down_after_reject_minutes": 60},
        "restrictions": {
            "never_delete_without_admin": True,
            "never_disable_safety_rules": True,
            "never_override_budget_caps": True,
        },
    }
    return init_queue(ApprovalPolicy(safety), persist_path=tmp_path / "q.json")


@pytest.fixture
def client(queue):
    from main import create_app
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── _normalise_phone ──────────────────────────────────────────────────────────


def test_normalise_phone_strips_plus():
    assert _normalise_phone("+919876543210") == "919876543210"


def test_normalise_phone_strips_spaces_and_dashes():
    assert _normalise_phone("+91 98765-43210") == "919876543210"


def test_normalise_phone_already_clean():
    assert _normalise_phone("919876543210") == "919876543210"


# ── WhatsAppClient.send_text ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_text_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        wa = WhatsAppClient(api_token="tok", phone_number_id="pid")
        result = await wa.send_text("+919876543210", "Hello")
        assert result is True
    await wa.close()


@pytest.mark.asyncio
async def test_send_text_api_error_returns_false():
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = '{"error": "bad request"}'

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        wa = WhatsAppClient(api_token="tok", phone_number_id="pid")
        result = await wa.send_text("+919876543210", "Hello")
        assert result is False
    await wa.close()


@pytest.mark.asyncio
async def test_send_text_network_error_returns_false():
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=Exception("timeout"))):
        wa = WhatsAppClient(api_token="tok", phone_number_id="pid")
        result = await wa.send_text("+919876543210", "Hello")
        assert result is False
    await wa.close()


# ── WhatsAppClient.send_approval_request ─────────────────────────────────────


@pytest.mark.asyncio
async def test_send_approval_request_contains_short_id():
    action = make_action()
    sent_texts = []

    async def mock_send_text(to, text):
        sent_texts.append(text)
        return True

    wa = WhatsAppClient(api_token="tok", phone_number_id="pid")
    wa.send_text = mock_send_text
    await wa.send_approval_request("+91987", action)

    assert len(sent_texts) == 1
    assert action.id[:8] in sent_texts[0]
    assert "APPROVE" in sent_texts[0]
    assert "REJECT" in sent_texts[0]
    await wa.close()


# ── WhatsAppClient.send_daily_digest ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_daily_digest_contains_spend():
    stats = DigestStats(
        date="12 Mar 2026",
        total_spend=15000.0,
        pending_count=3,
        approved_today=5,
        rejected_today=1,
        top_campaign="Chennai Events",
    )
    sent_texts = []

    async def mock_send_text(to, text):
        sent_texts.append(text)
        return True

    wa = WhatsAppClient(api_token="tok", phone_number_id="pid")
    wa.send_text = mock_send_text
    await wa.send_daily_digest("+91987", stats)

    assert "15,000" in sent_texts[0]
    assert "Chennai Events" in sent_texts[0]
    assert "12 Mar 2026" in sent_texts[0]
    await wa.close()


# ── NotificationDispatcher ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatcher_on_queued_tier2_sends():
    settings = make_settings()
    dispatcher = NotificationDispatcher(settings)
    action = make_action(tier=2)

    dispatcher._wa = AsyncMock()
    dispatcher._wa.send_approval_request = AsyncMock(return_value=True)

    await dispatcher.on_queued(action)
    dispatcher._wa.send_approval_request.assert_called_once()
    await dispatcher.close()


@pytest.mark.asyncio
async def test_dispatcher_on_queued_tier1_silent():
    """Tier 1 (auto) actions should not trigger notifications."""
    settings = make_settings()
    dispatcher = NotificationDispatcher(settings)
    action = make_action(action_type=ActionType.GET_CAMPAIGNS, tier=1)

    dispatcher._wa = AsyncMock()
    dispatcher._wa.send_approval_request = AsyncMock(return_value=True)

    await dispatcher.on_queued(action)
    dispatcher._wa.send_approval_request.assert_not_called()
    await dispatcher.close()


@pytest.mark.asyncio
async def test_dispatcher_no_whatsapp_config_is_silent():
    """If WhatsApp not configured, nothing should blow up."""
    settings = make_settings(wa_token="", wa_phone_id="")
    dispatcher = NotificationDispatcher(settings)
    action = make_action()

    # Should complete without error even though _wa is None
    await dispatcher.on_queued(action)
    await dispatcher.on_approved(action)
    await dispatcher.on_rejected(action)
    await dispatcher.close()


# ── Webhook — verification ─────────────────────────────────────────────────────


def test_webhook_verify_success(client):
    with patch("ads_engine.api.routes.webhooks.get_settings") as mock_settings:
        mock_settings.return_value.whatsapp_verify_token = "secret123"
        r = client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "challenge_xyz",
                "hub.verify_token": "secret123",
            },
        )
    assert r.status_code == 200
    assert r.text == "challenge_xyz"


def test_webhook_verify_wrong_token(client):
    with patch("ads_engine.api.routes.webhooks.get_settings") as mock_settings:
        mock_settings.return_value.whatsapp_verify_token = "secret123"
        r = client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "challenge_xyz",
                "hub.verify_token": "wrong_token",
            },
        )
    assert r.status_code == 403


def test_webhook_verify_no_token_configured(client):
    with patch("ads_engine.api.routes.webhooks.get_settings") as mock_settings:
        mock_settings.return_value.whatsapp_verify_token = None
        r = client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "xyz",
                "hub.verify_token": "anything",
            },
        )
    assert r.status_code == 403


# ── Webhook — APPROVE / REJECT ────────────────────────────────────────────────


def _webhook_body(text: str, sender: str = "919876543210") -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender,
                        "type": "text",
                        "text": {"body": text},
                    }]
                }
            }]
        }]
    }


def get_token(client, username="vishnu", password="admin123") -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return r.json()["access_token"]


def test_webhook_approve_action(client, queue):
    # Queue an action first
    headers = {"Authorization": f"Bearer {get_token(client)}"}
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "pause_campaign",
            "description": "Pause Chennai Events",
            "reason": "High CPC",
            "estimated_impact": "Save ₹3,000/day",
            "payload": {"campaign_id": "camp_001"},
        },
        headers=headers,
    )
    assert r.status_code == 200
    action_id = r.json()["id"]
    short_id = action_id[:8]

    # Send APPROVE via webhook
    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        json=_webhook_body(f"APPROVE {short_id}"),
    )
    assert resp.status_code == 200

    # Verify it's approved in the queue
    action = queue.get(action_id)
    assert action.status == ActionStatus.APPROVED
    assert action.reviewed_by == "whatsapp_webhook"


def test_webhook_reject_action_with_reason(client, queue):
    headers = {"Authorization": f"Bearer {get_token(client)}"}
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "update_budget",
            "description": "Increase budget to ₹5,000",
            "reason": "Scale winner",
            "estimated_impact": "+₹2,000/day",
            "payload": {"campaign_id": "camp_001", "daily_budget": 5000},
        },
        headers=headers,
    )
    action_id = r.json()["id"]
    short_id = action_id[:8]

    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        json=_webhook_body(f"REJECT {short_id} Budget too high right now"),
    )
    assert resp.status_code == 200

    action = queue.get(action_id)
    assert action.status == ActionStatus.REJECTED
    assert action.rejection_reason == "Budget too high right now"


def test_webhook_reject_without_reason_uses_default(client, queue):
    headers = {"Authorization": f"Bearer {get_token(client)}"}
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "pause_campaign",
            "description": "Pause Hyderabad Concerts",
            "reason": "Underperforming",
            "estimated_impact": "Save ₹1,500/day",
            "payload": {"campaign_id": "camp_002"},
        },
        headers=headers,
    )
    action_id = r.json()["id"]
    short_id = action_id[:8]

    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        json=_webhook_body(f"REJECT {short_id}"),
    )
    assert resp.status_code == 200
    action = queue.get(action_id)
    assert action.status == ActionStatus.REJECTED
    assert action.rejection_reason == "Rejected via WhatsApp"


def test_webhook_unknown_command_is_ignored(client):
    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        json=_webhook_body("Hello, what is my spend today?"),
    )
    assert resp.status_code == 200  # always 200


def test_webhook_unknown_action_id_is_ignored(client):
    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        json=_webhook_body("APPROVE deadbeef"),
    )
    assert resp.status_code == 200  # no crash


def test_webhook_non_text_message_is_ignored(client):
    body = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "919876543210",
                        "type": "image",
                        "image": {"id": "img123"},
                    }]
                }
            }]
        }]
    }
    resp = client.post("/api/v1/webhooks/whatsapp", json=body)
    assert resp.status_code == 200


def test_webhook_malformed_body_returns_200(client):
    """Even completely invalid bodies must return 200 (Meta requirement)."""
    resp = client.post(
        "/api/v1/webhooks/whatsapp",
        content=b"not json at all",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
