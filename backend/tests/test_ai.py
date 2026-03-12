"""Tests for Phase 5 — Claude AI layer.

All Claude API calls are mocked — zero network traffic.
Run with: pytest tests/test_ai.py -v
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from ads_engine.ai.chat import (
    ChatSession,
    _build_pending_action,
    _extract_proposed_actions,
    _strip_json_block,
)
from ads_engine.ai.analyst import analyze_performance, _parse_analysis
from ads_engine.ai.copywriter import generate_copy, _parse_copy
from ads_engine.ai.optimizer import suggest_optimizations, _parse_optimizer
from ads_engine.approval.action import ActionStatus, ActionType
from ads_engine.approval.policies import ApprovalPolicy
from ads_engine.approval.queue import init_queue
from datetime import datetime, timezone

from ads_engine.models.base import (
    AdSet,
    Campaign,
    EntityStatus,
    PerformanceMetrics,
    PerformanceReport,
    Platform,
    Targeting,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


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


_NOW = datetime(2026, 3, 12, 12, 0, 0, tzinfo=timezone.utc)


def make_report(name="Campaign A", spend=1000.0, cpc=10.0, clicks=100) -> PerformanceReport:
    return PerformanceReport(
        entity_id="camp_001",
        entity_type="campaign",
        client_id="tickets99",
        platform=Platform.META,
        date_from=_NOW,
        date_to=_NOW,
        metrics=PerformanceMetrics(
            spend=spend,
            clicks=clicks,
            impressions=10000,
            cpc=cpc,
            cpm=100.0,
            ctr=1.0,
            conversions=5,
            roas=2.0,
        ),
    )


def make_campaign(bid=1000.0) -> Campaign:
    return Campaign(
        id="camp_001",
        client_id="tickets99",
        name="Test Campaign",
        platform=Platform.META,
        status=EntityStatus.ACTIVE,
        daily_budget=bid,
        objective="CONVERSIONS",
        created_at=_NOW,
        updated_at=_NOW,
    )


def make_adset() -> AdSet:
    return AdSet(
        id="adset_001",
        campaign_id="camp_001",
        client_id="tickets99",
        name="Broad Audience",
        platform=Platform.META,
        status=EntityStatus.ACTIVE,
        daily_budget=500.0,
        targeting=Targeting(age_min=18, age_max=35),
        created_at=_NOW,
        updated_at=_NOW,
    )


# ── Mock responses ─────────────────────────────────────────────────────────────

_MOCK_CHAT_WITH_ACTION = """\
I can see that the Broad Audience ad set has a very high CPC. I recommend pausing it \
to stop wasted spend while you review the targeting.

```json
{
  "proposed_actions": [
    {
      "action_type": "PAUSE_ADSET",
      "platform": "meta",
      "description": "Pause AdSet 'Broad Audience' (ID: ads_001)",
      "reason": "CPC ₹9.50 is 3x above the ₹3.00 target",
      "estimated_impact": "Save ~₹3,000/day",
      "payload": {"adset_id": "ads_001"}
    }
  ]
}
```"""

_MOCK_CHAT_NO_ACTION = (
    "The campaigns are performing within expected ranges. No action needed right now."
)

_MOCK_ANALYSIS = {
    "summary": "Campaign A is performing well. Campaign B is underperforming with high CPC.",
    "winners": ["Campaign A — ROAS 2.0x"],
    "underperformers": ["Campaign B — CPC ₹12 vs ₹3 target"],
    "anomalies": ["Spend spike on Campaign B yesterday"],
    "recommended_actions": [
        {
            "action_type": "PAUSE_ADSET",
            "entity_id": "adset_002",
            "entity_name": "Broad Audience",
            "reason": "CPC 4x above target",
            "estimated_impact": "Save ~₹3,000/day",
        }
    ],
}

_MOCK_OPTIMIZER = {
    "rationale": "Shift budget from underperformers to winners.",
    "actions": [
        {
            "action_type": "UPDATE_BUDGET",
            "description": "Increase Campaign A budget",
            "reason": "ROAS 2x above target",
            "estimated_impact": "+₹2,000 revenue",
            "payload": {"campaign_id": "camp_001", "daily_budget": 1500},
        }
    ],
}

_MOCK_COPY = {
    "variations": [
        {
            "headline": "Book Tickets Now — Limited Seats!",
            "body": "Don't miss Chennai's biggest comedy night. Book before they sell out.",
            "cta": "Book Now",
            "tone": "urgency",
            "notes": "Urgency + scarcity drives conversions for events.",
        }
    ]
}


# ── context.py ─────────────────────────────────────────────────────────────────


def test_build_system_prompt_known_client():
    from ads_engine.ai.context import build_system_prompt
    prompt = build_system_prompt("tickets99")
    assert "Tickets99" in prompt
    assert "INR" in prompt


def test_build_system_prompt_unknown_client_no_crash():
    from ads_engine.ai.context import build_system_prompt
    prompt = build_system_prompt("no_such_client")
    assert "no_such_client" in prompt


# ── chat.py helpers ────────────────────────────────────────────────────────────


def test_extract_proposed_actions_with_block():
    actions = _extract_proposed_actions(_MOCK_CHAT_WITH_ACTION)
    assert len(actions) == 1
    assert actions[0]["action_type"] == "PAUSE_ADSET"


def test_extract_proposed_actions_no_block():
    assert _extract_proposed_actions(_MOCK_CHAT_NO_ACTION) == []


def test_strip_json_block_removes_block():
    result = _strip_json_block(_MOCK_CHAT_WITH_ACTION)
    assert "```json" not in result
    assert "PAUSE_ADSET" not in result
    assert "recommend pausing" in result


def test_strip_json_block_no_block():
    result = _strip_json_block(_MOCK_CHAT_NO_ACTION)
    assert result == _MOCK_CHAT_NO_ACTION


def test_build_pending_action_tier2():
    action = _build_pending_action(
        {
            "action_type": "PAUSE_ADSET",
            "description": "Pause adset",
            "reason": "High CPC",
            "estimated_impact": "Save money",
            "payload": {"adset_id": "123"},
        },
        client_id="tickets99",
        platform=Platform.META,
    )
    assert action.action_type == ActionType.PAUSE_ADSET
    assert action.status == ActionStatus.PENDING
    assert action.tier == 2


def test_build_pending_action_tier1():
    action = _build_pending_action(
        {"action_type": "GET_CAMPAIGNS", "description": "Get", "reason": "x", "estimated_impact": "y"},
        client_id="tickets99",
        platform=Platform.META,
    )
    assert action.tier == 1
    assert action.status == ActionStatus.APPROVED  # auto-approved


def test_build_pending_action_tier3():
    action = _build_pending_action(
        {"action_type": "DELETE_CAMPAIGN", "description": "Delete", "reason": "x", "estimated_impact": "y"},
        client_id="tickets99",
        platform=Platform.META,
    )
    assert action.tier == 3


def test_build_pending_action_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown action_type"):
        _build_pending_action(
            {"action_type": "DO_SOMETHING_WEIRD"},
            client_id="tickets99",
            platform=Platform.META,
        )


# ── ChatSession ────────────────────────────────────────────────────────────────


def test_chat_no_action():
    with patch("ads_engine.ai.chat.complete", return_value=_MOCK_CHAT_NO_ACTION):
        session = ChatSession("tickets99")
        result = session.chat("How are my campaigns?")
    assert _MOCK_CHAT_NO_ACTION in result.message
    assert result.proposed_actions == []
    assert result.queued_actions == []


def test_chat_proposes_and_queues_action(queue):
    with patch("ads_engine.ai.chat.complete", return_value=_MOCK_CHAT_WITH_ACTION):
        session = ChatSession("tickets99")
        result = session.chat("Pause underperforming ad sets", queue=queue)

    assert len(result.proposed_actions) == 1
    assert len(result.queued_actions) == 1
    assert result.queued_actions[0].action_type == ActionType.PAUSE_ADSET
    assert queue.pending_count() == 1


def test_chat_auto_queue_false_does_not_enqueue(queue):
    with patch("ads_engine.ai.chat.complete", return_value=_MOCK_CHAT_WITH_ACTION):
        session = ChatSession("tickets99")
        result = session.chat("Pause ad sets", auto_queue=False, queue=queue)

    assert len(result.proposed_actions) == 1
    assert result.queued_actions == []
    assert queue.pending_count() == 0


def test_chat_history_accumulates():
    with patch("ads_engine.ai.chat.complete", return_value=_MOCK_CHAT_NO_ACTION):
        session = ChatSession("tickets99")
        session.chat("First question")
        session.chat("Second question")
    assert len(session.history) == 4   # 2 user + 2 assistant


def test_chat_clear_resets_history():
    with patch("ads_engine.ai.chat.complete", return_value=_MOCK_CHAT_NO_ACTION):
        session = ChatSession("tickets99")
        session.chat("Hello")
        session.clear()
    assert session.history == []


def test_chat_json_block_stripped_from_message():
    with patch("ads_engine.ai.chat.complete", return_value=_MOCK_CHAT_WITH_ACTION):
        session = ChatSession("tickets99")
        result = session.chat("What should I do?")
    assert "```json" not in result.message
    assert "proposed_actions" not in result.message


# ── analyst.py ────────────────────────────────────────────────────────────────


def test_analyze_performance_parses_json():
    with patch("ads_engine.ai.analyst.complete", return_value=json.dumps(_MOCK_ANALYSIS)):
        result = analyze_performance("tickets99", Platform.META, [make_report()])
    assert result["summary"]
    assert isinstance(result["winners"], list)
    assert isinstance(result["recommended_actions"], list)
    assert result["recommended_actions"][0]["action_type"] == "PAUSE_ADSET"


def test_analyze_performance_strips_markdown_fences():
    wrapped = f"```json\n{json.dumps(_MOCK_ANALYSIS)}\n```"
    with patch("ads_engine.ai.analyst.complete", return_value=wrapped):
        result = analyze_performance("tickets99", Platform.META, [make_report()])
    assert result["summary"]


def test_analyze_performance_bad_json_fallback():
    with patch("ads_engine.ai.analyst.complete", return_value="Not JSON at all"):
        result = analyze_performance("tickets99", Platform.META, [make_report()])
    assert "summary" in result
    assert result["recommended_actions"] == []


def test_parse_analysis_plain_json():
    result = _parse_analysis(json.dumps(_MOCK_ANALYSIS))
    assert result["winners"] == _MOCK_ANALYSIS["winners"]


# ── copywriter.py ──────────────────────────────────────────────────────────────


def test_generate_copy_returns_variations():
    with patch("ads_engine.ai.copywriter.complete", return_value=json.dumps(_MOCK_COPY)):
        variations = generate_copy(
            client_id="tickets99",
            product="Comedy Night at Phoenix Mall",
            audience="18-35 urban Chennai",
        )
    assert len(variations) == 1
    assert "headline" in variations[0]
    assert "body" in variations[0]
    assert "cta" in variations[0]


def test_generate_copy_bad_json_returns_empty():
    with patch("ads_engine.ai.copywriter.complete", return_value="sorry, here is some text"):
        variations = generate_copy("tickets99", "product", "audience")
    assert variations == []


def test_parse_copy_strips_fences():
    wrapped = f"```\n{json.dumps(_MOCK_COPY)}\n```"
    result = _parse_copy(wrapped)
    assert len(result) == 1


# ── optimizer.py ───────────────────────────────────────────────────────────────


def test_suggest_optimizations_returns_pending_actions(queue):
    with patch("ads_engine.ai.optimizer.complete", return_value=json.dumps(_MOCK_OPTIMIZER)):
        actions = suggest_optimizations(
            client_id="tickets99",
            platform=Platform.META,
            campaigns=[make_campaign()],
            adsets=[make_adset()],
        )
    assert len(actions) == 1
    assert actions[0].action_type == ActionType.UPDATE_BUDGET


def test_suggest_optimizations_bad_json_returns_empty():
    with patch("ads_engine.ai.optimizer.complete", return_value="not json"):
        actions = suggest_optimizations("tickets99", Platform.META, [make_campaign()])
    assert actions == []


def test_parse_optimizer_strips_fences():
    wrapped = f"```json\n{json.dumps(_MOCK_OPTIMIZER)}\n```"
    result = _parse_optimizer(wrapped)
    assert len(result) == 1


# ── API endpoint (integration) ─────────────────────────────────────────────────


@pytest.fixture
def client(queue):
    from main import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def get_token(client) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "vishnu", "password": "admin123"})
    return resp.json()["access_token"]


def auth_headers(client) -> dict:
    return {"Authorization": f"Bearer {get_token(client)}"}


def test_ai_chat_endpoint_no_action(client):
    headers = auth_headers(client)
    with patch("ads_engine.ai.chat.complete", return_value=_MOCK_CHAT_NO_ACTION):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"client_id": "tickets99", "message": "How are my campaigns?"},
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["queued_count"] == 0
    assert _MOCK_CHAT_NO_ACTION in data["message"]


def test_ai_chat_endpoint_queues_action(client, queue):
    headers = auth_headers(client)
    with patch("ads_engine.ai.chat.complete", return_value=_MOCK_CHAT_WITH_ACTION):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"client_id": "tickets99", "message": "Pause underperformers"},
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["queued_count"] == 1
    assert data["queued_actions"][0]["action_type"] == "pause_adset"


def test_ai_chat_endpoint_bad_platform(client):
    headers = auth_headers(client)
    resp = client.post(
        "/api/v1/ai/chat",
        json={"client_id": "tickets99", "message": "Hello", "platform": "facebook"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_ai_chat_endpoint_requires_auth(client):
    resp = client.post(
        "/api/v1/ai/chat",
        json={"client_id": "tickets99", "message": "Hello"},
    )
    assert resp.status_code == 403


def test_ai_copy_endpoint(client):
    headers = auth_headers(client)
    with patch("ads_engine.ai.copywriter.complete", return_value=json.dumps(_MOCK_COPY)):
        resp = client.post(
            "/api/v1/ai/copy",
            json={
                "client_id": "tickets99",
                "product": "Comedy Night",
                "audience": "18-35 Chennai",
                "count": 1,
            },
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert "headline" in data["variations"][0]


def test_ai_copy_endpoint_invalid_count(client):
    headers = auth_headers(client)
    resp = client.post(
        "/api/v1/ai/copy",
        json={"client_id": "tickets99", "product": "x", "audience": "y", "count": 0},
        headers=headers,
    )
    assert resp.status_code == 400


def test_ai_copy_endpoint_viewer_cannot_access_wrong_client(client):
    resp_token = client.post(
        "/api/v1/auth/login", json={"username": "vyas", "password": "viewer123"}
    )
    token = resp_token.json()["access_token"]
    resp = client.post(
        "/api/v1/ai/copy",
        json={"client_id": "other_client", "product": "x", "audience": "y"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
