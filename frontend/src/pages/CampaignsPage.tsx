import { useState, useEffect, useCallback } from "react";
import { RefreshCw, Megaphone } from "lucide-react";
import DashboardLayout from "../components/DashboardLayout";
import CampaignCard from "./campaigns/CampaignCard";
import { getClients, getCampaigns, ClientSummary, CampaignSummary } from "../lib/api";

export default function CampaignsPage() {
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [selectedClient, setSelectedClient] = useState("");
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [loadingClients, setLoadingClients] = useState(true);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    getClients()
      .then((data) => {
        setClients(data);
        if (data.length > 0) setSelectedClient(data[0].client_id);
      })
      .catch(console.error)
      .finally(() => setLoadingClients(false));
  }, []);

  const loadCampaigns = useCallback(() => {
    if (!selectedClient) return;
    setLoadingCampaigns(true);
    getCampaigns(selectedClient)
      .then(setCampaigns)
      .catch(console.error)
      .finally(() => setLoadingCampaigns(false));
  }, [selectedClient]);

  useEffect(() => { loadCampaigns(); }, [loadCampaigns]);

  const handleQueued = () => {
    setToast("Action queued for approval ✓");
    setTimeout(() => setToast(""), 3000);
  };

  const active = campaigns.filter((c) => c.status === "active");
  const paused = campaigns.filter((c) => c.status === "paused");
  const other = campaigns.filter((c) => c.status !== "active" && c.status !== "paused");

  return (
    <DashboardLayout>
      <div className="p-6 max-w-5xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Campaigns</h1>
            <p className="text-sm text-gray-400 mt-0.5">
              Pause, activate, or adjust budgets — all changes go through the approval queue.
            </p>
          </div>
          <button onClick={loadCampaigns} disabled={loadingCampaigns} className="p-2 text-gray-400 hover:text-white transition-colors disabled:opacity-40">
            <RefreshCw className={`w-4 h-4 ${loadingCampaigns ? "animate-spin" : ""}`} />
          </button>
        </div>

        {toast && (
          <div className="bg-green-400/10 border border-green-400/20 text-green-400 text-sm px-4 py-2.5 rounded-lg">{toast}</div>
        )}

        {!loadingClients && clients.length > 1 && (
          <div className="flex gap-2 flex-wrap">
            {clients.map((c) => (
              <button
                key={c.client_id}
                onClick={() => setSelectedClient(c.client_id)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  selectedClient === c.client_id ? "bg-yellow-400 text-gray-950" : "bg-gray-800 text-gray-300 hover:bg-gray-700"
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>
        )}

        {(loadingClients || loadingCampaigns) && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-36 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />)}
          </div>
        )}

        {!loadingClients && !loadingCampaigns && campaigns.length === 0 && (
          <div className="flex flex-col items-center text-center text-gray-500 py-16 bg-gray-900 border border-gray-800 rounded-xl">
            <Megaphone className="w-10 h-10 mb-3 text-gray-700" />
            <p className="font-medium text-white">No campaigns found</p>
            <p className="text-sm mt-1">No campaigns are configured for this client.</p>
          </div>
        )}

        {!loadingCampaigns && campaigns.length > 0 && (
          <div className="space-y-6">
            {active.length > 0 && (
              <section>
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Active ({active.length})</h2>
                <div className="space-y-3">{active.map((c) => <CampaignCard key={c.id} campaign={c} onQueued={handleQueued} />)}</div>
              </section>
            )}
            {paused.length > 0 && (
              <section>
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Paused ({paused.length})</h2>
                <div className="space-y-3">{paused.map((c) => <CampaignCard key={c.id} campaign={c} onQueued={handleQueued} />)}</div>
              </section>
            )}
            {other.length > 0 && (
              <section>
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Other ({other.length})</h2>
                <div className="space-y-3">{other.map((c) => <CampaignCard key={c.id} campaign={c} onQueued={handleQueued} />)}</div>
              </section>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
