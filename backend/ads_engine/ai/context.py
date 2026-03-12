"""Build system prompts enriched with client context.

Every AI module calls `build_system_prompt(client_id)` to get a prompt that
includes the client's business context, audience, spend limits, and targets.
"""

from __future__ import annotations

from ..core.config import get_client_config

_BASE = """\
You are an expert digital advertising analyst and strategist managing ad campaigns \
on Meta (Facebook/Instagram) and Google Ads for an agency.

Your job is to analyze performance data, identify opportunities, and suggest \
specific optimizations. All amounts are in INR (Indian Rupees).

CRITICAL RULES:
1. Never execute anything directly — always propose actions for human review and approval.
2. Be specific: include exact entity IDs, campaign names, and budget amounts.
3. Be conservative — prefer pausing over deleting; prefer small budget changes over large ones.
4. Always explain WHY you are suggesting an action and what impact it will have.
5. When uncertain, recommend gathering more data before acting.
6. Suggest only actions the system supports: CREATE_CAMPAIGN, CREATE_ADSET, CREATE_AD, \
UPDATE_BUDGET, PAUSE_CAMPAIGN, ACTIVATE_CAMPAIGN, PAUSE_ADSET, ACTIVATE_ADSET, \
UPDATE_TARGETING, DUPLICATE_CAMPAIGN, DELETE_CAMPAIGN.\
"""


def build_system_prompt(client_id: str) -> str:
    """Build a system prompt with client-specific context injected.

    Falls back to a minimal prompt if the client config is not found.
    """
    try:
        cfg = get_client_config(client_id)
        name = cfg.get("name", client_id)
        currency = cfg.get("currency", "INR")
        industry = cfg.get("industry", "")
        ai_ctx = cfg.get("ai_context", "")
        limits = cfg.get("spend_limits", {})

        context = f"""

CLIENT CONTEXT
==============
Client ID : {client_id}
Name      : {name}
Industry  : {industry}
Currency  : {currency}

Business & Audience Context:
{ai_ctx.strip() if ai_ctx else "No context provided."}

Spend Limits:
- Max daily spend      : {currency} {limits.get("max_daily_spend", "not set")}
- Max single change    : {currency} {limits.get("max_single_budget_change", "not set")}
"""
    except FileNotFoundError:
        context = f"\nCLIENT: {client_id} (no config found — use generic best practices)\n"

    return _BASE + context
