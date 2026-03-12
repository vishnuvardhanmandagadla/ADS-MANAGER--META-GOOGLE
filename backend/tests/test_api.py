"""Tests for Phase 4 — FastAPI endpoints + WebSocket.

Uses FastAPI's TestClient (synchronous) for REST endpoints.
Run with: pytest tests/test_api.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ads_engine.approval.action import ActionType, PendingAction
from ads_engine.approval.policies import ApprovalPolicy
from ads_engine.approval.queue import ApprovalQueue, init_queue
from ads_engine.models.base import Platform


# ── App fixture ────────────────────────────────────────────────────────────────


@pytest.fixture
def queue(tmp_path) -> ApprovalQueue:
    """Fresh queue backed by a temp file."""
    from ads_engine.approval.queue import init_queue
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
    policy = ApprovalPolicy(safety)
    return init_queue(policy, persist_path=tmp_path / "queue.json")


@pytest.fixture
def client(queue):
    """TestClient with queue pre-initialised."""
    from main import create_app
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Auth helpers ───────────────────────────────────────────────────────────────


def get_token(client, username="vishnu", password="admin123") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(client, username="vishnu", password="admin123") -> dict:
    return {"Authorization": f"Bearer {get_token(client, username, password)}"}


# ── Health ─────────────────────────────────────────────────────────────────────


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Auth endpoints ─────────────────────────────────────────────────────────────


def test_login_success(client):
    resp = client.post("/api/v1/auth/login", json={"username": "vishnu", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["username"] == "vishnu"
    assert data["role"] == "admin"


def test_login_wrong_password(client):
    resp = client.post("/api/v1/auth/login", json={"username": "vishnu", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "pass"})
    assert resp.status_code == 401


def test_me_endpoint(client):
    headers = auth(client)
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "vishnu"
    assert resp.json()["role"] == "admin"


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 403


def test_me_invalid_token(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_manager_login(client):
    resp = client.post("/api/v1/auth/login", json={"username": "siva", "password": "manager123"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "manager"


def test_viewer_login(client):
    resp = client.post("/api/v1/auth/login", json={"username": "vyas", "password": "viewer123"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "viewer"


# ── Clients endpoints ──────────────────────────────────────────────────────────


def test_list_clients_admin(client):
    headers = auth(client)
    resp = client.get("/api/v1/clients", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # tickets99 should be in there (it has a YAML config)
    ids = [c["client_id"] for c in data]
    assert "tickets99" in ids


def test_list_clients_requires_auth(client):
    resp = client.get("/api/v1/clients")
    assert resp.status_code == 403


def test_get_client_by_id(client):
    headers = auth(client)
    resp = client.get("/api/v1/clients/tickets99", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_id"] == "tickets99"
    assert data["name"] == "Tickets99"
    assert data["currency"] == "INR"


def test_get_client_not_found(client):
    headers = auth(client)
    resp = client.get("/api/v1/clients/nonexistent", headers=headers)
    assert resp.status_code == 404


def test_manager_cannot_access_other_client(client):
    headers = auth(client, "siva", "manager123")
    # siva only has access to tickets99 — try a fake client
    resp = client.get("/api/v1/clients/other_client", headers=headers)
    assert resp.status_code == 403


# ── Approvals endpoints ────────────────────────────────────────────────────────


def make_action(client_id="tickets99") -> PendingAction:
    return PendingAction.tier2(
        client_id=client_id,
        platform=Platform.META,
        action_type=ActionType.PAUSE_ADSET,
        description="Pause AdSet 'Broad Audience'",
        reason="CPC 3x above target",
        estimated_impact="Save ~₹3,000/day",
        payload={"adset_id": "ads_001"},
    )


def test_list_pending_empty(client):
    headers = auth(client)
    resp = client.get("/api/v1/approvals", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["pending_count"] == 0
    assert resp.json()["actions"] == []


def test_list_pending_with_action(client, queue):
    action = make_action()
    queue.enqueue(action)
    headers = auth(client)
    resp = client.get("/api/v1/approvals", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_count"] == 1
    assert data["actions"][0]["id"] == action.id
    assert data["actions"][0]["status"] == "pending"
    assert data["actions"][0]["status_emoji"] == "🟡"


def test_get_single_action(client, queue):
    action = make_action()
    queue.enqueue(action)
    headers = auth(client)
    resp = client.get(f"/api/v1/approvals/{action.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == action.id


def test_get_nonexistent_action(client):
    headers = auth(client)
    resp = client.get("/api/v1/approvals/does-not-exist", headers=headers)
    assert resp.status_code == 404


def test_approve_action(client, queue):
    action = make_action()
    queue.enqueue(action)
    headers = auth(client)
    resp = client.post(
        f"/api/v1/approvals/{action.id}/approve",
        json={"reviewer": "vishnu"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["reviewed_by"] == "vishnu"


def test_reject_action(client, queue):
    action = make_action()
    queue.enqueue(action)
    headers = auth(client)
    resp = client.post(
        f"/api/v1/approvals/{action.id}/reject",
        json={"reviewer": "vishnu", "reason": "Not the right time"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "Not the right time"


def test_cancel_action(client, queue):
    action = make_action()
    queue.enqueue(action)
    headers = auth(client)
    resp = client.post(f"/api/v1/approvals/{action.id}/cancel", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_viewer_cannot_approve(client, queue):
    action = make_action()
    queue.enqueue(action)
    headers = auth(client, "vyas", "viewer123")
    resp = client.post(
        f"/api/v1/approvals/{action.id}/approve",
        json={"reviewer": "vyas"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_approve_already_approved_fails(client, queue):
    action = make_action()
    queue.enqueue(action)
    queue.approve(action.id, "vishnu")
    headers = auth(client)
    resp = client.post(
        f"/api/v1/approvals/{action.id}/approve",
        json={"reviewer": "vishnu"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_list_all_with_status_filter(client, queue):
    a1 = make_action()
    a2 = make_action()
    queue.enqueue(a1)
    queue.enqueue(a2)
    queue.approve(a1.id, "vishnu")

    headers = auth(client)
    resp = client.get("/api/v1/approvals/all?status=approved", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all(a["status"] == "approved" for a in data["actions"])


def test_list_all_invalid_status(client):
    headers = auth(client)
    resp = client.get("/api/v1/approvals/all?status=invalid", headers=headers)
    assert resp.status_code == 400


def test_manager_sees_only_own_client(client, queue):
    # Enqueue action for tickets99 and a fake other client
    t99 = make_action("tickets99")
    other = PendingAction.tier2(
        client_id="other_client",
        platform=Platform.META,
        action_type=ActionType.PAUSE_ADSET,
        description="Other",
        reason="test",
        estimated_impact="none",
        payload={"adset_id": "x"},
    )
    queue.enqueue(t99)
    queue._actions[other.id] = other  # bypass policy to add other client

    headers = auth(client, "siva", "manager123")
    resp = client.get("/api/v1/approvals", headers=headers)
    assert resp.status_code == 200
    ids = [a["client_id"] for a in resp.json()["actions"]]
    assert all(cid == "tickets99" for cid in ids)
    assert "other_client" not in ids


# ── WebSocket ──────────────────────────────────────────────────────────────────


def test_websocket_connect(client):
    with client.websocket_connect("/ws") as ws:
        data = json.loads(ws.receive_text())
        assert data["event"] == "connected"
        assert "connections" in data["data"]


def test_websocket_ping_pong(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()   # consume welcome message
        ws.send_text("ping")
        data = json.loads(ws.receive_text())
        assert data["event"] == "pong"
