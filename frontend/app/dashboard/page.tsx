"use client";

import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import MetricsBar from "./components/MetricsBar";
import SpendChart from "./components/SpendChart";
import ClientsTable from "./components/ClientsTable";
import { getClients, getPendingApprovals, ClientSummary } from "../lib/api";

export default function DashboardPage() {
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getClients(), getPendingApprovals()])
      .then(([c, a]) => {
        setClients(c);
        setPendingCount(a.pending_count);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6 max-w-7xl">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Today&apos;s performance across all clients
          </p>
        </div>

        {/* Metrics */}
        <MetricsBar pendingCount={pendingCount} clientCount={clients.length} />

        {/* Chart + Clients */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <SpendChart />
          <ClientsTable clients={clients} loading={loading} />
        </div>
      </div>
    </DashboardLayout>
  );
}
