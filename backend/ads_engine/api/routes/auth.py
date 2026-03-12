"""Auth routes — login and token refresh."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...core.config import get_settings
from ..auth import authenticate_user, create_access_token
from ..deps import get_current_user
from ..schemas import LoginRequest, MessageResponse, TokenResponse, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Exchange username + password for a JWT access token."""
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    settings = get_settings()
    token = create_access_token(
        username=user["username"],
        role=user["role"],
        client_ids=user["client_ids"],
        secret_key=settings.secret_key,
    )
    return TokenResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
    )


@router.get("/me", response_model=UserInfo)
async def me(user: dict = Depends(get_current_user)):
    """Return info about the currently authenticated user."""
    return UserInfo(
        username=user["username"],
        role=user["role"],
        client_ids=user["client_ids"],
    )
