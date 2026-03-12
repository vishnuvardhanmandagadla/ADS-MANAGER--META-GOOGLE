"""Audit log endpoints.

GET  /api/v1/audit          — list recent audit entries (admin only)
POST /api/v1/safety/check   — evaluate campaign metrics for anomalies
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ...core.safety import CampaignMetrics, SafetyEngine
from ...core.config import get_safety_config
from ...db.audit import AuditEntry, get_audit_log
from ..deps import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["audit"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class AuditEntryResponse(BaseModel):
    id: str
    event_type: str
    timestamp: str
    client_id: str
    action_id: Optional[str] = None
    action_type: Optional[str] = None
    platform: Optional[str] = None
    tier: Optional[int] = None
    description: Optional[str] = None
    actor: Optional[str] = None
    reason: Optional[str] = None
    extra: dict = {}


class AuditListResponse(BaseModel):
    total: int
    entries: list[AuditEntryResponse]


class SafetyCheckRequest(BaseModel):
    campaigns: list[dict[str, Any]]


class AnomalyResponse(BaseModel):
    campaign_id: str
    campaign_name: str
    client_id: str
    platform: str
    anomaly_type: str
    detail: str
    severity: str
    suggested_action: str
    metric_value: float
    threshold_value: float


class SafetyCheckResponse(BaseModel):
    anomaly_count: int
    anomalies: list[AnomalyResponse]


def _entry_to_response(entry: AuditEntry) -> AuditEntryResponse:
    return AuditEntryResponse(
        id=entry.id,
        event_type=entry.event_type,
        timestamp=entry.timestamp.isoformat(),
        client_id=entry.client_id,
        action_id=entry.action_id,
        action_type=entry.action_type,
        platform=entry.platform,
        tier=entry.tier,
        description=entry.description,
        actor=entry.actor,
        reason=entry.reason,
        extra=entry.extra,
    )


# ── Audit log ─────────────────────────────────────────────────────────────────


@router.get("/audit", response_model=AuditListResponse)
async def list_audit(
    client_id: Optional[str] = Query(None, description="Filter by client"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_admin),
):
    """Return recent audit log entries. Admin only."""
    try:
        audit = get_audit_log()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit log not initialised",
        )

    entries = audit.get_recent(limit=limit, client_id=client_id, event_type=event_type)
    return AuditListResponse(
        total=len(entries),
        entries=[_entry_to_response(e) for e in entries],
    )


# ── Safety check ──────────────────────────────────────────────────────────────


@router.post("/safety/check", response_model=SafetyCheckResponse)
async def safety_check(
    body: SafetyCheckRequest,
    user: dict = Depends(require_admin),
):
    """Evaluate campaign metrics against safety thresholds.

    Pass a list of campaign metric snapshots; returns any anomalies detected.
    The safety engine does NOT auto-pause — call POST /actions to queue a
    pause_campaign action after reviewing the results.
    """
    safety_cfg = get_safety_config()
    engine = SafetyEngine(safety_cfg)

    metrics = []
    for c in body.campaigns:
        try:
            metrics.append(CampaignMetrics(
                campaign_id=c["campaign_id"],
                campaign_name=c.get("campaign_name", c["campaign_id"]),
                client_id=c["client_id"],
                platform=c.get("platform", "meta"),
                daily_budget=float(c.get("daily_budget", 0)),
                spend_today=float(c.get("spend_today", 0)),
                current_cpc=float(c.get("current_cpc", 0)),
                avg_cpc_7day=float(c.get("avg_cpc_7day", 0)),
            ))
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid campaign entry: {exc}",
            )

    anomalies = engine.evaluate(metrics)

    # Log each anomaly to the audit trail
    try:
        audit = get_audit_log()
        for a in anomalies:
            audit.log_event(
                event_type="ANOMALY_DETECTED",
                client_id=a.client_id,
                platform=a.platform,
                description=a.detail,
                actor=user.get("username", "system"),
                extra={
                    "anomaly_type": a.anomaly_type,
                    "campaign_id": a.campaign_id,
                    "campaign_name": a.campaign_name,
                    "severity": a.severity,
                    "metric_value": a.metric_value,
                    "threshold_value": a.threshold_value,
                },
            )
    except RuntimeError:
        pass  # audit not yet init in tests — non-fatal

    return SafetyCheckResponse(
        anomaly_count=len(anomalies),
        anomalies=[
            AnomalyResponse(
                campaign_id=a.campaign_id,
                campaign_name=a.campaign_name,
                client_id=a.client_id,
                platform=a.platform,
                anomaly_type=a.anomaly_type,
                detail=a.detail,
                severity=a.severity,
                suggested_action=a.suggested_action,
                metric_value=a.metric_value,
                threshold_value=a.threshold_value,
            )
            for a in anomalies
        ],
    )
