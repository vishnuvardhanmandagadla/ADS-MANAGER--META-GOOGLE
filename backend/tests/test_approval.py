"""Unit tests for the Phase 3 approval system.

Covers: PendingAction, ApprovalPolicy, ApprovalQueue, ActionExecutor.
Run with: pytest tests/test_approval.py -v
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from ads_engine.models.base import ActionTier, Platform, ClientConfig
from ads_engine.approval.action import ActionStatus, ActionType, PendingAction
from ads_engine.approval.policies import ApprovalPolicy, PolicyViolation
from ads_engine.approval.queue import ApprovalQueue
from ads_engine.approval.executor import ActionExecutor
from ads_engine.approval.reviewer import ActionReviewer


# ── Fixtures ───────────────────────────────────────────────────────────────────

SAFETY_CFG = {
    "spend_limits": {
        "max_daily_spend_per_client": 50000,
        "max_single_budget_change": 10000,
        "require_approval_above": 5000,
        "max_new_campaigns_per_day": 3,
    },
    "approval": {
        "cool_down_after_reject_minutes": 60,
    },
    "restrictions": {
        "never_delete_without_admin": True,
        "never_disable_safety_rules": True,
        "never_override_budget_caps": True,
    },
}


def make_policy() -> ApprovalPolicy:
    return ApprovalPolicy(SAFETY_CFG)


def make_queue(tmp_path: Path) -> ApprovalQueue:
    return ApprovalQueue(make_policy(), persist_path=tmp_path / "queue.json")


def make_tier2_action(
    action_type: ActionType = ActionType.PAUSE_ADSET,
    client_id: str = "tickets99",
    payload: dict | None = None,
) -> PendingAction:
    return PendingAction.tier2(
        client_id=client_id,
        platform=Platform.META,
        action_type=action_type,
        description="Pause AdSet 'Broad Audience'",
        reason="CPC ₹8.4, 3x above target",
        estimated_impact="Save ~₹3,000/day",
        payload=payload or {"adset_id": "ads_001"},
    )


# ── PendingAction model ────────────────────────────────────────────────────────


def test_tier1_factory_auto_approved():
    action = PendingAction.tier1(
        client_id="tickets99",
        platform=Platform.META,
        action_type=ActionType.GET_CAMPAIGNS,
        description="Fetch campaigns",
        payload={},
    )
    assert action.tier == ActionTier.AUTO
    assert action.status == ActionStatus.APPROVED
    assert action.reviewed_by == "system"


def test_tier2_factory_pending():
    action = make_tier2_action()
    assert action.tier == ActionTier.APPROVE
    assert action.status == ActionStatus.PENDING
    assert action.reviewed_by is None


def test_tier3_factory_pending():
    action = PendingAction.tier3(
        client_id="tickets99",
        platform=Platform.META,
        action_type=ActionType.DELETE_CAMPAIGN,
        description="Delete campaign",
        reason="Client request",
        estimated_impact="Permanent",
        payload={"campaign_id": "cam_001"},
    )
    assert action.tier == ActionTier.RESTRICTED
    assert action.status == ActionStatus.PENDING


def test_action_approve_transition():
    action = make_tier2_action()
    action.approve("vishnu")
    assert action.status == ActionStatus.APPROVED
    assert action.reviewed_by == "vishnu"
    assert action.reviewed_at is not None


def test_action_reject_transition():
    action = make_tier2_action()
    action.reject("vishnu", "Not the right time")
    assert action.status == ActionStatus.REJECTED
    assert action.rejection_reason == "Not the right time"


def test_action_cannot_approve_twice():
    action = make_tier2_action()
    action.approve("vishnu")
    with pytest.raises(ValueError, match="Cannot approve"):
        action.approve("vishnu")


def test_action_cannot_reject_after_approve():
    action = make_tier2_action()
    action.approve("vishnu")
    with pytest.raises(ValueError, match="Cannot reject"):
        action.reject("vishnu")


def test_action_mark_executed():
    action = make_tier2_action()
    action.approve("vishnu")
    action.mark_executed()
    assert action.status == ActionStatus.EXECUTED
    assert action.executed_at is not None
    assert action.is_terminal


def test_action_mark_failed():
    action = make_tier2_action()
    action.approve("vishnu")
    action.mark_failed("API timeout")
    assert action.status == ActionStatus.FAILED
    assert action.execution_error == "API timeout"
    assert action.is_terminal


def test_action_is_expired():
    action = make_tier2_action()
    action.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    assert action.is_expired is True


def test_action_not_expired_when_approved():
    action = make_tier2_action()
    action.approve("vishnu")
    action.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    assert action.is_expired is False  # non-PENDING never expires


# ── ApprovalPolicy ─────────────────────────────────────────────────────────────


def test_policy_classify_tier1():
    assert ApprovalPolicy.classify(ActionType.GET_CAMPAIGNS) == ActionTier.AUTO
    assert ApprovalPolicy.classify(ActionType.GET_PERFORMANCE) == ActionTier.AUTO


def test_policy_classify_tier2():
    assert ApprovalPolicy.classify(ActionType.CREATE_CAMPAIGN) == ActionTier.APPROVE
    assert ApprovalPolicy.classify(ActionType.UPDATE_BUDGET) == ActionTier.APPROVE
    assert ApprovalPolicy.classify(ActionType.PAUSE_ADSET) == ActionTier.APPROVE


def test_policy_classify_tier3():
    assert ApprovalPolicy.classify(ActionType.DELETE_CAMPAIGN) == ActionTier.RESTRICTED
    assert ApprovalPolicy.classify(ActionType.DISABLE_SAFETY_RULE) == ActionTier.RESTRICTED


def test_policy_blocks_excessive_budget():
    policy = make_policy()
    action = make_tier2_action(
        action_type=ActionType.CREATE_CAMPAIGN,
        payload={"name": "Test", "objective": "LINK_CLICKS", "daily_budget": 60000},
    )
    with pytest.raises(PolicyViolation, match="exceeds max daily spend"):
        policy.check(action, [])


def test_policy_blocks_large_budget_change():
    policy = make_policy()
    action = make_tier2_action(
        action_type=ActionType.UPDATE_BUDGET,
        payload={"campaign_id": "cam_001", "old_budget": 5000, "new_daily_budget": 20000},
    )
    with pytest.raises(PolicyViolation, match="exceeds single-change limit"):
        policy.check(action, [])


def test_policy_allows_normal_budget():
    policy = make_policy()
    action = make_tier2_action(
        action_type=ActionType.UPDATE_BUDGET,
        payload={"campaign_id": "cam_001", "old_budget": 5000, "new_daily_budget": 8000},
    )
    policy.check(action, [])  # Should not raise


def test_policy_blocks_too_many_campaigns():
    policy = make_policy()

    # Simulate 3 approved campaign creations today
    history = []
    for _ in range(3):
        a = PendingAction.tier2(
            client_id="tickets99",
            platform=Platform.META,
            action_type=ActionType.CREATE_CAMPAIGN,
            description="Old campaign",
            reason="test",
            estimated_impact="none",
            payload={"daily_budget": 1000},
        )
        a.approve("vishnu")
        history.append(a)

    new_action = make_tier2_action(
        action_type=ActionType.CREATE_CAMPAIGN,
        payload={"name": "New Campaign", "daily_budget": 1000},
    )
    with pytest.raises(PolicyViolation, match="Daily limit"):
        policy.check(new_action, history)


def test_policy_cooldown_after_reject():
    policy = make_policy()
    action = make_tier2_action()
    policy.record_rejection(action)

    new_action = make_tier2_action()
    with pytest.raises(PolicyViolation, match="Cool-down"):
        policy.check(new_action, [])


def test_policy_cooldown_clears():
    policy = make_policy()
    action = make_tier2_action()
    policy.record_rejection(action)
    policy.clear_cooldown("tickets99", ActionType.PAUSE_ADSET)

    new_action = make_tier2_action()
    policy.check(new_action, [])  # Should not raise


def test_policy_blocks_disable_safety_rule():
    policy = make_policy()
    action = PendingAction.tier3(
        client_id="tickets99",
        platform=Platform.META,
        action_type=ActionType.DISABLE_SAFETY_RULE,
        description="Disable rule",
        reason="test",
        estimated_impact="bad",
        payload={},
    )
    with pytest.raises(PolicyViolation, match="Safety rules cannot be disabled"):
        policy.check(action, [])


def test_policy_requires_approval_tier2():
    policy = make_policy()
    action = make_tier2_action()
    assert policy.requires_approval(action) is True


def test_policy_no_approval_tier1():
    policy = make_policy()
    action = PendingAction.tier1(
        client_id="tickets99",
        platform=Platform.META,
        action_type=ActionType.GET_CAMPAIGNS,
        description="Fetch",
        payload={},
    )
    assert policy.requires_approval(action) is False


# ── ApprovalQueue ──────────────────────────────────────────────────────────────


def test_queue_enqueue_and_get(tmp_path):
    queue = make_queue(tmp_path)
    action = make_tier2_action()
    queue.enqueue(action)
    retrieved = queue.get(action.id)
    assert retrieved is not None
    assert retrieved.id == action.id


def test_queue_list_pending(tmp_path):
    queue = make_queue(tmp_path)
    a1 = make_tier2_action()
    a2 = make_tier2_action()
    queue.enqueue(a1)
    queue.enqueue(a2)
    pending = queue.list_pending()
    assert len(pending) == 2


def test_queue_approve(tmp_path):
    queue = make_queue(tmp_path)
    action = make_tier2_action()
    queue.enqueue(action)
    approved = queue.approve(action.id, "vishnu")
    assert approved.status == ActionStatus.APPROVED
    assert approved.reviewed_by == "vishnu"
    assert len(queue.list_pending()) == 0


def test_queue_reject(tmp_path):
    queue = make_queue(tmp_path)
    action = make_tier2_action()
    queue.enqueue(action)
    rejected = queue.reject(action.id, "vishnu", "Budget too high")
    assert rejected.status == ActionStatus.REJECTED
    assert rejected.rejection_reason == "Budget too high"


def test_queue_mark_executed(tmp_path):
    queue = make_queue(tmp_path)
    action = make_tier2_action()
    queue.enqueue(action)
    queue.approve(action.id, "vishnu")
    done = queue.mark_executed(action.id)
    assert done.status == ActionStatus.EXECUTED


def test_queue_mark_failed(tmp_path):
    queue = make_queue(tmp_path)
    action = make_tier2_action()
    queue.enqueue(action)
    queue.approve(action.id, "vishnu")
    failed = queue.mark_failed(action.id, "API timeout")
    assert failed.status == ActionStatus.FAILED
    assert failed.execution_error == "API timeout"


def test_queue_cancel(tmp_path):
    queue = make_queue(tmp_path)
    action = make_tier2_action()
    queue.enqueue(action)
    cancelled = queue.cancel(action.id)
    assert cancelled.status == ActionStatus.CANCELLED


def test_queue_cannot_cancel_approved(tmp_path):
    queue = make_queue(tmp_path)
    action = make_tier2_action()
    queue.enqueue(action)
    queue.approve(action.id, "vishnu")
    with pytest.raises(ValueError, match="PENDING"):
        queue.cancel(action.id)


def test_queue_expire_old(tmp_path):
    queue = make_queue(tmp_path)
    action = make_tier2_action()
    action.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    queue._actions[action.id] = action  # bypass policy for this test
    expired_count = queue.expire_old()
    assert expired_count == 1
    assert queue.get(action.id).status == ActionStatus.EXPIRED


def test_queue_filters_by_client(tmp_path):
    queue = make_queue(tmp_path)
    a1 = make_tier2_action(client_id="tickets99")
    a2 = make_tier2_action(client_id="client_b")
    queue.enqueue(a1)
    queue.enqueue(a2)
    t99 = queue.list_pending(client_id="tickets99")
    assert len(t99) == 1
    assert t99[0].client_id == "tickets99"


def test_queue_blocks_policy_violation(tmp_path):
    queue = make_queue(tmp_path)
    action = make_tier2_action(
        action_type=ActionType.CREATE_CAMPAIGN,
        payload={"name": "X", "objective": "LINK_CLICKS", "daily_budget": 999999},
    )
    with pytest.raises(PolicyViolation):
        queue.enqueue(action)


def test_queue_raises_on_unknown_action(tmp_path):
    queue = make_queue(tmp_path)
    with pytest.raises(KeyError):
        queue.approve("nonexistent-id", "vishnu")


def test_queue_pending_count(tmp_path):
    queue = make_queue(tmp_path)
    assert queue.pending_count() == 0
    queue.enqueue(make_tier2_action())
    queue.enqueue(make_tier2_action())
    assert queue.pending_count() == 2


def test_queue_persistence(tmp_path):
    """Actions should survive a queue restart (file persistence)."""
    persist_file = tmp_path / "queue.json"
    q1 = ApprovalQueue(make_policy(), persist_path=persist_file)
    action = make_tier2_action()
    q1.enqueue(action)

    # Create new queue instance pointing to same file
    q2 = ApprovalQueue(make_policy(), persist_path=persist_file)
    loaded = q2.get(action.id)
    assert loaded is not None
    assert loaded.description == action.description


# ── ActionExecutor ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_executor_dispatches_pause_adset(tmp_path):
    queue = make_queue(tmp_path)
    executor = ActionExecutor(queue)

    mock_adapter = MagicMock()
    mock_adapter.platform = Platform.META
    mock_adapter.set_adset_status = AsyncMock(return_value=MagicMock(id="ads_001"))
    executor.register_adapter("tickets99", mock_adapter)

    action = make_tier2_action(
        action_type=ActionType.PAUSE_ADSET,
        payload={"adset_id": "ads_001"},
    )
    queue.enqueue(action)
    queue.approve(action.id, "vishnu")

    result = await executor.run(action.id)

    mock_adapter.set_adset_status.assert_called_once()
    assert queue.get(action.id).status == ActionStatus.EXECUTED


@pytest.mark.asyncio
async def test_executor_dispatches_update_budget(tmp_path):
    queue = make_queue(tmp_path)
    executor = ActionExecutor(queue)

    mock_adapter = MagicMock()
    mock_adapter.platform = Platform.META
    mock_adapter.update_campaign_budget = AsyncMock(return_value=MagicMock())
    executor.register_adapter("tickets99", mock_adapter)

    action = PendingAction.tier2(
        client_id="tickets99",
        platform=Platform.META,
        action_type=ActionType.UPDATE_BUDGET,
        description="Increase budget",
        reason="Good performance",
        estimated_impact="+₹500/day spend",
        payload={"campaign_id": "cam_001", "old_budget": 2000, "new_daily_budget": 3000},
    )
    queue.enqueue(action)
    queue.approve(action.id, "vishnu")
    await executor.run(action.id)

    mock_adapter.update_campaign_budget.assert_called_once_with(
        campaign_id="cam_001", new_daily_budget=3000.0
    )


@pytest.mark.asyncio
async def test_executor_rejects_unapproved(tmp_path):
    queue = make_queue(tmp_path)
    executor = ActionExecutor(queue)

    action = make_tier2_action()
    queue.enqueue(action)
    # Do NOT approve

    with pytest.raises(ValueError, match="not APPROVED"):
        await executor.run(action.id)


@pytest.mark.asyncio
async def test_executor_marks_failed_on_error(tmp_path):
    queue = make_queue(tmp_path)
    executor = ActionExecutor(queue)

    mock_adapter = MagicMock()
    mock_adapter.platform = Platform.META
    mock_adapter.set_adset_status = AsyncMock(side_effect=RuntimeError("API exploded"))
    executor.register_adapter("tickets99", mock_adapter)

    action = make_tier2_action(payload={"adset_id": "ads_001"})
    queue.enqueue(action)
    queue.approve(action.id, "vishnu")

    with pytest.raises(RuntimeError, match="API exploded"):
        await executor.run(action.id)

    assert queue.get(action.id).status == ActionStatus.FAILED
    assert "API exploded" in queue.get(action.id).execution_error


@pytest.mark.asyncio
async def test_executor_raises_without_adapter(tmp_path):
    queue = make_queue(tmp_path)
    executor = ActionExecutor(queue)

    action = make_tier2_action()
    queue.enqueue(action)
    queue.approve(action.id, "vishnu")

    with pytest.raises(RuntimeError, match="No adapter registered"):
        await executor.run(action.id)


# ── ActionReviewer ─────────────────────────────────────────────────────────────


def test_reviewer_formats_whatsapp_message():
    reviewer = ActionReviewer(admin_whatsapp="+91999999999")
    action = make_tier2_action()
    msg = reviewer.format_whatsapp_message(action)
    assert "Needs Your Approval" in msg
    assert action.description in msg
    assert action.reason in msg
    assert action.id[:8] in msg


def test_reviewer_formats_dashboard_card():
    reviewer = ActionReviewer()
    action = make_tier2_action()
    card = reviewer.format_dashboard_card(action)
    assert card["id"] == action.id
    assert card["status"] == ActionStatus.PENDING
    assert card["status_emoji"] == "🟡"
    assert card["client_id"] == "tickets99"


@pytest.mark.asyncio
async def test_reviewer_skips_tier1():
    reviewer = ActionReviewer()
    action = PendingAction.tier1(
        client_id="tickets99",
        platform=Platform.META,
        action_type=ActionType.GET_CAMPAIGNS,
        description="Fetch campaigns",
        payload={},
    )
    # Should complete silently (no notification for Tier 1)
    await reviewer.notify(action)
