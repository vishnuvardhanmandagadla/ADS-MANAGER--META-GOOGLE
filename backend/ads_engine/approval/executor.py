"""Executor — the only place that calls platform adapter write methods.

Flow:
    Human approves → queue.approve() → executor.run(action) → platform API call

The executor dispatches based on action.action_type to the correct adapter method.
It never touches unapproved actions.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models.base import EntityStatus, Platform, Targeting, AdCreative
from ..platforms.base import PlatformAdapter
from .action import ActionStatus, ActionType, PendingAction
from .queue import ApprovalQueue

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes approved PendingActions by dispatching to platform adapters."""

    def __init__(self, queue: ApprovalQueue):
        self._queue = queue
        # Registry: (client_id, platform) → adapter
        self._adapters: dict[tuple[str, Platform], PlatformAdapter] = {}

    def register_adapter(self, client_id: str, adapter: PlatformAdapter) -> None:
        """Register a platform adapter for a client."""
        key = (client_id, adapter.platform)
        self._adapters[key] = adapter
        logger.info("Registered %s adapter for client '%s'", adapter.platform, client_id)

    def get_adapter(self, client_id: str, platform: Platform) -> PlatformAdapter:
        key = (client_id, platform)
        adapter = self._adapters.get(key)
        if not adapter:
            raise RuntimeError(
                f"No adapter registered for client='{client_id}' platform='{platform}'. "
                "Register one via executor.register_adapter() at startup."
            )
        return adapter

    # ── Main entry point ───────────────────────────────────────────────────

    async def run(self, action_id: str) -> Any:
        """Execute an approved action.

        Args:
            action_id: The UUID of the approved PendingAction.

        Returns:
            Whatever the platform adapter returns (Campaign, AdSet, Ad, bool...).

        Raises:
            ValueError: If action is not in APPROVED state.
            RuntimeError: If no adapter is registered for this client+platform.
        """
        action = self._queue.get(action_id)
        if not action:
            raise KeyError(f"Action '{action_id}' not found")

        if action.status != ActionStatus.APPROVED:
            raise ValueError(
                f"Action '{action_id}' is {action.status}, not APPROVED. "
                "Only approved actions can be executed."
            )

        logger.info(
            "[EXECUTOR] Running %s — '%s' for client '%s'",
            action.action_type, action.description, action.client_id,
        )

        try:
            result = await self._dispatch(action)
            self._queue.mark_executed(action_id)
            logger.info("[EXECUTOR] Success: %s", action.description)
            return result

        except Exception as exc:
            error_msg = str(exc)
            self._queue.mark_failed(action_id, error_msg)
            logger.error("[EXECUTOR] Failed: %s — %s", action.description, error_msg)
            raise

    # ── Dispatcher ─────────────────────────────────────────────────────────

    async def _dispatch(self, action: PendingAction) -> Any:
        """Route action to the correct adapter method."""
        adapter = self.get_adapter(action.client_id, action.platform)
        p = action.payload  # shorthand

        match action.action_type:

            # ── Tier 2 — write operations ──────────────────────────────────

            case ActionType.CREATE_CAMPAIGN:
                return await adapter.create_campaign(
                    name=p["name"],
                    objective=p["objective"],
                    daily_budget=float(p["daily_budget"]),
                    start_date=p.get("start_date"),
                    end_date=p.get("end_date"),
                )

            case ActionType.CREATE_ADSET:
                targeting = Targeting(**p["targeting"]) if p.get("targeting") else Targeting()
                return await adapter.create_adset(
                    campaign_id=p["campaign_id"],
                    name=p["name"],
                    targeting=targeting,
                    daily_budget=float(p["daily_budget"]) if p.get("daily_budget") else None,
                )

            case ActionType.CREATE_AD:
                creative = AdCreative(**p["creative"]) if p.get("creative") else AdCreative()
                return await adapter.create_ad(
                    adset_id=p["adset_id"],
                    name=p["name"],
                    creative=creative,
                )

            case ActionType.UPDATE_BUDGET:
                return await adapter.update_campaign_budget(
                    campaign_id=p["campaign_id"],
                    new_daily_budget=float(p["new_daily_budget"]),
                )

            case ActionType.PAUSE_CAMPAIGN:
                return await adapter.set_campaign_status(
                    campaign_id=p["campaign_id"],
                    status=EntityStatus.PAUSED,
                )

            case ActionType.ACTIVATE_CAMPAIGN:
                return await adapter.set_campaign_status(
                    campaign_id=p["campaign_id"],
                    status=EntityStatus.ACTIVE,
                )

            case ActionType.PAUSE_ADSET:
                return await adapter.set_adset_status(
                    adset_id=p["adset_id"],
                    status=EntityStatus.PAUSED,
                )

            case ActionType.ACTIVATE_ADSET:
                return await adapter.set_adset_status(
                    adset_id=p["adset_id"],
                    status=EntityStatus.ACTIVE,
                )

            case ActionType.UPDATE_TARGETING:
                targeting = Targeting(**p["targeting"])
                return await adapter.update_adset_targeting(
                    adset_id=p["adset_id"],
                    targeting=targeting,
                )

            case ActionType.DUPLICATE_CAMPAIGN:
                return await adapter.duplicate_campaign(
                    campaign_id=p["campaign_id"],
                    new_name=p["new_name"],
                )

            # ── Tier 3 — restricted ────────────────────────────────────────

            case ActionType.DELETE_CAMPAIGN:
                return await adapter.delete_campaign(campaign_id=p["campaign_id"])

            # ── Tier 1 — should not reach executor ────────────────────────

            case ActionType.GET_CAMPAIGNS | ActionType.GET_ADSETS | \
                 ActionType.GET_ADS | ActionType.GET_PERFORMANCE:
                logger.warning(
                    "Tier 1 action %s passed to executor — skipping (no-op)",
                    action.action_type,
                )
                return None

            case _:
                raise NotImplementedError(
                    f"No executor handler for action_type='{action.action_type}'"
                )
