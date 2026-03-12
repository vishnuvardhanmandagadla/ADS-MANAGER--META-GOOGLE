"""Tests for Phase 7 — campaigns + direct action creation endpoints.

Run with: pytest tests/test_campaigns.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ads_engine.approval.policies import ApprovalPolicy
from ads_engine.approval.queue import init_queue


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


def get_token(client, username="vishnu", password="admin123") -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(client, username="vishnu", password="admin123") -> dict:
    return {"Authorization": f"Bearer {get_token(client, username, password)}"}


# ── GET /clients/{id}/campaigns ────────────────────────────────────────────────


def test_list_campaigns_returns_list(client):
    headers = auth(client)
    r = client.get("/api/v1/clients/tickets99/campaigns", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_list_campaigns_has_required_fields(client):
    headers = auth(client)
    r = client.get("/api/v1/clients/tickets99/campaigns", headers=headers)
    camp = r.json()[0]
    for field in ("id", "name", "status", "daily_budget", "spend", "clicks", "cpc"):
        assert field in camp, f"Missing field: {field}"


def test_list_campaigns_injects_client_id(client):
    headers = auth(client)
    r = client.get("/api/v1/clients/tickets99/campaigns", headers=headers)
    assert all(c["client_id"] == "tickets99" for c in r.json())


def test_list_campaigns_requires_auth(client):
    r = client.get("/api/v1/clients/tickets99/campaigns")
    assert r.status_code == 403


def test_list_campaigns_not_found(client):
    headers = auth(client)
    r = client.get("/api/v1/clients/nonexistent/campaigns", headers=headers)
    assert r.status_code == 404


def test_manager_can_see_own_client_campaigns(client):
    headers = auth(client, "siva", "manager123")
    r = client.get("/api/v1/clients/tickets99/campaigns", headers=headers)
    assert r.status_code == 200


def test_manager_blocked_from_other_client_campaigns(client):
    headers = auth(client, "siva", "manager123")
    r = client.get("/api/v1/clients/other_client/campaigns", headers=headers)
    assert r.status_code == 403


# ── POST /actions ──────────────────────────────────────────────────────────────


def test_create_pause_action(client, queue):
    headers = auth(client)
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "pause_campaign",
            "description": "Pause 'Chennai Events — Broad Audience'",
            "reason": "CPC 3x above target",
            "estimated_impact": "Save ₹3,000/day",
            "payload": {"campaign_id": "camp_001"},
        },
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["action_type"] == "pause_campaign"
    assert data["status"] == "pending"
    assert data["tier"] == 2
    assert queue.pending_count() == 1


def test_create_budget_action(client, queue):
    headers = auth(client)
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "update_budget",
            "description": "Increase daily budget to ₹4,000",
            "reason": "ROAS 3.8x — scale winner",
            "estimated_impact": "+₹2,000 revenue/day",
            "payload": {"campaign_id": "camp_001", "daily_budget": 4000},
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["action_type"] == "update_budget"
    assert queue.pending_count() == 1


def test_create_activate_action(client, queue):
    headers = auth(client)
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "activate_campaign",
            "description": "Activate 'Bangalore Comedy Night'",
            "reason": "Event date approaching",
            "estimated_impact": "Drive 500 ticket sales",
            "payload": {"campaign_id": "camp_003"},
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_create_action_bad_platform(client):
    headers = auth(client)
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "facebook",
            "action_type": "pause_campaign",
            "description": "test",
            "reason": "test",
            "estimated_impact": "test",
        },
        headers=headers,
    )
    assert r.status_code == 400


def test_create_action_bad_action_type(client):
    headers = auth(client)
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "do_something_illegal",
            "description": "test",
            "reason": "test",
            "estimated_impact": "test",
        },
        headers=headers,
    )
    assert r.status_code == 400


def test_create_action_requires_auth(client):
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "pause_campaign",
            "description": "test",
            "reason": "test",
            "estimated_impact": "test",
        },
    )
    assert r.status_code == 403


def test_viewer_cannot_create_action(client, queue):
    headers = auth(client, "vyas", "viewer123")
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "pause_campaign",
            "description": "test",
            "reason": "test",
            "estimated_impact": "test",
            "payload": {"campaign_id": "camp_001"},
        },
        headers=headers,
    )
    # Viewer doesn't have access to create actions (they can see queue but not approve/create)
    assert r.status_code == 403


def test_tier3_action_blocked_for_non_admin(client, queue):
    headers = auth(client, "siva", "manager123")
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "delete_campaign",
            "description": "Delete campaign",
            "reason": "test",
            "estimated_impact": "test",
            "payload": {"campaign_id": "camp_001"},
        },
        headers=headers,
    )
    assert r.status_code == 403


def test_tier3_action_allowed_for_admin(client, queue):
    headers = auth(client)
    r = client.post(
        "/api/v1/actions",
        json={
            "client_id": "tickets99",
            "platform": "meta",
            "action_type": "delete_campaign",
            "description": "Delete test campaign",
            "reason": "No longer needed",
            "estimated_impact": "Free up account",
            "payload": {"campaign_id": "camp_001"},
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["tier"] == 3
