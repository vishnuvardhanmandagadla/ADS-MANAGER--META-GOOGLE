"""AI endpoints — conversational interface + copy generation.

POST /api/v1/ai/chat      — chat with the AI analyst, auto-queues suggested actions
POST /api/v1/ai/copy      — generate ad copy variations
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...ai.chat import ChatSession
from ...ai.copywriter import generate_copy
from ...models.base import Platform
from ..deps import check_client_access, get_current_user, get_queue
from ..schemas import ActionCardResponse, action_to_card

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


# ── Request / response models ───────────────────────────────────────────────────


class ChatRequest(BaseModel):
    client_id: str
    message: str
    platform: str = "meta"
    auto_queue: bool = True


class ChatResponseSchema(BaseModel):
    message: str
    proposed_actions: list[dict]
    queued_actions: list[ActionCardResponse]
    queued_count: int


class CopyRequest(BaseModel):
    client_id: str
    product: str
    audience: str
    count: int = 3
    existing_copy: Optional[str] = None


class CopyResponseSchema(BaseModel):
    variations: list[dict]
    count: int


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponseSchema)
async def ai_chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    queue=Depends(get_queue),
):
    """Chat with the AI analyst.

    Suggested actions are automatically enqueued for human approval
    unless `auto_queue` is set to false.
    """
    check_client_access(user, req.client_id)

    try:
        platform = Platform(req.platform.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown platform {req.platform!r}. Use 'meta' or 'google'.",
        )

    session = ChatSession(client_id=req.client_id)

    try:
        result = session.chat(
            user_message=req.message,
            platform=platform,
            auto_queue=req.auto_queue,
            queue=queue,
        )
    except Exception as exc:
        logger.error("[AI chat] Error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service error: {exc}",
        )

    return ChatResponseSchema(
        message=result.message,
        proposed_actions=result.proposed_actions,
        queued_actions=[action_to_card(a) for a in result.queued_actions],
        queued_count=len(result.queued_actions),
    )


@router.post("/copy", response_model=CopyResponseSchema)
async def ai_copy(
    req: CopyRequest,
    user: dict = Depends(get_current_user),
):
    """Generate ad copy variations for a product and target audience."""
    check_client_access(user, req.client_id)

    if not 1 <= req.count <= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="count must be between 1 and 10.",
        )

    try:
        variations = generate_copy(
            client_id=req.client_id,
            product=req.product,
            audience=req.audience,
            count=req.count,
            existing_copy=req.existing_copy,
        )
    except Exception as exc:
        logger.error("[AI copy] Error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service error: {exc}",
        )

    return CopyResponseSchema(variations=variations, count=len(variations))
