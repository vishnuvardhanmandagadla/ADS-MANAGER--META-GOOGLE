"""FastAPI dependency injection — reusable deps for routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from ..approval import queue as _queue_module
from ..approval.queue import ApprovalQueue
from ..core.config import get_settings
from .auth import can_access_client, can_approve, can_approve_tier3, decode_token

_bearer = HTTPBearer()


# ── Queue ──────────────────────────────────────────────────────────────────────


def get_queue() -> ApprovalQueue:
    """Return the global approval queue. Raises 503 if not yet initialised."""
    q = _queue_module.approval_queue  # read live from module, not stale import
    if q is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Approval queue not initialised. Server may still be starting.",
        )
    return q


# ── Auth ───────────────────────────────────────────────────────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Validate Bearer token and return user dict."""
    settings = get_settings()
    try:
        payload = decode_token(credentials.credentials, settings.secret_key)
        username: str = payload.get("sub", "")
        if not username:
            raise ValueError("Missing subject")
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "username": username,
        "role": payload.get("role", "viewer"),
        "client_ids": payload.get("client_ids", []),
    }


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Raise 403 if user is not an admin."""
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


async def require_approver(user: dict = Depends(get_current_user)) -> dict:
    """Raise 403 if user cannot approve Tier 2 actions."""
    if not can_approve(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or Admin role required to approve actions",
        )
    return user


def check_client_access(user: dict, client_id: str) -> None:
    """Raise 403 if user cannot access this client."""
    if not can_access_client(user, client_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to client '{client_id}'",
        )
