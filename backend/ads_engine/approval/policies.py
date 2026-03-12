"""Approval policies — what tier does an action belong to, and is it safe to run?

This is the rules engine that sits between "AI wants to do X" and "X happens".
It enforces:
  - Tier classification (auto / approve / restricted)
  - Safety limits (spend caps, campaign creation limits)
  - Cool-down after rejection (don't re-suggest the same thing immediately)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..models.base import ActionTier
from .action import ActionStatus, ActionType, PendingAction

logger = logging.getLogger(__name__)


# ── Tier map ───────────────────────────────────────────────────────────────────

_TIER_MAP: dict[ActionType, ActionTier] = {
    # Tier 1 — auto
    ActionType.GET_CAMPAIGNS:   ActionTier.AUTO,
    ActionType.GET_ADSETS:      ActionTier.AUTO,
    ActionType.GET_ADS:         ActionTier.AUTO,
    ActionType.GET_PERFORMANCE: ActionTier.AUTO,

    # Tier 2 — approve
    ActionType.CREATE_CAMPAIGN:    ActionTier.APPROVE,
    ActionType.CREATE_ADSET:       ActionTier.APPROVE,
    ActionType.CREATE_AD:          ActionTier.APPROVE,
    ActionType.UPDATE_BUDGET:      ActionTier.APPROVE,
    ActionType.PAUSE_CAMPAIGN:     ActionTier.APPROVE,
    ActionType.ACTIVATE_CAMPAIGN:  ActionTier.APPROVE,
    ActionType.PAUSE_ADSET:        ActionTier.APPROVE,
    ActionType.ACTIVATE_ADSET:     ActionTier.APPROVE,
    ActionType.UPDATE_TARGETING:   ActionTier.APPROVE,
    ActionType.DUPLICATE_CAMPAIGN: ActionTier.APPROVE,

    # Tier 3 — restricted
    ActionType.DELETE_CAMPAIGN:    ActionTier.RESTRICTED,
    ActionType.REMOVE_CLIENT:      ActionTier.RESTRICTED,
    ActionType.OVERRIDE_BUDGET_CAP: ActionTier.RESTRICTED,
    ActionType.DISABLE_SAFETY_RULE: ActionTier.RESTRICTED,
}


# ── Policy violations ──────────────────────────────────────────────────────────


class PolicyViolation(Exception):
    """Raised when an action breaks a safety rule."""


# ── Policy engine ──────────────────────────────────────────────────────────────


class ApprovalPolicy:
    """Checks actions against safety config and cool-down history."""

    def __init__(self, safety_config: dict):
        self._cfg = safety_config
        # In-memory cool-down tracker: (client_id, action_type) → last rejection time
        self._cooldowns: dict[tuple[str, ActionType], datetime] = {}

    # ── Tier classification ────────────────────────────────────────────────

    @staticmethod
    def classify(action_type: ActionType) -> ActionTier:
        """Return the tier for a given action type."""
        return _TIER_MAP.get(action_type, ActionTier.APPROVE)

    # ── Safety checks ──────────────────────────────────────────────────────

    def check(self, action: PendingAction, history: list[PendingAction]) -> None:
        """Raise PolicyViolation if the action breaks any safety rule.

        Args:
            action: The action being proposed.
            history: All previous actions for this client (used for rate limits).

        Raises:
            PolicyViolation: With a human-readable message explaining the block.
        """
        self._check_spend_limit(action)
        self._check_campaign_creation_limit(action, history)
        self._check_budget_change_size(action)
        self._check_cooldown(action)
        self._check_tier3_restrictions(action)

    def _check_spend_limit(self, action: PendingAction) -> None:
        """Block actions that exceed the per-client daily spend cap."""
        limit = self._cfg.get("spend_limits", {}).get("max_daily_spend_per_client", 50000)
        budget = action.payload.get("daily_budget") or action.payload.get("new_daily_budget")
        if budget and float(budget) > limit:
            raise PolicyViolation(
                f"Proposed budget ₹{budget:,.0f}/day exceeds max daily spend "
                f"₹{limit:,.0f} for this client."
            )

    def _check_budget_change_size(self, action: PendingAction) -> None:
        """Block single budget changes larger than the configured max."""
        if action.action_type != ActionType.UPDATE_BUDGET:
            return
        max_change = self._cfg.get("spend_limits", {}).get("max_single_budget_change", 10000)
        old = float(action.payload.get("old_budget", 0))
        new = float(action.payload.get("new_daily_budget", 0))
        delta = abs(new - old)
        if delta > max_change:
            raise PolicyViolation(
                f"Budget change of ₹{delta:,.0f} exceeds single-change limit "
                f"of ₹{max_change:,.0f}. Split into smaller steps."
            )

    def _check_campaign_creation_limit(
        self, action: PendingAction, history: list[PendingAction]
    ) -> None:
        """Block if too many campaigns created today."""
        if action.action_type != ActionType.CREATE_CAMPAIGN:
            return
        max_per_day = self._cfg.get("spend_limits", {}).get("max_new_campaigns_per_day", 5)
        today = datetime.now(timezone.utc).date()
        created_today = sum(
            1
            for a in history
            if a.action_type == ActionType.CREATE_CAMPAIGN
            and a.client_id == action.client_id
            and a.status in (ActionStatus.APPROVED, ActionStatus.EXECUTED)
            and a.created_at.date() == today
        )
        if created_today >= max_per_day:
            raise PolicyViolation(
                f"Already created {created_today} campaigns today for "
                f"{action.client_id}. Daily limit is {max_per_day}."
            )

    def _check_cooldown(self, action: PendingAction) -> None:
        """Block if the same action was rejected recently (cool-down window)."""
        cool_min = self._cfg.get("approval", {}).get("cool_down_after_reject_minutes", 60)
        key = (action.client_id, action.action_type)
        last_reject = self._cooldowns.get(key)
        if last_reject:
            elapsed = (datetime.now(timezone.utc) - last_reject).total_seconds() / 60
            if elapsed < cool_min:
                remaining = cool_min - elapsed
                raise PolicyViolation(
                    f"This action was rejected {elapsed:.0f} min ago. "
                    f"Cool-down: {remaining:.0f} min remaining."
                )

    def _check_tier3_restrictions(self, action: PendingAction) -> None:
        """Enforce absolute Tier 3 restrictions from config."""
        restrictions = self._cfg.get("restrictions", {})
        if action.action_type == ActionType.DELETE_CAMPAIGN:
            if restrictions.get("never_delete_without_admin", True):
                if action.tier != ActionTier.RESTRICTED:
                    raise PolicyViolation(
                        "Campaign deletion requires Tier 3 (admin) privileges."
                    )
        if action.action_type == ActionType.DISABLE_SAFETY_RULE:
            if restrictions.get("never_disable_safety_rules", True):
                raise PolicyViolation(
                    "Safety rules cannot be disabled through the action system."
                )
        if action.action_type == ActionType.OVERRIDE_BUDGET_CAP:
            if restrictions.get("never_override_budget_caps", True):
                raise PolicyViolation(
                    "Budget caps cannot be overridden through the action system."
                )

    # ── Cool-down tracking ─────────────────────────────────────────────────

    def record_rejection(self, action: PendingAction) -> None:
        """Call this when an action is rejected to start the cool-down clock."""
        key = (action.client_id, action.action_type)
        self._cooldowns[key] = datetime.now(timezone.utc)
        logger.info(
            "Cool-down started for (%s, %s)", action.client_id, action.action_type
        )

    def clear_cooldown(self, client_id: str, action_type: ActionType) -> None:
        """Manually clear a cool-down (e.g. if situation changes)."""
        self._cooldowns.pop((client_id, action_type), None)

    # ── Require-approval threshold ─────────────────────────────────────────

    def requires_approval(self, action: PendingAction) -> bool:
        """Return True if this action must wait for human review.

        Tier 1 actions are auto-approved.
        Tier 2/3 actions always require approval.
        Also forces approval if the budget exceeds the require_approval_above threshold.
        """
        if action.tier == ActionTier.AUTO:
            return False

        # Extra check: even low-tier actions need approval if spend is high
        threshold = self._cfg.get("spend_limits", {}).get("require_approval_above", 5000)
        budget = action.payload.get("daily_budget") or action.payload.get("new_daily_budget")
        if budget and float(budget) > threshold:
            return True

        return action.tier in (ActionTier.APPROVE, ActionTier.RESTRICTED)
