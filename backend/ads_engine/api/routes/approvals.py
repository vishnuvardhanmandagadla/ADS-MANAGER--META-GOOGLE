"""Approval queue routes — the core human-in-the-loop API.

These are the endpoints the dashboard and WhatsApp webhook call to
approve / reject / cancel pending actions.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...approval.action import ActionStatus
from ...approval.queue import ApprovalQueue
from ...approval.reviewer import ActionReviewer
from ..deps import check_client_access, get_current_user, get_queue, require_approver
from ..schemas import (
    ActionCardResponse,
    ApprovalsListResponse,
    ApproveRequest,
    MessageResponse,
    RejectRequest,
    action_to_card,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/approvals", tags=["approvals"])

# Reviewer is stateless so one shared instance is fine
_reviewer = ActionReviewer()


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("", response_model=ApprovalsListResponse)
async def list_pending(
    client_id: Optional[str] = Query(None, description="Filter by client"),
    user: dict = Depends(get_current_user),
    queue: ApprovalQueue = Depends(get_queue),
):
    """Return all pending actions visible to the current user."""
    if client_id:
        check_client_access(user, client_id)

    pending = queue.list_pending(
        client_id=client_id if client_id else None
        if "*" in user["client_ids"]
        else None,
    )

    # Non-admin users: filter to their allowed clients
    if "*" not in user["client_ids"]:
        pending = [a for a in pending if a.client_id in user["client_ids"]]

    # Run expiry maintenance on every list call (cheap, no scheduler needed yet)
    queue.expire_old()

    return ApprovalsListResponse(
        pending_count=len(pending),
        actions=[action_to_card(a) for a in pending],
    )


@router.get("/all", response_model=ApprovalsListResponse)
async def list_all(
    client_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(get_current_user),
    queue: ApprovalQueue = Depends(get_queue),
):
    """Return all actions (any status) with optional filters."""
    if client_id:
        check_client_access(user, client_id)

    status_enum = None
    if status_filter:
        try:
            status_enum = ActionStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status_filter}'. "
                       f"Valid: {[s.value for s in ActionStatus]}",
            )

    actions = queue.list_all(client_id=client_id, status=status_enum, limit=limit)

    if "*" not in user["client_ids"]:
        actions = [a for a in actions if a.client_id in user["client_ids"]]

    return ApprovalsListResponse(
        pending_count=queue.pending_count(),
        actions=[action_to_card(a) for a in actions],
    )


@router.get("/{action_id}", response_model=ActionCardResponse)
async def get_action(
    action_id: str,
    user: dict = Depends(get_current_user),
    queue: ApprovalQueue = Depends(get_queue),
):
    """Get a single action by ID."""
    action = queue.get(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")
    check_client_access(user, action.client_id)
    return action_to_card(action)


# ── Approve ────────────────────────────────────────────────────────────────────


@router.post("/{action_id}/approve", response_model=ActionCardResponse)
async def approve_action(
    action_id: str,
    body: ApproveRequest,
    user: dict = Depends(require_approver),
    queue: ApprovalQueue = Depends(get_queue),
):
    """Approve a pending action. Requires manager or admin role."""
    action = queue.get(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")

    check_client_access(user, action.client_id)

    # Tier 3 actions need admin
    from ...models.base import ActionTier
    if action.tier == ActionTier.RESTRICTED and user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tier 3 (restricted) actions require Admin role",
        )

    try:
        updated = queue.approve(action_id, reviewer=body.reviewer)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    logger.info("Action %s approved by %s via API", action_id[:8], body.reviewer)

    try:
        from ...db.audit import get_audit_log, ACTION_APPROVED
        get_audit_log().log_event(
            event_type=ACTION_APPROVED,
            client_id=updated.client_id,
            action_id=updated.id,
            action_type=updated.action_type,
            platform=updated.platform,
            tier=updated.tier,
            description=updated.description,
            actor=body.reviewer,
        )
    except RuntimeError:
        pass

    return action_to_card(updated)


# ── Reject ─────────────────────────────────────────────────────────────────────


@router.post("/{action_id}/reject", response_model=ActionCardResponse)
async def reject_action(
    action_id: str,
    body: RejectRequest,
    user: dict = Depends(require_approver),
    queue: ApprovalQueue = Depends(get_queue),
):
    """Reject a pending action. Requires manager or admin role."""
    action = queue.get(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")

    check_client_access(user, action.client_id)

    try:
        updated = queue.reject(action_id, reviewer=body.reviewer, reason=body.reason)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    logger.info("Action %s rejected by %s — %s", action_id[:8], body.reviewer, body.reason)

    try:
        from ...db.audit import get_audit_log, ACTION_REJECTED
        get_audit_log().log_event(
            event_type=ACTION_REJECTED,
            client_id=updated.client_id,
            action_id=updated.id,
            action_type=updated.action_type,
            platform=updated.platform,
            tier=updated.tier,
            description=updated.description,
            actor=body.reviewer,
            reason=body.reason,
        )
    except RuntimeError:
        pass

    return action_to_card(updated)


# ── Cancel ─────────────────────────────────────────────────────────────────────


@router.post("/{action_id}/cancel", response_model=ActionCardResponse)
async def cancel_action(
    action_id: str,
    user: dict = Depends(get_current_user),
    queue: ApprovalQueue = Depends(get_queue),
):
    """Cancel a pending action (withdraw before review). Any authenticated user."""
    action = queue.get(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")

    check_client_access(user, action.client_id)

    try:
        updated = queue.cancel(action_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return action_to_card(updated)
