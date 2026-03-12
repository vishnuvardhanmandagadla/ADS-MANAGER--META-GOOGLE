"""Budget and audience optimizer — suggest spend shifts and targeting changes.

Produces a list of PendingActions (tier 2) that go to the approval queue.
No action is taken automatically.
"""

from __future__ import annotations

import json
import logging

from ..approval.action import PendingAction
from ..models.base import Campaign, AdSet, Platform
from .client import complete
from .context import build_system_prompt
from .chat import _build_pending_action

logger = logging.getLogger(__name__)

_OPTIMIZER_SUFFIX = """
OPTIMIZATION FORMAT
===================
Respond ONLY with valid JSON:
{
  "rationale": "Brief explanation of your optimization strategy",
  "actions": [
    {
      "action_type": "UPDATE_BUDGET|PAUSE_ADSET|ACTIVATE_ADSET|UPDATE_TARGETING|...",
      "description": "Short description of the action",
      "reason": "Data-backed reason",
      "estimated_impact": "Quantified expected outcome",
      "payload": {"key": "value"}
    }
  ]
}
"""


def suggest_optimizations(
    client_id: str,
    platform: Platform,
    campaigns: list[Campaign],
    adsets: list[AdSet] | None = None,
) -> list[PendingAction]:
    """Ask Claude to suggest budget/audience optimizations and return PendingActions.

    Args:
        client_id: Injects client context into the prompt.
        platform: Target ad platform.
        campaigns: Current campaigns to analyze.
        adsets: Optional ad sets for more granular suggestions.

    Returns:
        List of PendingAction objects (all tier 2, awaiting human approval).
    """
    system = build_system_prompt(client_id) + _OPTIMIZER_SUFFIX

    camp_data = json.dumps(
        [c.model_dump(mode="json") for c in campaigns], indent=2, default=str
    )
    adset_data = (
        json.dumps([a.model_dump(mode="json") for a in adsets], indent=2, default=str)
        if adsets
        else "Not provided"
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"Suggest budget and audience optimizations for {client_id} on {platform.value}.\n\n"
                f"Campaigns:\n{camp_data}\n\n"
                f"Ad Sets:\n{adset_data}"
            ),
        }
    ]

    raw = complete(system, messages)
    action_dicts = _parse_optimizer(raw)

    actions: list[PendingAction] = []
    for raw_action in action_dicts:
        try:
            action = _build_pending_action(raw_action, client_id, platform)
            actions.append(action)
        except Exception as exc:
            logger.warning("[Optimizer] Skipping malformed action %s: %s", raw_action, exc)

    logger.info("[Optimizer] Suggested %d action(s) for %s", len(actions), client_id)
    return actions


def _parse_optimizer(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
        return data.get("actions", [])
    except json.JSONDecodeError:
        logger.warning("[Optimizer] Non-JSON response from Claude")
        return []
