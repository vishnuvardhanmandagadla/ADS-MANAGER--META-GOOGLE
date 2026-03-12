"""Safety engine — runtime anomaly detection.

Monitors live campaign metrics against the thresholds in config/safety.yaml
and raises anomaly alerts when:
  - CPC spikes more than `cpc_spike_threshold_pct`% above the 7-day average
  - Daily spend hits more than `spend_overrun_threshold_pct`% of budget

When an anomaly is detected the engine produces a suggested PendingAction
(pause_campaign) that goes through the normal approval queue.
Setting `auto_approve_pause_on_anomaly: false` in safety.yaml means even
anomaly-triggered pauses need a human ✅.

This is separate from ApprovalPolicy (policies.py) which handles pre-flight
checks before an action enters the queue.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class CampaignMetrics:
    """Minimal metrics snapshot passed to the safety engine."""
    campaign_id: str
    campaign_name: str
    client_id: str
    platform: str                    # "meta" | "google"
    daily_budget: float              # ₹
    spend_today: float               # ₹ spent so far today
    current_cpc: float               # ₹ CPC in the current window
    avg_cpc_7day: float              # ₹ 7-day average CPC (0 = no history)


@dataclass
class AnomalyResult:
    """Returned by SafetyEngine when an anomaly is detected."""
    campaign_id: str
    campaign_name: str
    client_id: str
    platform: str
    anomaly_type: str        # "CPC_SPIKE" | "SPEND_OVERRUN"
    detail: str              # Human-readable explanation
    severity: str            # "warning" | "critical"
    suggested_action: str    # "pause_campaign"
    metric_value: float      # The triggering metric value
    threshold_value: float   # The threshold that was breached


# ── Engine ────────────────────────────────────────────────────────────────────


class SafetyEngine:
    """Evaluates live campaign metrics against safety.yaml thresholds."""

    def __init__(self, safety_config: dict):
        anomaly_cfg = safety_config.get("anomaly_detection", {})
        self._cpc_spike_enabled: bool = anomaly_cfg.get(
            "auto_pause_on_cpc_spike", True
        )
        self._cpc_spike_pct: float = float(
            anomaly_cfg.get("cpc_spike_threshold_pct", 200)
        )
        self._spend_overrun_enabled: bool = anomaly_cfg.get(
            "auto_pause_on_spend_overrun", True
        )
        self._spend_overrun_pct: float = float(
            anomaly_cfg.get("spend_overrun_threshold_pct", 120)
        )

    # ── Individual checks ─────────────────────────────────────────────────────

    def check_cpc_spike(
        self,
        current_cpc: float,
        avg_7day_cpc: float,
    ) -> tuple[bool, float]:
        """Check if CPC has spiked beyond the threshold.

        Returns:
            (is_spike, pct_above_avg) — pct_above_avg is 0 if no history.
        """
        if not self._cpc_spike_enabled:
            return False, 0.0
        if avg_7day_cpc <= 0:
            return False, 0.0  # no baseline — can't determine a spike

        pct_above = ((current_cpc - avg_7day_cpc) / avg_7day_cpc) * 100
        is_spike = pct_above >= self._cpc_spike_pct
        return is_spike, pct_above

    def check_spend_overrun(
        self,
        spend_today: float,
        daily_budget: float,
    ) -> tuple[bool, float]:
        """Check if today's spend has exceeded the overrun threshold.

        Returns:
            (is_overrun, pct_of_budget) — e.g. (True, 125.0)
        """
        if not self._spend_overrun_enabled:
            return False, 0.0
        if daily_budget <= 0:
            return False, 0.0

        pct_of_budget = (spend_today / daily_budget) * 100
        is_overrun = pct_of_budget >= self._spend_overrun_pct
        return is_overrun, pct_of_budget

    # ── Batch evaluation ──────────────────────────────────────────────────────

    def evaluate(self, campaigns: list[CampaignMetrics]) -> list[AnomalyResult]:
        """Evaluate a list of campaign metrics and return all anomalies found."""
        anomalies: list[AnomalyResult] = []

        for c in campaigns:
            # CPC spike
            is_spike, pct_above = self.check_cpc_spike(c.current_cpc, c.avg_cpc_7day)
            if is_spike:
                detail = (
                    f"CPC ₹{c.current_cpc:.2f} is {pct_above:.0f}% above the "
                    f"7-day avg ₹{c.avg_cpc_7day:.2f} "
                    f"(threshold: {self._cpc_spike_pct:.0f}%)"
                )
                logger.warning(
                    "[SafetyEngine] CPC spike — %s / %s: %s",
                    c.client_id, c.campaign_name, detail,
                )
                anomalies.append(AnomalyResult(
                    campaign_id=c.campaign_id,
                    campaign_name=c.campaign_name,
                    client_id=c.client_id,
                    platform=c.platform,
                    anomaly_type="CPC_SPIKE",
                    detail=detail,
                    severity="critical" if pct_above >= self._cpc_spike_pct * 1.5 else "warning",
                    suggested_action="pause_campaign",
                    metric_value=c.current_cpc,
                    threshold_value=c.avg_cpc_7day * (1 + self._cpc_spike_pct / 100),
                ))

            # Spend overrun
            is_overrun, pct_of_budget = self.check_spend_overrun(
                c.spend_today, c.daily_budget
            )
            if is_overrun:
                detail = (
                    f"Spend ₹{c.spend_today:,.0f} is {pct_of_budget:.0f}% of the "
                    f"₹{c.daily_budget:,.0f} daily budget "
                    f"(threshold: {self._spend_overrun_pct:.0f}%)"
                )
                logger.warning(
                    "[SafetyEngine] Spend overrun — %s / %s: %s",
                    c.client_id, c.campaign_name, detail,
                )
                anomalies.append(AnomalyResult(
                    campaign_id=c.campaign_id,
                    campaign_name=c.campaign_name,
                    client_id=c.client_id,
                    platform=c.platform,
                    anomaly_type="SPEND_OVERRUN",
                    detail=detail,
                    severity="critical" if pct_of_budget >= 150 else "warning",
                    suggested_action="pause_campaign",
                    metric_value=c.spend_today,
                    threshold_value=c.daily_budget * self._spend_overrun_pct / 100,
                ))

        return anomalies
