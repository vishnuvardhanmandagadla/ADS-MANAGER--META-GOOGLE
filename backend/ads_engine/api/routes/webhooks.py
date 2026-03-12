"""WhatsApp webhook endpoints.

GET  /webhooks/whatsapp  — Meta webhook verification challenge
POST /webhooks/whatsapp  — Receive incoming WhatsApp messages

Approvers can reply to notification messages with:
  APPROVE <id8>              — approve the action
  REJECT  <id8> [reason]     — reject with optional reason

Where <id8> is the first 8 characters of the action UUID
(shown in every notification message).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from ...approval.queue import ApprovalQueue
from ...core.config import get_settings
from ...notifications import get_dispatcher
from ..deps import get_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_WEBHOOK_REVIEWER = "whatsapp_webhook"


# ── Verification ──────────────────────────────────────────────────────────────


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    """Meta calls this once when you register the webhook URL.

    Responds with the challenge value if the verify token matches.
    Set WHATSAPP_VERIFY_TOKEN in .env to the same value you enter in
    the Meta developer console.
    """
    settings = get_settings()
    expected = settings.whatsapp_verify_token

    if not expected:
        logger.warning("WHATSAPP_VERIFY_TOKEN not set — rejecting verification request")
        raise HTTPException(status_code=403, detail="Webhook not configured")

    if hub_mode != "subscribe" or hub_verify_token != expected:
        logger.warning(
            "Webhook verification failed — mode=%s token_match=%s",
            hub_mode,
            hub_verify_token == expected,
        )
        raise HTTPException(status_code=403, detail="Verification failed")

    logger.info("WhatsApp webhook verified ✓")
    return PlainTextResponse(hub_challenge)


# ── Incoming messages ─────────────────────────────────────────────────────────


@router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def receive_message(
    request: Request,
    queue: ApprovalQueue = Depends(get_queue),
):
    """Receive incoming WhatsApp messages from Meta.

    Meta requires a 200 response within 20 s — we process synchronously
    and always return 200 (errors are logged, not propagated).
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return {"status": "ok"}  # always 200

    try:
        _process_webhook(body, queue)
    except Exception as exc:
        logger.error("Webhook processing error: %s", exc)

    return {"status": "ok"}


# ── Message processing ────────────────────────────────────────────────────────


def _process_webhook(body: dict, queue: ApprovalQueue) -> None:
    """Extract and act on incoming WhatsApp text messages."""
    entries = body.get("entry", [])
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                if msg.get("type") != "text":
                    continue
                sender = msg.get("from", "unknown")
                text = msg.get("text", {}).get("body", "").strip()
                if text:
                    _handle_command(text, sender, queue)


def _handle_command(text: str, sender: str, queue: ApprovalQueue) -> None:
    """Parse APPROVE / REJECT commands and act on the matching action."""
    parts = text.strip().split(None, 2)  # max 3 parts: CMD ID8 [REASON]
    if not parts:
        return

    cmd = parts[0].upper()

    if cmd == "APPROVE" and len(parts) >= 2:
        short_id = parts[1].lower()
        action = _find_action(short_id, queue)
        if not action:
            logger.warning("Webhook APPROVE: no pending action matching '%s'", short_id)
            return
        queue.approve(action.id, reviewer=_WEBHOOK_REVIEWER)
        logger.info(
            "WhatsApp APPROVE: action %s ('%s') approved by %s",
            action.id[:8], action.description, sender,
        )
        # Fire outcome notification (non-blocking)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_notify_outcome(action))
        except Exception:
            pass

    elif cmd == "REJECT" and len(parts) >= 2:
        short_id = parts[1].lower()
        reason = parts[2] if len(parts) >= 3 else "Rejected via WhatsApp"
        action = _find_action(short_id, queue)
        if not action:
            logger.warning("Webhook REJECT: no pending action matching '%s'", short_id)
            return
        queue.reject(action.id, reviewer=_WEBHOOK_REVIEWER, reason=reason)
        logger.info(
            "WhatsApp REJECT: action %s ('%s') rejected by %s — %s",
            action.id[:8], action.description, sender, reason,
        )
    else:
        logger.debug("Webhook: unrecognised command from %s: %r", sender, text[:80])


def _find_action(short_id: str, queue: ApprovalQueue):
    """Find a PENDING action whose UUID starts with short_id (case-insensitive)."""
    from ...approval.action import ActionStatus
    for action in queue.list_all():
        if (
            action.status == ActionStatus.PENDING
            and action.id.lower().startswith(short_id.lower())
        ):
            return action
    return None


async def _notify_outcome(action) -> None:
    """Send outcome notification after webhook-triggered approve/reject."""
    try:
        await get_dispatcher().on_approved(action)
    except Exception as exc:
        logger.debug("Outcome notification error: %s", exc)
