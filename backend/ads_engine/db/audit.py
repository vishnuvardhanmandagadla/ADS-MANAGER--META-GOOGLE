"""Immutable audit log — Phase 10.

Every spend-affecting action is recorded here: who queued it, who approved
or rejected it, when it executed, and any anomalies the safety engine raised.

Storage: append-only JSONL file at data/audit.jsonl
Each line is a JSON-serialised AuditEntry. Lines are never modified or deleted.
Retention is enforced by truncating entries older than `retention_days` on load.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "audit.jsonl"
_DEFAULT_RETENTION_DAYS = 365

# ── Event types ────────────────────────────────────────────────────────────────

ACTION_QUEUED        = "ACTION_QUEUED"
ACTION_APPROVED      = "ACTION_APPROVED"
ACTION_REJECTED      = "ACTION_REJECTED"
ACTION_EXECUTED      = "ACTION_EXECUTED"
ACTION_FAILED        = "ACTION_FAILED"
ACTION_EXPIRED       = "ACTION_EXPIRED"
ACTION_CANCELLED     = "ACTION_CANCELLED"
TIER3_ATTEMPTED      = "TIER3_ATTEMPTED"   # Tier 3 blocked for non-admin
ANOMALY_DETECTED     = "ANOMALY_DETECTED"  # CPC spike / spend overrun
POLICY_VIOLATION     = "POLICY_VIOLATION"  # PolicyViolation raised pre-enqueue


# ── Entry model ────────────────────────────────────────────────────────────────


class AuditEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    client_id: str
    action_id: Optional[str] = None
    action_type: Optional[str] = None
    platform: Optional[str] = None
    tier: Optional[int] = None
    description: Optional[str] = None
    actor: Optional[str] = None       # username or "whatsapp_webhook" or "system"
    reason: Optional[str] = None      # rejection reason / anomaly detail
    extra: dict = Field(default_factory=dict)


# ── Audit log ──────────────────────────────────────────────────────────────────


class AuditLog:
    """Append-only JSONL audit store.

    Thread/asyncio safe for single-process use (all writes are synchronous
    file appends — atomic on POSIX; acceptable for this use case).
    """

    def __init__(
        self,
        path: Path = _DEFAULT_PATH,
        retention_days: int = _DEFAULT_RETENTION_DAYS,
    ):
        self._path = path
        self._retention_days = retention_days
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Trim old entries on startup
        self._trim()

    # ── Write ─────────────────────────────────────────────────────────────────

    def log(self, entry: AuditEntry) -> AuditEntry:
        """Append an entry to the log. Returns the entry (with id/timestamp set)."""
        try:
            line = entry.model_dump_json() + "\n"
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as exc:
            logger.error("Audit log write failed: %s", exc)
        return entry

    def log_event(
        self,
        event_type: str,
        client_id: str,
        *,
        action_id: Optional[str] = None,
        action_type: Optional[str] = None,
        platform: Optional[str] = None,
        tier: Optional[int] = None,
        description: Optional[str] = None,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> AuditEntry:
        """Convenience wrapper — build and log an AuditEntry in one call."""
        entry = AuditEntry(
            event_type=event_type,
            client_id=client_id,
            action_id=action_id,
            action_type=action_type,
            platform=platform,
            tier=tier,
            description=description,
            actor=actor,
            reason=reason,
            extra=extra or {},
        )
        return self.log(entry)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_recent(
        self,
        limit: int = 50,
        client_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> list[AuditEntry]:
        """Return recent audit entries, newest first.

        Args:
            limit:      Max number of entries to return.
            client_id:  Filter to a specific client.
            event_type: Filter to a specific event type.
        """
        entries: list[AuditEntry] = []
        try:
            if not self._path.exists():
                return []
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = AuditEntry.model_validate_json(line)
                        if client_id and entry.client_id != client_id:
                            continue
                        if event_type and entry.event_type != event_type:
                            continue
                        entries.append(entry)
                    except Exception:
                        pass  # skip malformed lines
        except Exception as exc:
            logger.error("Audit log read failed: %s", exc)

        # Newest first
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def count(self, client_id: Optional[str] = None) -> int:
        """Return total entry count (optionally filtered by client)."""
        return len(self.get_recent(limit=100_000, client_id=client_id))

    # ── Maintenance ───────────────────────────────────────────────────────────

    def _trim(self) -> None:
        """Remove entries older than retention_days. Called at startup."""
        if not self._path.exists():
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        kept: list[str] = []
        removed = 0
        try:
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        ts = datetime.fromisoformat(data["timestamp"])
                        if ts >= cutoff:
                            kept.append(line)
                        else:
                            removed += 1
                    except Exception:
                        kept.append(line)  # keep lines we can't parse
            if removed:
                with open(self._path, "w", encoding="utf-8") as f:
                    f.write("\n".join(kept) + ("\n" if kept else ""))
                logger.info("Audit log: trimmed %d entries older than %d days", removed, self._retention_days)
        except Exception as exc:
            logger.warning("Audit log trim failed: %s", exc)


# ── Singleton ──────────────────────────────────────────────────────────────────

_audit_log: Optional[AuditLog] = None


def init_audit_log(
    path: Path = _DEFAULT_PATH,
    retention_days: int = _DEFAULT_RETENTION_DAYS,
) -> AuditLog:
    """Call once at app startup."""
    global _audit_log
    _audit_log = AuditLog(path=path, retention_days=retention_days)
    return _audit_log


def get_audit_log() -> AuditLog:
    """Return the singleton. Raises if not yet initialised."""
    if _audit_log is None:
        raise RuntimeError(
            "AuditLog not initialised — call init_audit_log() at startup"
        )
    return _audit_log
