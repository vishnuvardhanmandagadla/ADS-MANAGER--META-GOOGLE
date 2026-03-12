"""Reviewer — formats and dispatches approval notifications to humans.

Phase 3: Logs to console + formats the WhatsApp/dashboard message payload.
Phase 9: Will wire up real WhatsApp Business API and Telegram bot.

The reviewer doesn't block — it sends the notification and returns immediately.
The human's response (approve/reject) comes back via the API endpoints (Phase 4).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from .action import ActionStatus, ActionTier, PendingAction

logger = logging.getLogger(__name__)

# Tier labels for notification messages
_TIER_LABELS = {
    ActionTier.AUTO: "Auto",
    ActionTier.APPROVE: "Needs Your Approval",
    ActionTier.RESTRICTED: "Admin Action Required",
}

# Status emoji
_STATUS_EMOJI = {
    ActionStatus.PENDING:   "🟡",
    ActionStatus.APPROVED:  "✅",
    ActionStatus.REJECTED:  "❌",
    ActionStatus.EXECUTED:  "✅ Done",
    ActionStatus.FAILED:    "🔴 Failed",
    ActionStatus.EXPIRED:   "⏱️ Expired",
    ActionStatus.CANCELLED: "🚫 Cancelled",
}


class ActionReviewer:
    """Formats and sends approval notifications. Stubs for Phase 9 channels."""

    def __init__(self, admin_whatsapp: Optional[str] = None, admin_email: Optional[str] = None):
        self._admin_whatsapp = admin_whatsapp
        self._admin_email = admin_email

    # ── Main entry point ───────────────────────────────────────────────────

    async def notify(self, action: PendingAction) -> None:
        """Send a notification for a newly queued action.

        For Tier 1 (auto): no notification needed.
        For Tier 2/3: log + format message + send to configured channels.
        """
        if action.tier == ActionTier.AUTO:
            return

        message = self.format_whatsapp_message(action)

        # Always log — Phase 9 will also fire real channels here
        logger.info("\n%s\n%s", "─" * 60, message)

        # Phase 9 stubs:
        await self._send_whatsapp(message, action)
        await self._send_telegram(message, action)

    # ── Message formatters ─────────────────────────────────────────────────

    def format_whatsapp_message(self, action: PendingAction) -> str:
        """Format the WhatsApp approval request message."""
        tier_label = _TIER_LABELS.get(action.tier, "Review Required")
        age = f"{action.age_minutes:.0f} min ago" if action.age_minutes >= 1 else "just now"

        lines = [
            f"🔔 *{tier_label}* — {action.client_id.title()}",
            f"",
            f"*Action:* {action.description}",
            f"*Platform:* {action.platform.upper()}",
            f"*Reason:* {action.reason}",
            f"*Impact:* {action.estimated_impact}",
            f"*Created:* {age}",
            f"*Expires:* {action.expires_at.strftime('%d %b %H:%M')} UTC",
            f"",
            f"Reply *APPROVE {action.id[:8]}* to approve",
            f"Reply *REJECT {action.id[:8]}* to reject",
        ]
        if action.tier == ActionTier.RESTRICTED:
            lines.insert(1, "⚠️ *ADMIN ACTION — Extra confirmation required*")

        return "\n".join(lines)

    def format_dashboard_card(self, action: PendingAction) -> dict:
        """Return a dict ready to be serialised as JSON for the dashboard UI."""
        return {
            "id": action.id,
            "client_id": action.client_id,
            "platform": action.platform,
            "tier": action.tier,
            "action_type": action.action_type,
            "description": action.description,
            "reason": action.reason,
            "estimated_impact": action.estimated_impact,
            "status": action.status,
            "status_emoji": _STATUS_EMOJI.get(action.status, "❓"),
            "created_at": action.created_at.isoformat(),
            "expires_at": action.expires_at.isoformat(),
            "age_minutes": round(action.age_minutes, 1),
            "reviewed_by": action.reviewed_by,
            "reviewed_at": action.reviewed_at.isoformat() if action.reviewed_at else None,
            "executed_at": action.executed_at.isoformat() if action.executed_at else None,
            "rejection_reason": action.rejection_reason,
            "execution_error": action.execution_error,
        }

    # ── Channels ───────────────────────────────────────────────────────────

    async def _send_whatsapp(self, message: str, action: PendingAction) -> None:
        """Send via WhatsApp Business Cloud API (Phase 9)."""
        try:
            from ..notifications import get_dispatcher
            await get_dispatcher().on_queued(action)
        except RuntimeError:
            # Dispatcher not yet initialised (e.g. during tests)
            if self._admin_whatsapp:
                logger.debug(
                    "[REVIEWER] WhatsApp → %s:\n%s", self._admin_whatsapp, message
                )

    # ── Outcome notifications ──────────────────────────────────────────────

    async def notify_executed(self, action: PendingAction) -> None:
        """Notify that an approved action was successfully executed."""
        msg = (
            f"✅ *Executed* — {action.client_id.title()}\n"
            f"{action.description}\n"
            f"Approved by: {action.reviewed_by} | "
            f"Executed: {action.executed_at.strftime('%H:%M') if action.executed_at else '—'}"
        )
        logger.info("\n%s", msg)

    async def notify_failed(self, action: PendingAction) -> None:
        """Notify that an approved action failed during execution."""
        msg = (
            f"🔴 *Execution Failed* — {action.client_id.title()}\n"
            f"{action.description}\n"
            f"Error: {action.execution_error}"
        )
        logger.error("\n%s", msg)

    async def notify_expired(self, actions: list[PendingAction]) -> None:
        """Notify about expired actions (called by scheduler)."""
        if not actions:
            return
        lines = [f"⏱️ *{len(actions)} action(s) expired without review*"]
        for a in actions:
            lines.append(f"  • {a.description} ({a.client_id})")
        logger.warning("\n".join(lines))
