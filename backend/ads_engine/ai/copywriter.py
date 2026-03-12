"""Ad copy generator — produce headline + body variations for a given audience.

Phase 5: generates copy suggestions as text. Phase 7 will wire this into
the frontend's AI Chat page so users can request copy directly.
"""

from __future__ import annotations

import json
import logging

from .client import complete
from .context import build_system_prompt

logger = logging.getLogger(__name__)

_COPY_SUFFIX = """
COPY FORMAT
===========
Respond ONLY with valid JSON:
{
  "variations": [
    {
      "headline": "Short punchy headline (≤40 chars)",
      "body": "Ad body text (≤125 chars)",
      "cta": "Shop Now|Learn More|Book Now|Sign Up|Get Offer",
      "tone": "urgency|curiosity|social_proof|value",
      "notes": "Brief note on why this works for this audience"
    }
  ]
}
"""


def generate_copy(
    client_id: str,
    product: str,
    audience: str,
    count: int = 3,
    existing_copy: str | None = None,
) -> list[dict]:
    """Generate ad copy variations for a product targeting a specific audience.

    Args:
        client_id: Injects client context (brand voice, targets).
        product: What is being advertised (e.g. "Comedy Night at Phoenix Mall").
        audience: Who we're targeting (e.g. "18-35 urban professionals in Chennai").
        count: How many variations to generate.
        existing_copy: Optional existing ad copy to improve upon.

    Returns:
        List of dicts with keys: headline, body, cta, tone, notes.
    """
    system = build_system_prompt(client_id) + _COPY_SUFFIX

    existing_section = (
        f"\nExisting copy to improve upon:\n{existing_copy}\n"
        if existing_copy
        else ""
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"Generate {count} ad copy variation(s) for:\n"
                f"Product: {product}\n"
                f"Target audience: {audience}"
                f"{existing_section}"
            ),
        }
    ]

    raw = complete(system, messages)
    return _parse_copy(raw)


def _parse_copy(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
        return data.get("variations", [])
    except json.JSONDecodeError:
        logger.warning("[Copywriter] Non-JSON response from Claude")
        return []
