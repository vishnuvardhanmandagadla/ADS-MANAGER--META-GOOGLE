"use client";

import { useState } from "react";
import {
  Play,
  Pause,
  IndianRupee,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { createAction, CampaignSummary } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import BudgetModal from "./BudgetModal";

interface CampaignCardProps {
  campaign: CampaignSummary;
  onQueued: () => void;
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-400/10 text-green-400",
  paused: "bg-yellow-400/10 text-yellow-400",
  archived: "bg-gray-500/10 text-gray-500",
  deleted: "bg-red-400/10 text-red-400",
};

function MetricBlock({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className="text-sm font-semibold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500">{sub}</p>}
    </div>
  );
}

export default function CampaignCard({ campaign, onQueued }: CampaignCardProps) {
  const { user } = useAuth();
  const [loading, setLoading] = useState<"pause" | "activate" | null>(null);
  const [showBudget, setShowBudget] = useState(false);
  const [error, setError] = useState("");

  const canAct = user?.role === "admin" || user?.role === "manager";

  const handleToggle = async () => {
    if (!user || !canAct) return;
    const isPausing = campaign.status === "active";
    setLoading(isPausing ? "pause" : "activate");
    setError("");
    try {
      await createAction({
        client_id: campaign.client_id,
        platform: "meta",
        action_type: isPausing ? "pause_campaign" : "activate_campaign",
        description: isPausing
          ? `Pause campaign "${campaign.name}"`
          : `Activate campaign "${campaign.name}"`,
        reason: isPausing
          ? "Manual pause via campaign controls"
          : "Manual activation via campaign controls",
        estimated_impact: isPausing
          ? `Stop ₹${campaign.daily_budget.toLocaleString()}/day spend`
          : `Resume ₹${campaign.daily_budget.toLocaleString()}/day spend`,
        payload: { campaign_id: campaign.id },
      });
      onQueued();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to queue action");
    } finally {
      setLoading(null);
    }
  };

  const roasColor =
    campaign.roas === null
      ? "text-gray-500"
      : campaign.roas >= 3
      ? "text-green-400"
      : campaign.roas >= 1.5
      ? "text-yellow-400"
      : "text-red-400";

  const RoasIcon =
    campaign.roas === null
      ? Minus
      : campaign.roas >= 3
      ? TrendingUp
      : campaign.roas >= 1.5
      ? Minus
      : TrendingDown;

  return (
    <>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-semibold text-white truncate">{campaign.name}</p>
            {campaign.objective && (
              <p className="text-xs text-gray-500 mt-0.5">{campaign.objective}</p>
            )}
          </div>
          <span
            className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
              STATUS_STYLES[campaign.status] ?? STATUS_STYLES.archived
            }`}
          >
            {campaign.status}
          </span>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-gray-800 pt-3">
          <MetricBlock
            label="Daily Budget"
            value={`₹${campaign.daily_budget.toLocaleString()}`}
          />
          <MetricBlock
            label="Spend"
            value={`₹${campaign.spend.toLocaleString()}`}
          />
          <MetricBlock
            label="CPC"
            value={campaign.cpc > 0 ? `₹${campaign.cpc.toFixed(2)}` : "—"}
            sub={`CTR ${campaign.ctr.toFixed(1)}%`}
          />
          <div>
            <p className="text-xs text-gray-500 mb-0.5">ROAS</p>
            <p className={`text-sm font-semibold flex items-center gap-1 ${roasColor}`}>
              <RoasIcon className="w-3.5 h-3.5" />
              {campaign.roas !== null ? `${campaign.roas.toFixed(1)}x` : "—"}
            </p>
            <p className="text-xs text-gray-500">
              {campaign.conversions} conv.
            </p>
          </div>
        </div>

        {/* Actions */}
        {error && (
          <p className="text-xs text-red-400 bg-red-400/10 px-3 py-1.5 rounded-lg">
            {error}
          </p>
        )}

        {canAct && (
          <div className="flex gap-2 border-t border-gray-800 pt-3">
            {(campaign.status === "active" || campaign.status === "paused") && (
              <button
                onClick={handleToggle}
                disabled={loading !== null}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 ${
                  campaign.status === "active"
                    ? "bg-yellow-400/10 text-yellow-400 hover:bg-yellow-400/20"
                    : "bg-green-400/10 text-green-400 hover:bg-green-400/20"
                }`}
              >
                {campaign.status === "active" ? (
                  <>
                    <Pause className="w-3.5 h-3.5" />
                    {loading === "pause" ? "Queuing…" : "Pause"}
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" />
                    {loading === "activate" ? "Queuing…" : "Activate"}
                  </>
                )}
              </button>
            )}

            <button
              onClick={() => setShowBudget(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <IndianRupee className="w-3.5 h-3.5" />
              Edit Budget
            </button>
          </div>
        )}
      </div>

      {showBudget && (
        <BudgetModal
          campaign={campaign}
          onClose={() => setShowBudget(false)}
          onQueued={() => {
            setShowBudget(false);
            onQueued();
          }}
        />
      )}
    </>
  );
}
