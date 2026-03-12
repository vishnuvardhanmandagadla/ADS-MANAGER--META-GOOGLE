import { useState } from "react";
import { CheckCircle, XCircle, Clock, AlertTriangle } from "lucide-react";
import { ApprovalAction, approveAction, rejectAction } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const TIER_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: "Auto", color: "text-green-400 bg-green-400/10" },
  2: { label: "Approve", color: "text-yellow-400 bg-yellow-400/10" },
  3: { label: "Admin", color: "text-red-400 bg-red-400/10" },
};

const PLATFORM_ICONS: Record<string, string> = {
  meta: "𝕗",
  google: "G",
};

const ACTION_TYPE_LABELS: Record<string, string> = {
  pause_adset: "Pause Ad Set",
  activate_adset: "Activate Ad Set",
  pause_campaign: "Pause Campaign",
  activate_campaign: "Activate Campaign",
  update_budget: "Update Budget",
  create_campaign: "Create Campaign",
  delete_campaign: "Delete Campaign",
};

export default function ActionCard({ action, onUpdate }: { action: ApprovalAction; onUpdate: (updated: ApprovalAction) => void }) {
  const { user } = useAuth();
  const [loading, setLoading] = useState<"approve" | "reject" | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [error, setError] = useState("");

  const isPending = action.status === "pending";
  const canAct = user?.role === "admin" || user?.role === "manager";
  const tier = TIER_LABELS[action.tier] ?? TIER_LABELS[2];

  const handleApprove = async () => {
    if (!user) return;
    setLoading("approve");
    setError("");
    try {
      const updated = await approveAction(action.id, user.username);
      onUpdate(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to approve");
    } finally {
      setLoading(null);
    }
  };

  const handleReject = async () => {
    if (!user || !rejectReason.trim()) return;
    setLoading("reject");
    setError("");
    try {
      const updated = await rejectAction(action.id, user.username, rejectReason);
      onUpdate(updated);
      setShowReject(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reject");
    } finally {
      setLoading(null);
    }
  };

  const statusColor =
    action.status === "approved" ? "border-green-800" :
    action.status === "rejected" ? "border-red-800" :
    action.status === "pending" ? "border-yellow-800/50" : "border-gray-800";

  return (
    <div className={`bg-gray-900 border rounded-xl p-5 space-y-4 ${statusColor}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-gray-800 flex items-center justify-center text-base flex-shrink-0">
            {PLATFORM_ICONS[action.platform] ?? "?"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-white text-sm leading-snug">{action.description}</p>
            <p className="text-xs text-gray-500 mt-0.5">
              {ACTION_TYPE_LABELS[action.action_type] ?? action.action_type} · <span className="capitalize">{action.platform}</span> · {action.client_id}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${tier.color}`}>Tier {action.tier}</span>
          <span className="text-lg">{action.status_emoji}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Why</p>
          <p className="text-xs text-gray-300">{action.reason}</p>
        </div>
        <div className="bg-gray-800/60 rounded-lg p-3">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Impact</p>
          <p className="text-xs text-gray-300">{action.estimated_impact}</p>
        </div>
      </div>

      {action.rejection_reason && (
        <div className="flex items-start gap-2 bg-red-400/10 border border-red-400/20 rounded-lg p-3">
          <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-red-300">{action.rejection_reason}</p>
        </div>
      )}

      {isPending && canAct && (
        <div className="space-y-2">
          {error && <p className="text-xs text-red-400 bg-red-400/10 px-3 py-1.5 rounded">{error}</p>}
          {showReject ? (
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Reason for rejection…"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-400/40 focus:border-red-400"
              />
              <div className="flex gap-2">
                <button onClick={handleReject} disabled={!rejectReason.trim() || loading === "reject"} className="flex-1 py-1.5 bg-red-500 text-white text-xs font-semibold rounded-lg hover:bg-red-400 disabled:opacity-50 transition-colors">
                  {loading === "reject" ? "Rejecting…" : "Confirm Reject"}
                </button>
                <button onClick={() => { setShowReject(false); setRejectReason(""); }} className="px-4 py-1.5 bg-gray-800 text-gray-300 text-xs font-medium rounded-lg hover:bg-gray-700 transition-colors">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <button onClick={handleApprove} disabled={loading !== null} className="flex items-center gap-1.5 px-4 py-1.5 bg-green-500/20 text-green-400 border border-green-500/30 text-xs font-semibold rounded-lg hover:bg-green-500/30 disabled:opacity-50 transition-colors">
                <CheckCircle className="w-3.5 h-3.5" />
                {loading === "approve" ? "Approving…" : "Approve"}
              </button>
              <button onClick={() => setShowReject(true)} disabled={loading !== null} className="flex items-center gap-1.5 px-4 py-1.5 bg-red-500/20 text-red-400 border border-red-500/30 text-xs font-semibold rounded-lg hover:bg-red-500/30 disabled:opacity-50 transition-colors">
                <XCircle className="w-3.5 h-3.5" />
                Reject
              </button>
            </div>
          )}
        </div>
      )}

      {!isPending && (
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          {action.status === "approved" ? <CheckCircle className="w-3.5 h-3.5 text-green-400" /> :
           action.status === "rejected" ? <XCircle className="w-3.5 h-3.5 text-red-400" /> :
           <Clock className="w-3.5 h-3.5" />}
          <span className="capitalize">{action.status}</span>
          {action.reviewed_by && <span>by {action.reviewed_by}</span>}
        </div>
      )}

      <p className="text-xs text-gray-600">{new Date(action.created_at).toLocaleString()}</p>
    </div>
  );
}
