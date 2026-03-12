import { Link } from "react-router-dom";
import { ClientSummary } from "../../lib/api";
import { ExternalLink } from "lucide-react";

const PLATFORM_COLORS: Record<string, string> = {
  meta: "bg-blue-500/20 text-blue-400",
  google: "bg-green-500/20 text-green-400",
};

export default function ClientsTable({ clients, loading }: { clients: ClientSummary[]; loading?: boolean }) {
  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Active Clients</h3>
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <div key={i} className="h-12 bg-gray-800 rounded-lg animate-pulse" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">Active Clients</h3>
        <Link to="/campaigns" className="text-xs text-yellow-400 hover:text-yellow-300 transition-colors">
          View campaigns
        </Link>
      </div>
      {clients.length === 0 ? (
        <p className="text-sm text-gray-500 py-4 text-center">No clients configured yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="pb-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Client</th>
                <th className="pb-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Platforms</th>
                <th className="pb-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Daily Cap</th>
                <th className="pb-3 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {clients.map((c) => (
                <tr key={c.client_id} className="group">
                  <td className="py-3">
                    <p className="font-medium text-white">{c.name}</p>
                    <p className="text-xs text-gray-500">{c.client_id}</p>
                  </td>
                  <td className="py-3">
                    <div className="flex flex-wrap gap-1">
                      {c.platforms_enabled.map((p) => (
                        <span key={p} className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${PLATFORM_COLORS[p] ?? "bg-gray-700 text-gray-300"}`}>
                          {p}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 text-right text-gray-300">
                    {c.max_daily_spend != null ? `${c.currency} ${c.max_daily_spend.toLocaleString()}` : "—"}
                  </td>
                  <td className="py-3 text-right">
                    <Link to="/campaigns" className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-500 hover:text-yellow-400">
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
