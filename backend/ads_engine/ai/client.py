"""Thin wrapper around the Anthropic SDK.

All AI modules import `complete()` from here so we have one place to swap models,
add retries, or inject observability.
"""

from __future__ import annotations

import logging

from anthropic import Anthropic

from ..core.config import get_app_config, get_settings

logger = logging.getLogger(__name__)


def get_claude_client() -> Anthropic:
    settings = get_settings()
    return Anthropic(api_key=settings.anthropic_api_key)


def complete(
    system: str,
    messages: list[dict],
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """Send messages to Claude and return the text response.

    Args:
        system: System prompt (injected with client context by callers).
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
        model: Override the model from settings.yaml.
        max_tokens: Override max_tokens from settings.yaml.

    Returns:
        The assistant's text response.
    """
    config = get_app_config()
    ai_cfg = config.get("ai", {})
    model = model or ai_cfg.get("model", "claude-sonnet-4-6")
    max_tokens = max_tokens or ai_cfg.get("max_tokens", 4096)

    client = get_claude_client()

    logger.debug("[AI] Sending %d message(s) to %s", len(messages), model)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )

    text = response.content[0].text
    logger.debug("[AI] Response: %d chars", len(text))
    return text
