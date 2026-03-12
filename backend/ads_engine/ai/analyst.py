"""Performance analyst — analyze PerformanceReports and suggest actions.

Called by the scheduler every hour to surface anomalies and produce a
ranked list of suggested PendingActions for human review.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from ..models.base import PerformanceReport, Platform
from .client import complete
from .context import build_system_prompt

logger = logging.getLogger(__name__)

_ANALYST_SUFFIX = """
ANALYSIS FORMAT
===============
Respond ONLY with valid JSON (no markdown, no prose outside the JSON):
{
  "summary": "2-3 sentence overview of overall performance",
  "winners": ["entity name — metric highlight", ...],
  "underperformers": ["entity name — problem description", ...],
  "anomalies": ["anomaly description", ...],
  "recommended_actions": [
    {
      "action_type": "PAUSE_ADSET|UPDATE_BUDGET|...",
      "entity_id": "exact_id",
      "entity_name": "human name",
      "reason": "specific data-backed reason",
      "estimated_impact": "quantified expected outcome"
    }
  ]
}
"""


def analyze_performance(
    client_id: str,
    platform: Platform,
    reports: list[PerformanceReport],
) -> dict:
    """Analyze performance reports and return a structured insight dict.

    Args:
        client_id: Used to inject client context into the prompt.
        platform: The ad platform the reports came from.
        reports: List of PerformanceReport objects to analyze.

    Returns:
        Dict with keys: summary, winners, underperformers, anomalies, recommended_actions.
        Falls back gracefully if Claude returns non-JSON.
    """
    system = build_system_prompt(client_id) + _ANALYST_SUFFIX

    reports_json = json.dumps(
        [r.model_dump(mode="json") for r in reports],
        indent=2,
        default=str,
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"Analyze these {platform.value} ad performance reports for {client_id} "
                f"and return your analysis as JSON:\n\n{reports_json}"
            ),
        }
    ]

    raw = complete(system, messages)
    return _parse_analysis(raw)


def _parse_analysis(text: str) -> dict:
    """Parse JSON from the analyst response. Strips markdown fences if present."""
    text = text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[Analyst] Non-JSON response from Claude, using fallback")
        return {
            "summary": text,
            "winners": [],
            "underperformers": [],
            "anomalies": [],
            "recommended_actions": [],
        }
