"""Request / response Pydantic schemas for the API layer.

These are separate from the core models so the API surface can evolve
independently of internal data structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..approval.action import ActionStatus, ActionType
from ..models.base import ActionTier, Platform


# ── Auth ───────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserInfo(BaseModel):
    username: str
    role: str                          # admin | manager | viewer
    client_ids: list[str]              # which clients this user can see


# ── Clients ────────────────────────────────────────────────────────────────────


class ClientSummary(BaseModel):
    client_id: str
    name: str
    currency: str
    platforms_enabled: list[str]
    max_daily_spend: Optional[float] = None


# ── Campaigns ─────────────────────────────────────────────────────────────────


class CampaignSummary(BaseModel):
    id: str
    name: str
    status: str
    platform: str
    daily_budget: Optional[float] = None
    spend: Optional[float] = None
    clicks: Optional[int] = None
    cpc: Optional[float] = None


# ── Approvals ─────────────────────────────────────────────────────────────────


class ActionCardResponse(BaseModel):
    """Shape of a PendingAction as returned by the API."""
    id: str
    client_id: str
    platform: str
    tier: int
    action_type: str
    description: str
    reason: str
    estimated_impact: str
    status: str
    status_emoji: str
    payload: dict[str, Any]
    created_at: datetime
    expires_at: datetime
    age_minutes: float
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    execution_error: Optional[str] = None


_STATUS_EMOJI = {
    ActionStatus.PENDING:   "🟡",
    ActionStatus.APPROVED:  "✅",
    ActionStatus.REJECTED:  "❌",
    ActionStatus.EXECUTED:  "✅",
    ActionStatus.FAILED:    "🔴",
    ActionStatus.EXPIRED:   "⏱️",
    ActionStatus.CANCELLED: "🚫",
}


def action_to_card(action) -> ActionCardResponse:
    """Convert a PendingAction to its API response shape."""
    return ActionCardResponse(
        id=action.id,
        client_id=action.client_id,
        platform=action.platform,
        tier=action.tier,
        action_type=action.action_type,
        description=action.description,
        reason=action.reason,
        estimated_impact=action.estimated_impact,
        status=action.status,
        status_emoji=_STATUS_EMOJI.get(action.status, "❓"),
        payload=action.payload,
        created_at=action.created_at,
        expires_at=action.expires_at,
        age_minutes=round(action.age_minutes, 1),
        reviewed_by=action.reviewed_by,
        reviewed_at=action.reviewed_at,
        executed_at=action.executed_at,
        rejection_reason=action.rejection_reason,
        execution_error=action.execution_error,
    )


class ApproveRequest(BaseModel):
    reviewer: str = Field(..., min_length=1, description="Username of approver")


class RejectRequest(BaseModel):
    reviewer: str = Field(..., min_length=1)
    reason: str = Field(default="", description="Why this action was rejected")


class ApprovalsListResponse(BaseModel):
    pending_count: int
    actions: list[ActionCardResponse]


# ── WebSocket events ───────────────────────────────────────────────────────────


class WSEvent(BaseModel):
    event: str          # action_queued | action_approved | action_rejected | action_executed | action_failed
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Generic responses ─────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
