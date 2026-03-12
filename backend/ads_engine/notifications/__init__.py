"""Notification channels — Phase 9.

Current channels: WhatsApp Business Cloud API.
"""

from .dispatcher import NotificationDispatcher, init_dispatcher, get_dispatcher

__all__ = ["NotificationDispatcher", "init_dispatcher", "get_dispatcher"]
