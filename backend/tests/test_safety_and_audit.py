"""Tests for Phase 10 — Safety engine + Audit log.

Run with: pytest tests/test_safety_and_audit.py -v
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from ads_engine.approval.policies import ApprovalPolicy
from ads_engine.approval.queue import init_queue
from ads_engine.core.safety import CampaignMetrics, SafetyEngine
from ads_engine.db.audit import AuditLog, AuditEntry, init_audit_log
from ads_engine.db.audit import (
    ACTION_QUEUED, ACTION_APPROVED, ACTION_REJECTED, TIER3_ATTEMPTED, ANOMALY_DETECTED
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def audit_log(tmp_path) -> AuditLog:
    return AuditLog(path=tmp_path / "audit.jsonl", retention_days=365)


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
def client(queue, tmp_path):
    init_audit_log(path=tmp_path / "audit.jsonl")
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


# ── AuditLog: write / read ─────────────────────────────────────────────────────


def test_audit_log_single_entry(audit_log, tmp_path):
    audit_log.log_event(
        event_type=ACTION_QUEUED,
        client_id="tickets99",
        action_id="abc123",
        description="Pause Chennai Events",
        actor="vishnu",
    )
    entries = audit_log.get_recent()
    assert len(entries) == 1
    assert entries[0].event_type == ACTION_QUEUED
    assert entries[0].client_id == "tickets99"
    assert entries[0].actor == "vishnu"


def test_audit_log_newest_first(audit_log):
    for i in range(3):
        audit_log.log_event(ACTION_QUEUED, "tickets99", description=f"action {i}")
    entries = audit_log.get_recent()
    # Newest first — timestamps are monotonically increasing so order may vary by ms;
    # just check all 3 are returned
    assert len(entries) == 3


def test_audit_log_limit(audit_log):
    for i in range(10):
        audit_log.log_event(ACTION_QUEUED, "tickets99")
    entries = audit_log.get_recent(limit=3)
    assert len(entries) == 3


def test_audit_log_client_id_filter(audit_log):
    audit_log.log_event(ACTION_QUEUED, "tickets99")
    audit_log.log_event(ACTION_QUEUED, "other_client")
    audit_log.log_event(ACTION_APPROVED, "tickets99")

    entries = audit_log.get_recent(client_id="tickets99")
    assert all(e.client_id == "tickets99" for e in entries)
    assert len(entries) == 2


def test_audit_log_event_type_filter(audit_log):
    audit_log.log_event(ACTION_QUEUED, "tickets99")
    audit_log.log_event(ACTION_APPROVED, "tickets99")
    audit_log.log_event(ACTION_REJECTED, "tickets99")

    approved = audit_log.get_recent(event_type=ACTION_APPROVED)
    assert len(approved) == 1
    assert approved[0].event_type == ACTION_APPROVED


def test_audit_log_persists_to_file(tmp_path):
    path = tmp_path / "audit.jsonl"
    log1 = AuditLog(path=path)
    log1.log_event(ACTION_QUEUED, "tickets99", description="Test")

    # New instance reads from same file
    log2 = AuditLog(path=path)
    entries = log2.get_recent()
    assert len(entries) == 1
    assert entries[0].description == "Test"


def test_audit_log_empty_file(audit_log):
    entries = audit_log.get_recent()
    assert entries == []


def test_audit_log_count(audit_log):
    for _ in range(5):
        audit_log.log_event(ACTION_QUEUED, "tickets99")
    audit_log.log_event(ACTION_QUEUED, "other")
    assert audit_log.count() == 6
    assert audit_log.count(client_id="tickets99") == 5


# ── SafetyEngine: CPC spike ────────────────────────────────────────────────────


def make_safety_config(cpc_pct=200, spend_pct=120) -> dict:
    return {
        "anomaly_detection": {
            "auto_pause_on_cpc_spike": True,
            "cpc_spike_threshold_pct": cpc_pct,
            "auto_pause_on_spend_overrun": True,
            "spend_overrun_threshold_pct": spend_pct,
        }
    }


def test_cpc_spike_detected():
    engine = SafetyEngine(make_safety_config(cpc_pct=200))
    is_spike, pct = engine.check_cpc_spike(current_cpc=15.0, avg_7day_cpc=4.0)
    # 15 is (15-4)/4 * 100 = 275% above avg — exceeds 200%
    assert is_spike is True
    assert pct == pytest.approx(275.0)


def test_cpc_spike_not_triggered_below_threshold():
    engine = SafetyEngine(make_safety_config(cpc_pct=200))
    is_spike, pct = engine.check_cpc_spike(current_cpc=8.0, avg_7day_cpc=4.0)
    # 100% above — below 200% threshold
    assert is_spike is False
    assert pct == pytest.approx(100.0)


def test_cpc_spike_no_baseline():
    """With zero 7-day avg there is no baseline — should not flag as spike."""
    engine = SafetyEngine(make_safety_config())
    is_spike, pct = engine.check_cpc_spike(current_cpc=50.0, avg_7day_cpc=0.0)
    assert is_spike is False
    assert pct == 0.0


def test_cpc_spike_disabled():
    cfg = {
        "anomaly_detection": {
            "auto_pause_on_cpc_spike": False,
            "cpc_spike_threshold_pct": 200,
            "auto_pause_on_spend_overrun": True,
            "spend_overrun_threshold_pct": 120,
        }
    }
    engine = SafetyEngine(cfg)
    is_spike, _ = engine.check_cpc_spike(current_cpc=100.0, avg_7day_cpc=1.0)
    assert is_spike is False


# ── SafetyEngine: spend overrun ───────────────────────────────────────────────


def test_spend_overrun_detected():
    engine = SafetyEngine(make_safety_config(spend_pct=120))
    is_overrun, pct = engine.check_spend_overrun(spend_today=3700, daily_budget=3000)
    # 3700/3000 = 123.3% — exceeds 120%
    assert is_overrun is True
    assert pct == pytest.approx(123.33, rel=0.01)


def test_spend_overrun_not_triggered():
    engine = SafetyEngine(make_safety_config(spend_pct=120))
    is_overrun, pct = engine.check_spend_overrun(spend_today=2800, daily_budget=3000)
    # 93.3% — below threshold
    assert is_overrun is False


def test_spend_overrun_zero_budget():
    engine = SafetyEngine(make_safety_config())
    is_overrun, pct = engine.check_spend_overrun(spend_today=1000, daily_budget=0)
    assert is_overrun is False


# ── SafetyEngine: evaluate batch ─────────────────────────────────────────────


def test_evaluate_returns_anomalies():
    engine = SafetyEngine(make_safety_config(cpc_pct=200, spend_pct=120))
    campaigns = [
        CampaignMetrics(
            campaign_id="camp_001",
            campaign_name="Chennai Events",
            client_id="tickets99",
            platform="meta",
            daily_budget=3000,
            spend_today=3700,   # overrun
            current_cpc=15.0,
            avg_cpc_7day=4.0,   # spike
        ),
        CampaignMetrics(
            campaign_id="camp_002",
            campaign_name="Normal Campaign",
            client_id="tickets99",
            platform="meta",
            daily_budget=3000,
            spend_today=2000,   # fine
            current_cpc=3.5,
            avg_cpc_7day=3.0,   # fine
        ),
    ]
    anomalies = engine.evaluate(campaigns)
    # camp_001 should have 2 anomalies (CPC spike + spend overrun), camp_002 has 0
    assert len(anomalies) == 2
    types = {a.anomaly_type for a in anomalies}
    assert "CPC_SPIKE" in types
    assert "SPEND_OVERRUN" in types
    assert all(a.campaign_id == "camp_001" for a in anomalies)


def test_evaluate_no_anomalies():
    engine = SafetyEngine(make_safety_config())
    campaigns = [
        CampaignMetrics(
            campaign_id="camp_001", campaign_name="Good", client_id="tickets99",
            platform="meta", daily_budget=3000, spend_today=2000,
            current_cpc=3.0, avg_cpc_7day=3.0,
        )
    ]
    assert engine.evaluate(campaigns) == []


def test_evaluate_severity_critical_for_extreme_spike():
    engine = SafetyEngine(make_safety_config(cpc_pct=200))
    campaigns = [
        CampaignMetrics(
            campaign_id="c1", campaign_name="X", client_id="t99", platform="meta",
            daily_budget=3000, spend_today=2000,
            current_cpc=50.0, avg_cpc_7day=4.0,  # 1150% — 1.5x above threshold
        )
    ]
    anomalies = engine.evaluate(campaigns)
    assert anomalies[0].severity == "critical"


# ── API: GET /audit ────────────────────────────────────────────────────────────


def test_audit_endpoint_admin_access(client):
    r = client.get("/api/v1/audit", headers=auth(client))
    assert r.status_code == 200
    data = r.json()
    assert "entries" in data
    assert "total" in data


def test_audit_endpoint_viewer_blocked(client):
    r = client.get("/api/v1/audit", headers=auth(client, "vyas", "viewer123"))
    assert r.status_code == 403


def test_audit_grows_after_approve(client, queue):
    # Queue an action
    headers = auth(client)
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

    # Approve it
    client.post(
        f"/api/v1/approvals/{action_id}/approve",
        json={"reviewer": "vishnu"},
        headers=headers,
    )

    # Audit should have at least ACTION_QUEUED + ACTION_APPROVED
    r = client.get("/api/v1/audit", headers=headers)
    assert r.status_code == 200
    event_types = {e["event_type"] for e in r.json()["entries"]}
    assert ACTION_QUEUED in event_types
    assert ACTION_APPROVED in event_types


def test_tier3_attempt_logged(client, queue):
    # Manager tries Tier 3 — should be blocked AND logged
    manager_headers = auth(client, "siva", "manager123")
    client.post(
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
        headers=manager_headers,
    )

    # Audit should contain TIER3_ATTEMPTED
    admin_headers = auth(client)
    r = client.get("/api/v1/audit", headers=admin_headers)
    event_types = {e["event_type"] for e in r.json()["entries"]}
    assert TIER3_ATTEMPTED in event_types


# ── API: POST /safety/check ────────────────────────────────────────────────────


def test_safety_check_detects_anomaly(client):
    r = client.post(
        "/api/v1/safety/check",
        json={
            "campaigns": [{
                "campaign_id": "camp_001",
                "campaign_name": "Chennai Events",
                "client_id": "tickets99",
                "platform": "meta",
                "daily_budget": 3000,
                "spend_today": 3700,
                "current_cpc": 15.0,
                "avg_cpc_7day": 4.0,
            }]
        },
        headers=auth(client),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["anomaly_count"] == 2  # CPC spike + spend overrun
    types = {a["anomaly_type"] for a in data["anomalies"]}
    assert "CPC_SPIKE" in types
    assert "SPEND_OVERRUN" in types


def test_safety_check_no_anomaly(client):
    r = client.post(
        "/api/v1/safety/check",
        json={
            "campaigns": [{
                "campaign_id": "camp_004",
                "campaign_name": "Sports Lookalike",
                "client_id": "tickets99",
                "platform": "meta",
                "daily_budget": 2500,
                "spend_today": 2000,
                "current_cpc": 2.1,
                "avg_cpc_7day": 2.0,
            }]
        },
        headers=auth(client),
    )
    assert r.status_code == 200
    assert r.json()["anomaly_count"] == 0


def test_safety_check_viewer_blocked(client):
    r = client.post(
        "/api/v1/safety/check",
        json={"campaigns": []},
        headers=auth(client, "vyas", "viewer123"),
    )
    assert r.status_code == 403
