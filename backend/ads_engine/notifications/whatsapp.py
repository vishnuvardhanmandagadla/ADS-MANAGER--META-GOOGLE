"""WhatsApp Business Cloud API client.

Sends approval requests, outcome notifications, daily digests, and
anomaly alerts via the Meta WhatsApp Cloud API.

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

from ..approval.action import PendingAction

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_API_BASE = "https://graph.facebook.com/v21.0"
_TIMEOUT = 10.0  # seconds


# ── Message helpers ────────────────────────────────────────────────────────────


@dataclass
class DigestStats:
    """Stats bundle for the morning daily digest."""
    date: str                          # "12 Mar 2026"
    total_spend: float                 # ₹ spent across all clients today
    pending_count: int                 # actions waiting for review
    approved_today: int = 0
    rejected_today: int = 0
    top_campaign: Optional[str] = None  # best performer name


# ── Client ────────────────────────────────────────────────────────────────────


class WhatsAppClient:
    """Thin wrapper around the WhatsApp Business Cloud API.

    All send methods are fire-and-forget — they log errors but never raise,
    so a notification failure never crashes the main request path.
    """

    def __init__(self, api_token: str, phone_number_id: str):
        self._token = api_token
        self._phone_number_id = phone_number_id
        self._http = httpx.AsyncClient(
            base_url=_API_BASE,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=_TIMEOUT,
        )

    async def close(self) -> None:
        await self._http.aclose()

    # ── Core send ─────────────────────────────────────────────────────────────

    async def send_text(self, to: str, text: str) -> bool:
        """Send a plain text message. Returns True on success."""
        phone = _normalise_phone(to)
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text, "preview_url": False},
        }
        try:
            resp = await self._http.post(
                f"/{self._phone_number_id}/messages",
                json=payload,
            )
            if resp.status_code >= 400:
                logger.error(
                    "WhatsApp send failed (%s): %s", resp.status_code, resp.text[:300]
                )
                return False
            return True
        except Exception as exc:
            logger.error("WhatsApp send error: %s", exc)
            return False

    # ── Notification templates ─────────────────────────────────────────────────

    async def send_approval_request(
        self, to: str, action: PendingAction
    ) -> bool:
        """Send a Tier 2/3 approval request with short-ID reply instructions."""
        short_id = action.id[:8]
        tier_tag = "⚠️ ADMIN ACTION" if action.tier == 3 else "🔔 Approval Needed"

        lines = [
            f"{tier_tag} — {action.client_id.title()}",
            "",
            f"*{action.description}*",
            f"Platform: {action.platform.upper()}",
            f"Reason: {action.reason}",
            f"Impact: {action.estimated_impact}",
            f"Expires: {action.expires_at.strftime('%d %b %H:%M')} UTC",
            "",
            f"Reply  APPROVE {short_id}  to approve",
            f"Reply  REJECT {short_id} <reason>  to reject",
        ]
        return await self.send_text(to, "\n".join(lines))

    async def send_outcome(self, to: str, action: PendingAction) -> bool:
        """Notify that an action was approved / rejected / executed / failed."""
        status_icons = {
            "approved":  "✅ Approved",
            "rejected":  "❌ Rejected",
            "executed":  "✅ Executed",
            "failed":    "🔴 Failed",
            "cancelled": "🚫 Cancelled",
            "expired":   "⏱️ Expired",
        }
        label = status_icons.get(action.status, action.status.upper())

        lines = [
            f"{label} — {action.client_id.title()}",
            action.description,
        ]
        if action.reviewed_by:
            lines.append(f"By: {action.reviewed_by}")
        if action.rejection_reason:
            lines.append(f"Reason: {action.rejection_reason}")
        if action.execution_error:
            lines.append(f"Error: {action.execution_error}")

        return await self.send_text(to, "\n".join(lines))

    async def send_expiry_reminder(
        self, to: str, actions: list[PendingAction]
    ) -> bool:
        """Alert that pending actions are about to expire."""
        if not actions:
            return True
        lines = [f"⏱️ {len(actions)} action(s) expiring soon — review required"]
        for a in actions[:5]:  # cap at 5 to avoid huge messages
            lines.append(f"  • {a.description}")
        if len(actions) > 5:
            lines.append(f"  … and {len(actions) - 5} more")
        lines.append("\nOpen the dashboard to approve or reject.")
        return await self.send_text(to, "\n".join(lines))

    async def send_daily_digest(self, to: str, stats: DigestStats) -> bool:
        """Send the morning performance digest."""
        lines = [
            f"📊 Daily Digest — {stats.date}",
            "",
            f"Spend today:  ₹{stats.total_spend:,.0f}",
            f"Pending approvals:  {stats.pending_count}",
            f"Approved:  {stats.approved_today}  |  Rejected:  {stats.rejected_today}",
        ]
        if stats.top_campaign:
            lines.append(f"Top campaign: {stats.top_campaign}")
        lines.append("\nHave a productive day! 🚀")
        return await self.send_text(to, "\n".join(lines))

    async def send_anomaly_alert(
        self, to: str, client_id: str, message: str
    ) -> bool:
        """Send a spend anomaly or CPC spike alert."""
        text = f"🚨 Anomaly — {client_id.title()}\n\n{message}"
        return await self.send_text(to, text)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalise_phone(phone: str) -> str:
    """Strip spaces/dashes and ensure E.164 format without the leading +."""
    return phone.replace("+", "").replace(" ", "").replace("-", "")
