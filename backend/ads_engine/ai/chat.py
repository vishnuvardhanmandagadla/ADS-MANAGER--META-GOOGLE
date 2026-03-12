"""Conversational AI interface — natural language → approval queue actions.

Usage:
    session = ChatSession(client_id="tickets99")
    result = session.chat("Pause the underperforming ad sets", queue=queue)
    print(result.message)
    print(f"Queued {len(result.queued_actions)} action(s) for approval")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..approval.action import ActionStatus, ActionType, PendingAction
from ..approval.queue import ApprovalQueue
from ..models.base import Platform
from .client import complete
from .context import build_system_prompt

logger = logging.getLogger(__name__)

# Appended to every ChatSession system prompt to teach Claude the action format
_ACTION_FORMAT = """
PROPOSING ACTIONS
=================
When the user asks you to take an action (pause, create, update budgets, etc.):
1. Explain what you would do and why in plain language.
2. End your response with a JSON block containing the proposed actions.

Format:
```json
{
  "proposed_actions": [
    {
      "action_type": "PAUSE_ADSET",
      "platform": "meta",
      "description": "Pause AdSet 'Broad Audience' (ID: ads_001)",
      "reason": "CPC ₹9.50 is 3x above the ₹3.00 target",
      "estimated_impact": "Save ~₹3,000/day, reduces wasted spend",
      "payload": {"adset_id": "ads_001"}
    }
  ]
}
```

Supported action_type values: CREATE_CAMPAIGN, CREATE_ADSET, CREATE_AD,
UPDATE_BUDGET, PAUSE_CAMPAIGN, ACTIVATE_CAMPAIGN, PAUSE_ADSET, ACTIVATE_ADSET,
UPDATE_TARGETING, DUPLICATE_CAMPAIGN, DELETE_CAMPAIGN,
GET_CAMPAIGNS, GET_ADSETS, GET_ADS, GET_PERFORMANCE.

If you are just answering a question with no actions needed, omit the JSON block entirely.
"""

# Maps action_type string → ActionType enum
_ACTION_TYPE_MAP: dict[str, ActionType] = {t.value: t for t in ActionType}

_TIER3 = {
    ActionType.DELETE_CAMPAIGN,
    ActionType.REMOVE_CLIENT,
    ActionType.OVERRIDE_BUDGET_CAP,
    ActionType.DISABLE_SAFETY_RULE,
}
_TIER1 = {
    ActionType.GET_CAMPAIGNS,
    ActionType.GET_ADSETS,
    ActionType.GET_ADS,
    ActionType.GET_PERFORMANCE,
}


@dataclass
class ChatMessage:
    role: str   # "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    message: str                                        # display text (JSON block stripped)
    proposed_actions: list[dict] = field(default_factory=list)   # raw dicts from Claude
    queued_actions: list[PendingAction] = field(default_factory=list)  # enqueued actions


class ChatSession:
    """Stateful conversation with the AI analyst for one client.

    Each session keeps its own message history so follow-up questions work
    naturally ("make that budget change I mentioned larger" etc.).
    """

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self._history: list[ChatMessage] = []
        self._system = build_system_prompt(client_id) + _ACTION_FORMAT

    # ── Public API ─────────────────────────────────────────────────────────

    def chat(
        self,
        user_message: str,
        platform: Platform = Platform.META,
        auto_queue: bool = True,
        queue: Optional[ApprovalQueue] = None,
    ) -> ChatResponse:
        """Send a user message and get an AI response.

        Args:
            user_message: What the user typed.
            platform: Target ad platform (used when building PendingActions).
            auto_queue: If True and queue is provided, auto-enqueue proposed actions.
            queue: The ApprovalQueue to enqueue actions into.

        Returns:
            ChatResponse with the message text and any queued actions.
        """
        self._history.append(ChatMessage(role="user", content=user_message))

        messages = [{"role": m.role, "content": m.content} for m in self._history]
        response_text = complete(self._system, messages)

        self._history.append(ChatMessage(role="assistant", content=response_text))

        proposed = _extract_proposed_actions(response_text)
        queued: list[PendingAction] = []

        if auto_queue and queue and proposed:
            for raw in proposed:
                try:
                    action = _build_pending_action(raw, self.client_id, platform)
                    queue.enqueue(action)
                    queued.append(action)
                    logger.info(
                        "[AI] Queued %s for client %s", action.action_type, self.client_id
                    )
                except Exception as exc:
                    logger.warning("[AI] Could not queue action %s: %s", raw, exc)

        return ChatResponse(
            message=_strip_json_block(response_text),
            proposed_actions=proposed,
            queued_actions=queued,
        )

    def clear(self) -> None:
        """Reset conversation history (keeps system prompt)."""
        self._history.clear()

    @property
    def history(self) -> list[ChatMessage]:
        return list(self._history)


# ── Private helpers ─────────────────────────────────────────────────────────────


def _extract_proposed_actions(text: str) -> list[dict]:
    """Pull the proposed_actions list from a ```json block in the response."""
    try:
        if "```json" in text:
            json_str = text.split("```json")[1].split("```")[0].strip()
            data = json.loads(json_str)
            return data.get("proposed_actions", [])
    except (json.JSONDecodeError, IndexError):
        pass
    return []


def _strip_json_block(text: str) -> str:
    """Remove the trailing ```json block from the message shown to the user."""
    idx = text.rfind("```json")
    if idx != -1:
        return text[:idx].strip()
    return text.strip()


def _build_pending_action(
    raw: dict,
    client_id: str,
    platform: Platform,
) -> PendingAction:
    """Convert a raw dict (from Claude's JSON) into a PendingAction.

    Raises:
        ValueError: If action_type is not recognised.
    """
    raw_type = raw.get("action_type", "").lower()
    action_type = _ACTION_TYPE_MAP.get(raw_type)
    if action_type is None:
        raise ValueError(f"Unknown action_type: {raw.get('action_type', '')!r}")

    kwargs = dict(
        client_id=client_id,
        platform=platform,
        action_type=action_type,
        description=raw.get("description", ""),
        reason=raw.get("reason", "AI suggested"),
        estimated_impact=raw.get("estimated_impact", "Unknown"),
        payload=raw.get("payload", {}),
    )

    if action_type in _TIER3:
        return PendingAction.tier3(**kwargs)
    if action_type in _TIER1:
        # tier1 only takes client_id, platform, action_type, description, payload
        return PendingAction.tier1(
            client_id=kwargs["client_id"],
            platform=kwargs["platform"],
            action_type=kwargs["action_type"],
            description=kwargs["description"],
            payload=kwargs["payload"],
        )
    return PendingAction.tier2(**kwargs)
