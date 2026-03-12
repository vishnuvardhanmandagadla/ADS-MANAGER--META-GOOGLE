"use client";

import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { getClients, ClientSummary } from "../lib/api";

const PLATFORM_COLORS: Record<string, string> = {
  meta: "bg-blue-500/20 text-blue-400",
  google: "bg-green-500/20 text-green-400",
};

export default function ClientsPage() {
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getClients()
      .then(setClients)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout>
      <div className="p-6 max-w-4xl space-y-6">
        <div>
          <h1 className="text-xl font-bold text-white">Clients</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            All configured ad clients
          </p>
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="h-24 bg-gray-900 border border-gray-800 rounded-xl animate-pulse"
              />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {clients.map((c) => (
              <div
                key={c.client_id}
                className="bg-gray-900 border border-gray-800 rounded-xl p-5"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-white">{c.name}</p>
                    <p className="text-xs text-gray-500 mt-0.5 font-mono">
                      {c.client_id}
                    </p>
                  </div>
                  <div className="flex gap-1.5">
                    {c.platforms_enabled.map((p) => (
                      <span
                        key={p}
                        className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
                          PLATFORM_COLORS[p] ?? "bg-gray-700 text-gray-300"
                        }`}
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="mt-3 flex gap-6">
                  <div>
                    <p className="text-xs text-gray-500">Currency</p>
                    <p className="text-sm text-white font-medium">
                      {c.currency}
                    </p>
                  </div>
                  {c.max_daily_spend != null && (
                    <div>
                      <p className="text-xs text-gray-500">Daily Cap</p>
                      <p className="text-sm text-white font-medium">
                        {c.currency} {c.max_daily_spend.toLocaleString()}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
