import { useEffect, useState, useCallback } from "react";
import DashboardLayout from "../components/DashboardLayout";
import ActionCard from "./approvals/ActionCard";
import { getAllApprovals, ApprovalAction } from "../lib/api";
import { useWebSocket, WsEvent } from "../lib/ws";
import { RefreshCw } from "lucide-react";

const STATUS_TABS = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "executed", label: "Executed" },
];

export default function ApprovalsPage() {
  const [actions, setActions] = useState<ApprovalAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("pending");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);
    try {
      const data = await getAllApprovals(activeTab);
      setActions(data.actions);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeTab]);

  useEffect(() => { setLoading(true); load(); }, [activeTab, load]);

  useWebSocket((event: WsEvent) => {
    if (["action_queued", "action_approved", "action_rejected", "action_executed"].includes(event.event)) {
      load();
    }
  });

  const handleUpdate = (updated: ApprovalAction) => {
    setActions((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    setTimeout(() => load(), 400);
  };

  return (
    <DashboardLayout>
      <div className="p-6 max-w-4xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Approval Queue</h1>
            <p className="text-sm text-gray-400 mt-0.5">
              {actions.length} action{actions.length !== 1 ? "s" : ""} — {activeTab}
            </p>
          </div>
          <button
            onClick={() => load(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 text-gray-400 text-xs rounded-lg hover:bg-gray-700 hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        <div className="flex gap-1 bg-gray-900 border border-gray-800 p-1 rounded-lg w-fit">
          {STATUS_TABS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setActiveTab(value)}
              className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
                activeTab === value ? "bg-gray-700 text-white font-medium" : "text-gray-400 hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => <div key={i} className="h-44 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />)}
          </div>
        ) : actions.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <p className="text-4xl mb-3">✅</p>
            <p className="font-medium text-white">All clear</p>
            <p className="text-sm mt-1">No {activeTab} actions right now.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {actions.map((action) => (
              <ActionCard key={action.id} action={action} onUpdate={handleUpdate} />
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
