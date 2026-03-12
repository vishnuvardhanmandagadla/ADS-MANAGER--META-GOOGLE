"""Notification dispatcher — single entry point for all outbound notifications.

Initialised once at app startup. If WhatsApp credentials are not configured,
all notification methods become silent no-ops so the rest of the system
is unaffected.

Usage in other modules:
    from ads_engine.notifications import get_dispatcher
    await get_dispatcher().on_queued(action)
"""

from __future__ import annotations

import logging
from typing import Optional

from ..approval.action import ActionTier, PendingAction
from ..core.config import Settings
from .whatsapp import DigestStats, WhatsAppClient

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Routes events to configured notification channels.

    Currently supports: WhatsApp Business Cloud API.
    Telegram stub removed — WhatsApp-only for Phase 9.
    """

    def __init__(self, settings: Settings):
        self._admin_phone: Optional[str] = settings.admin_whatsapp
        self._wa: Optional[WhatsAppClient] = None

        if settings.whatsapp_api_token and settings.whatsapp_phone_number_id:
            self._wa = WhatsAppClient(
                api_token=settings.whatsapp_api_token,
                phone_number_id=settings.whatsapp_phone_number_id,
            )
            logger.info(
                "[Notifications] WhatsApp ready — phone_number_id=%s, admin=%s",
                settings.whatsapp_phone_number_id,
                self._admin_phone or "not set",
            )
        else:
            logger.info(
                "[Notifications] WhatsApp not configured "
                "(WHATSAPP_API_TOKEN / WHATSAPP_PHONE_NUMBER_ID missing)"
            )

    # ── Queue lifecycle events ─────────────────────────────────────────────────

    async def on_queued(self, action: PendingAction) -> None:
        """Called when an action enters the queue. Notifies for Tier 2/3 only."""
        if action.tier == ActionTier.AUTO:
            return  # Tier 1 — auto, no human notification needed
        if not self._wa or not self._admin_phone:
            return
        await self._wa.send_approval_request(self._admin_phone, action)

    async def on_approved(self, action: PendingAction) -> None:
        """Called when an action is approved via the dashboard."""
        if not self._wa or not self._admin_phone:
            return
        await self._wa.send_outcome(self._admin_phone, action)

    async def on_rejected(self, action: PendingAction) -> None:
        """Called when an action is rejected."""
        if not self._wa or not self._admin_phone:
            return
        await self._wa.send_outcome(self._admin_phone, action)

    async def on_executed(self, action: PendingAction) -> None:
        """Called when an approved action is successfully executed."""
        if not self._wa or not self._admin_phone:
            return
        await self._wa.send_outcome(self._admin_phone, action)

    async def on_failed(self, action: PendingAction) -> None:
        """Called when execution of an approved action fails."""
        if not self._wa or not self._admin_phone:
            return
        await self._wa.send_outcome(self._admin_phone, action)

    async def on_expired(self, actions: list[PendingAction]) -> None:
        """Called when pending actions expire without review."""
        if not actions or not self._wa or not self._admin_phone:
            return
        await self._wa.send_expiry_reminder(self._admin_phone, actions)

    # ── Scheduled notifications ────────────────────────────────────────────────

    async def send_daily_digest(self, stats: DigestStats) -> None:
        """Send morning digest. Called by the scheduler (Phase 10)."""
        if not self._wa or not self._admin_phone:
            return
        await self._wa.send_daily_digest(self._admin_phone, stats)

    async def send_anomaly_alert(self, client_id: str, message: str) -> None:
        """Send an anomaly alert (CPC spike, budget overrun, etc.)."""
        if not self._wa or not self._admin_phone:
            return
        await self._wa.send_anomaly_alert(self._admin_phone, client_id, message)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._wa:
            await self._wa.close()


# ── Singleton ─────────────────────────────────────────────────────────────────

_dispatcher: Optional[NotificationDispatcher] = None


def init_dispatcher(settings: Settings) -> NotificationDispatcher:
    """Call once at app startup."""
    global _dispatcher
    _dispatcher = NotificationDispatcher(settings)
    return _dispatcher


def get_dispatcher() -> NotificationDispatcher:
    """Return the singleton. Raises if not yet initialised."""
    if _dispatcher is None:
        raise RuntimeError(
            "NotificationDispatcher not initialised — call init_dispatcher() at startup"
        )
    return _dispatcher
