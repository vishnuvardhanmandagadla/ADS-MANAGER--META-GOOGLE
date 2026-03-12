"""Approval queue — stores and manages all PendingActions.

Phase 3: in-memory store with JSON file persistence so actions survive restarts.
Phase 6: will be replaced with a proper PostgreSQL-backed store.

The queue is a singleton — import and use `approval_queue` directly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .action import ActionStatus, ActionType, PendingAction
from .policies import ApprovalPolicy, PolicyViolation

logger = logging.getLogger(__name__)

# Persist queue to this file between restarts (Phase 6 replaces with DB)
_QUEUE_FILE = Path(__file__).resolve().parents[3] / "data" / "approval_queue.json"


class ApprovalQueue:
    """Thread-safe (asyncio-safe) in-memory approval queue with file persistence."""

    def __init__(self, policy: ApprovalPolicy, persist_path: Path = _QUEUE_FILE):
        self._actions: dict[str, PendingAction] = {}
        self._policy = policy
        self._persist_path = persist_path
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._persist_path.exists():
            return
        try:
            raw = json.loads(self._persist_path.read_text(encoding="utf-8"))
            for item in raw:
                action = PendingAction.model_validate(item)
                self._actions[action.id] = action
            logger.info("Loaded %d actions from queue file", len(self._actions))
        except Exception as exc:
            logger.warning("Could not load queue file: %s", exc)

    def _save(self) -> None:
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = [a.model_dump(mode="json") for a in self._actions.values()]
            self._persist_path.write_text(
                json.dumps(data, default=str, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.error("Could not save queue file: %s", exc)

    # ── Write operations ───────────────────────────────────────────────────

    def enqueue(self, action: PendingAction) -> PendingAction:
        """Add an action to the queue after policy checks.

        Raises:
            PolicyViolation: If the action breaks a safety rule.
        """
        history = list(self._actions.values())
        self._policy.check(action, history)

        self._actions[action.id] = action
        self._save()

        tier_label = {1: "AUTO", 2: "PENDING APPROVAL", 3: "PENDING ADMIN APPROVAL"}
        logger.info(
            "[QUEUE] Enqueued %s — %s [%s]",
            action.action_type, action.description, tier_label.get(action.tier, "?"),
        )
        return action

    def approve(self, action_id: str, reviewer: str) -> PendingAction:
        """Mark an action as approved.

        Args:
            action_id: The action UUID.
            reviewer: Username of the person approving.

        Raises:
            KeyError: If action not found.
            ValueError: If action is in a terminal state.
        """
        action = self._get_or_raise(action_id)
        action.approve(reviewer)
        self._save()
        logger.info(
            "[QUEUE] APPROVED %s ('%s') by %s",
            action.action_type, action.description, reviewer,
        )
        return action

    def reject(self, action_id: str, reviewer: str, reason: str = "") -> PendingAction:
        """Mark an action as rejected and start the cool-down clock."""
        action = self._get_or_raise(action_id)
        action.reject(reviewer, reason)
        self._policy.record_rejection(action)
        self._save()
        logger.info(
            "[QUEUE] REJECTED %s ('%s') by %s — %s",
            action.action_type, action.description, reviewer, reason,
        )
        return action

    def mark_executed(self, action_id: str) -> PendingAction:
        """Called by executor after successful platform API call."""
        action = self._get_or_raise(action_id)
        action.mark_executed()
        self._save()
        logger.info(
            "[QUEUE] EXECUTED %s ('%s')", action.action_type, action.description
        )
        return action

    def mark_failed(self, action_id: str, error: str) -> PendingAction:
        """Called by executor when the platform API call throws."""
        action = self._get_or_raise(action_id)
        action.mark_failed(error)
        self._save()
        logger.error(
            "[QUEUE] FAILED %s ('%s') — %s", action.action_type, action.description, error
        )
        return action

    def cancel(self, action_id: str) -> PendingAction:
        """Withdraw a pending action before it's reviewed."""
        action = self._get_or_raise(action_id)
        if action.status != ActionStatus.PENDING:
            raise ValueError(f"Can only cancel PENDING actions, not {action.status}")
        action.status = ActionStatus.CANCELLED
        self._save()
        return action

    # ── Maintenance ────────────────────────────────────────────────────────

    def expire_old(self) -> int:
        """Mark all expired pending actions. Returns count expired."""
        count = 0
        for action in self._actions.values():
            if action.is_expired:
                action.mark_expired()
                count += 1
        if count:
            self._save()
            logger.info("[QUEUE] Expired %d stale actions", count)
        return count

    # ── Read operations ────────────────────────────────────────────────────

    def get(self, action_id: str) -> Optional[PendingAction]:
        return self._actions.get(action_id)

    def list_pending(self, client_id: Optional[str] = None) -> list[PendingAction]:
        """All actions awaiting human review, newest first."""
        actions = [
            a for a in self._actions.values()
            if a.status == ActionStatus.PENDING
            and (client_id is None or a.client_id == client_id)
        ]
        return sorted(actions, key=lambda a: a.created_at, reverse=True)

    def list_all(
        self,
        client_id: Optional[str] = None,
        status: Optional[ActionStatus] = None,
        limit: int = 100,
    ) -> list[PendingAction]:
        """All actions with optional filters, newest first."""
        actions = [
            a for a in self._actions.values()
            if (client_id is None or a.client_id == client_id)
            and (status is None or a.status == status)
        ]
        return sorted(actions, key=lambda a: a.created_at, reverse=True)[:limit]

    def pending_count(self, client_id: Optional[str] = None) -> int:
        return len(self.list_pending(client_id))

    # ── Private ────────────────────────────────────────────────────────────

    def _get_or_raise(self, action_id: str) -> PendingAction:
        action = self._actions.get(action_id)
        if not action:
            raise KeyError(f"Action '{action_id}' not found in queue")
        return action


# ── Singleton — initialised in main.py lifespan ───────────────────────────────
# Import this in other modules:
#   from ads_engine.approval.queue import approval_queue

approval_queue: Optional[ApprovalQueue] = None


def init_queue(policy: ApprovalPolicy, persist_path: Path = _QUEUE_FILE) -> ApprovalQueue:
    """Call once at app startup."""
    global approval_queue
    approval_queue = ApprovalQueue(policy, persist_path)
    return approval_queue
