"""Client routes — list clients and their platform configs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...core.config import get_client_config, list_clients
from ..deps import check_client_access, get_current_user
from ..schemas import ClientSummary

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientSummary])
async def get_clients(user: dict = Depends(get_current_user)):
    """List all clients the current user has access to."""
    client_ids = list_clients()
    result = []
    for cid in client_ids:
        # Filter by user access
        if "*" not in user["client_ids"] and cid not in user["client_ids"]:
            continue
        try:
            cfg = get_client_config(cid)
            platforms_enabled = [
                p for p, v in cfg.get("platforms", {}).items()
                if v.get("enabled", False)
            ]
            result.append(ClientSummary(
                client_id=cid,
                name=cfg.get("name", cid),
                currency=cfg.get("currency", "INR"),
                platforms_enabled=platforms_enabled,
                max_daily_spend=cfg.get("spend_limits", {}).get("max_daily_spend"),
            ))
        except FileNotFoundError:
            continue
    return result


@router.get("/{client_id}", response_model=ClientSummary)
async def get_client(client_id: str, user: dict = Depends(get_current_user)):
    """Get a single client's config summary."""
    check_client_access(user, client_id)
    try:
        cfg = get_client_config(client_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")

    platforms_enabled = [
        p for p, v in cfg.get("platforms", {}).items()
        if v.get("enabled", False)
    ]
    return ClientSummary(
        client_id=client_id,
        name=cfg.get("name", client_id),
        currency=cfg.get("currency", "INR"),
        platforms_enabled=platforms_enabled,
        max_daily_spend=cfg.get("spend_limits", {}).get("max_daily_spend"),
    )
