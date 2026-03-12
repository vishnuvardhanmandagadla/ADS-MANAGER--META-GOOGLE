"""PendingAction — the single model that every spend-affecting action flows through.

Every time the AI or any code wants to touch an ad platform, it creates a
PendingAction and drops it in the queue. Nothing executes until a human
approves it (for Tier 2/3). Tier 1 actions pass straight through.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ..models.base import ActionTier, Platform


# ── Enums ──────────────────────────────────────────────────────────────────────


class ActionStatus(str, Enum):
    PENDING = "pending"       # Waiting for human review
    APPROVED = "approved"     # Human said ✅, ready to execute
    REJECTED = "rejected"     # Human said ❌, will not execute
    EXECUTED = "executed"     # Successfully ran on the platform
    FAILED = "failed"         # Approved but execution threw an error
    EXPIRED = "expired"       # No response within expiry window
    CANCELLED = "cancelled"   # Withdrawn before review


class ActionType(str, Enum):
    # ── Tier 1 — auto (read-only, no approval needed) ──────────────────────
    GET_CAMPAIGNS = "get_campaigns"
    GET_ADSETS = "get_adsets"
    GET_ADS = "get_ads"
    GET_PERFORMANCE = "get_performance"

    # ── Tier 2 — require human approval ────────────────────────────────────
    CREATE_CAMPAIGN = "create_campaign"
    CREATE_ADSET = "create_adset"
    CREATE_AD = "create_ad"
    UPDATE_BUDGET = "update_budget"
    PAUSE_CAMPAIGN = "pause_campaign"
    ACTIVATE_CAMPAIGN = "activate_campaign"
    PAUSE_ADSET = "pause_adset"
    ACTIVATE_ADSET = "activate_adset"
    UPDATE_TARGETING = "update_targeting"
    DUPLICATE_CAMPAIGN = "duplicate_campaign"

    # ── Tier 3 — admin only ─────────────────────────────────────────────────
    DELETE_CAMPAIGN = "delete_campaign"
    REMOVE_CLIENT = "remove_client"
    OVERRIDE_BUDGET_CAP = "override_budget_cap"
    DISABLE_SAFETY_RULE = "disable_safety_rule"


# ── Default expiry window (from safety.yaml approval.expiry) ──────────────────

DEFAULT_EXPIRY_HOURS = 24


# ── Model ─────────────────────────────────────────────────────────────────────


class PendingAction(BaseModel):
    """One unit of work that must pass through the approval gate."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    client_id: str
    platform: Platform
    tier: ActionTier
    action_type: ActionType

    # Human-readable fields (shown in the approval UI and WhatsApp message)
    description: str        # "Pause AdSet 'Broad Audience'"
    reason: str             # "CPC ₹8.4, 3x above target"
    estimated_impact: str   # "Save ~₹3,000/day"

    # The actual parameters that will be passed to the platform adapter
    payload: dict[str, Any]

    # Lifecycle
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=DEFAULT_EXPIRY_HOURS)
    )

    # Review tracking
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    # Execution tracking
    executed_at: Optional[datetime] = None
    execution_error: Optional[str] = None

    # ── Derived properties ─────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        return self.status == ActionStatus.PENDING and datetime.utcnow() > self.expires_at

    @property
    def is_terminal(self) -> bool:
        """True if no further state transitions are possible."""
        return self.status in (
            ActionStatus.EXECUTED,
            ActionStatus.REJECTED,
            ActionStatus.FAILED,
            ActionStatus.EXPIRED,
            ActionStatus.CANCELLED,
        )

    @property
    def age_minutes(self) -> float:
        return (datetime.utcnow() - self.created_at).total_seconds() / 60

    # ── Transition helpers ─────────────────────────────────────────────────

    def approve(self, reviewer: str) -> None:
        if self.status != ActionStatus.PENDING:
            raise ValueError(f"Cannot approve action in status {self.status}")
        self.status = ActionStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = datetime.utcnow()

    def reject(self, reviewer: str, reason: str = "") -> None:
        if self.status != ActionStatus.PENDING:
            raise ValueError(f"Cannot reject action in status {self.status}")
        self.status = ActionStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = datetime.utcnow()
        self.rejection_reason = reason

    def mark_executed(self) -> None:
        if self.status != ActionStatus.APPROVED:
            raise ValueError(f"Cannot execute action in status {self.status}")
        self.status = ActionStatus.EXECUTED
        self.executed_at = datetime.utcnow()

    def mark_failed(self, error: str) -> None:
        self.status = ActionStatus.FAILED
        self.execution_error = error
        self.executed_at = datetime.utcnow()

    def mark_expired(self) -> None:
        if self.status == ActionStatus.PENDING:
            self.status = ActionStatus.EXPIRED

    # ── Factory helpers ────────────────────────────────────────────────────

    @classmethod
    def tier1(
        cls,
        client_id: str,
        platform: Platform,
        action_type: ActionType,
        description: str,
        payload: dict,
    ) -> "PendingAction":
        """Create a Tier 1 (auto) action — pre-approved, no queue needed."""
        action = cls(
            client_id=client_id,
            platform=platform,
            tier=ActionTier.AUTO,
            action_type=action_type,
            description=description,
            reason="Automatic — read-only operation",
            estimated_impact="None",
            payload=payload,
            status=ActionStatus.APPROVED,
        )
        action.reviewed_by = "system"
        action.reviewed_at = action.created_at
        return action

    @classmethod
    def tier2(
        cls,
        client_id: str,
        platform: Platform,
        action_type: ActionType,
        description: str,
        reason: str,
        estimated_impact: str,
        payload: dict,
    ) -> "PendingAction":
        """Create a Tier 2 action — goes into the queue, needs human ✅."""
        return cls(
            client_id=client_id,
            platform=platform,
            tier=ActionTier.APPROVE,
            action_type=action_type,
            description=description,
            reason=reason,
            estimated_impact=estimated_impact,
            payload=payload,
            status=ActionStatus.PENDING,
        )

    @classmethod
    def tier3(
        cls,
        client_id: str,
        platform: Platform,
        action_type: ActionType,
        description: str,
        reason: str,
        estimated_impact: str,
        payload: dict,
    ) -> "PendingAction":
        """Create a Tier 3 action — admin-only, extra confirmation required."""
        return cls(
            client_id=client_id,
            platform=platform,
            tier=ActionTier.RESTRICTED,
            action_type=action_type,
            description=description,
            reason=reason,
            estimated_impact=estimated_impact,
            payload=payload,
            status=ActionStatus.PENDING,
        )
