"use client";

import { useState } from "react";
import { X, IndianRupee } from "lucide-react";
import { createAction, CampaignSummary } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface BudgetModalProps {
  campaign: CampaignSummary;
  onClose: () => void;
  onQueued: () => void;
}

export default function BudgetModal({
  campaign,
  onClose,
  onQueued,
}: BudgetModalProps) {
  const { user } = useAuth();
  const [budget, setBudget] = useState(String(campaign.daily_budget));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const newBudget = Number(budget);
  const delta = newBudget - campaign.daily_budget;
  const valid = !isNaN(newBudget) && newBudget > 0 && delta !== 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid || !user) return;
    setLoading(true);
    setError("");
    try {
      await createAction({
        client_id: campaign.client_id,
        platform: "meta",
        action_type: "update_budget",
        description: `Update daily budget for "${campaign.name}" from ₹${campaign.daily_budget.toLocaleString()} → ₹${newBudget.toLocaleString()}`,
        reason: delta > 0 ? "Scale up performing campaign" : "Reduce spend on underperformer",
        estimated_impact:
          delta > 0
            ? `+₹${Math.abs(delta).toLocaleString()}/day additional spend`
            : `Save ₹${Math.abs(delta).toLocaleString()}/day`,
        payload: { campaign_id: campaign.id, daily_budget: newBudget },
      });
      onQueued();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to queue action");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-white">Edit Daily Budget</h3>
          <button
            onClick={onClose}
            className="p-1 text-gray-500 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-sm text-gray-400 mb-4 truncate">
          {campaign.name}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              New daily budget (INR)
            </label>
            <div className="relative">
              <IndianRupee className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="number"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-yellow-400/40 focus:border-yellow-400"
                min={1}
                step={100}
              />
            </div>
            {delta !== 0 && !isNaN(newBudget) && newBudget > 0 && (
              <p
                className={`text-xs mt-1.5 ${
                  delta > 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {delta > 0 ? "+" : ""}₹{delta.toLocaleString()}/day vs current
              </p>
            )}
          </div>

          {error && (
            <p className="text-xs text-red-400 bg-red-400/10 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!valid || loading}
              className="flex-1 py-2 bg-yellow-400 text-gray-950 text-sm font-semibold rounded-lg hover:bg-yellow-300 disabled:opacity-50 transition-colors"
            >
              {loading ? "Queuing…" : "Queue for Approval"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
