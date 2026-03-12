"""Campaigns endpoints.

GET  /api/v1/clients/{client_id}/campaigns   — list campaigns
POST /api/v1/actions                          — create a PendingAction directly
                                               (UI controls — bypasses AI, still goes
                                                through the approval queue)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...approval.action import ActionType, PendingAction
from ...approval.policies import PolicyViolation
from ...approval.queue import ApprovalQueue
from ...core.config import get_client_config, get_settings
from ...models.base import Platform
from ..deps import check_client_access, get_current_user, get_queue, require_approver
from ..schemas import ActionCardResponse, action_to_card

logger = logging.getLogger(__name__)
router = APIRouter(tags=["campaigns"])

# ── Mock campaign data ─────────────────────────────────────────────────────────
# Realistic Tickets99 campaign data.
# Phase 8 replaces this with real Meta Insights API calls when
# meta_access_token is set in .env.

_MOCK_CAMPAIGNS: list[dict[str, Any]] = [
    {
        "id": "camp_001",
        "name": "Chennai Events — Broad Audience",
        "status": "active",
        "objective": "CONVERSIONS",
        "daily_budget": 3000,
        "spend": 2840.5,
        "clicks": 942,
        "impressions": 78400,
        "cpc": 3.01,
        "ctr": 1.2,
        "roas": 3.8,
        "conversions": 28,
    },
    {
        "id": "camp_002",
        "name": "Hyderabad Concerts — Retargeting",
        "status": "active",
        "objective": "CONVERSIONS",
        "daily_budget": 1500,
        "spend": 1890.0,
        "clicks": 187,
        "impressions": 46900,
        "cpc": 10.1,
        "ctr": 0.4,
        "roas": 1.2,
        "conversions": 6,
    },
    {
        "id": "camp_003",
        "name": "Bangalore Comedy Night",
        "status": "paused",
        "objective": "TRAFFIC",
        "daily_budget": 2000,
        "spend": 0.0,
        "clicks": 0,
        "impressions": 0,
        "cpc": 0.0,
        "ctr": 0.0,
        "roas": None,
        "conversions": 0,
    },
    {
        "id": "camp_004",
        "name": "Sports Events — Lookalike 2%",
        "status": "active",
        "objective": "CONVERSIONS",
        "daily_budget": 2500,
        "spend": 2310.0,
        "clicks": 1155,
        "impressions": 96200,
        "cpc": 2.0,
        "ctr": 1.2,
        "roas": 5.1,
        "conversions": 41,
    },
]


# ── Request models ─────────────────────────────────────────────────────────────


class CreateActionRequest(BaseModel):
    client_id: str
    platform: str = "meta"
    action_type: str
    description: str
    reason: str
    estimated_impact: str
    payload: dict[str, Any] = {}


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/clients/{client_id}/campaigns")
async def list_campaigns(
    client_id: str,
    user: dict = Depends(get_current_user),
):
    """List campaigns for a client.

    Returns mock data unless Meta credentials are configured in .env,
    in which case Phase 8 will wire the real Insights API call here.
    """
    check_client_access(user, client_id)

    # Verify the client exists
    try:
        get_client_config(client_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found.",
        )

    settings = get_settings()
    if settings.meta_access_token:
        # Phase 8: replace with real MetaAdapter.get_campaigns() call
        logger.info(
            "[Campaigns] Meta credentials found — real API coming in Phase 8"
        )

    # Return mock data (with client_id injected)
    return [{"client_id": client_id, **c} for c in _MOCK_CAMPAIGNS]


@router.post("/actions", response_model=ActionCardResponse)
async def create_action(
    req: CreateActionRequest,
    user: dict = Depends(require_approver),  # manager or admin only
    queue: ApprovalQueue = Depends(get_queue),
):
    """Create a PendingAction directly from the UI.

    Used by campaign control buttons (Pause, Activate, Edit Budget).
    The action goes through the normal approval queue — nothing executes
    until a manager or admin approves it.
    """
    check_client_access(user, req.client_id)

    # Validate platform
    try:
        platform = Platform(req.platform.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown platform: {req.platform!r}",
        )

    # Validate action type
    try:
        action_type = ActionType(req.action_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action_type: {req.action_type!r}",
        )

    # Tier 3 actions require admin
    _TIER3 = {
        ActionType.DELETE_CAMPAIGN,
        ActionType.REMOVE_CLIENT,
        ActionType.OVERRIDE_BUDGET_CAP,
        ActionType.DISABLE_SAFETY_RULE,
    }
    if action_type in _TIER3 and user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for Tier 3 actions.",
        )

    # Build the action
    _TIER1 = {
        ActionType.GET_CAMPAIGNS,
        ActionType.GET_ADSETS,
        ActionType.GET_ADS,
        ActionType.GET_PERFORMANCE,
    }
    kwargs = dict(
        client_id=req.client_id,
        platform=platform,
        action_type=action_type,
        description=req.description,
        payload=req.payload,
    )
    if action_type in _TIER1:
        action = PendingAction.tier1(**kwargs)
    elif action_type in _TIER3:
        action = PendingAction.tier3(
            reason=req.reason,
            estimated_impact=req.estimated_impact,
            **kwargs,
        )
    else:
        action = PendingAction.tier2(
            reason=req.reason,
            estimated_impact=req.estimated_impact,
            **kwargs,
        )

    try:
        queue.enqueue(action)
    except PolicyViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return action_to_card(action)
