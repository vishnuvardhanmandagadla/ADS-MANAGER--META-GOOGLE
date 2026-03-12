import { useState, useEffect } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { useAuth } from "../lib/auth";
import { apiFetch } from "../lib/api";
import { Shield, Users, Bell, Database, ClipboardList, RefreshCw } from "lucide-react";

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="p-1.5 bg-gray-800 rounded-lg text-yellow-400">{icon}</div>
        <h2 className="text-sm font-semibold text-white">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
      <span className="text-sm text-gray-400">{label}</span>
      <span className="text-sm text-white font-medium">{value}</span>
    </div>
  );
}

interface AuditEntry {
  id: string;
  event_type: string;
  timestamp: string;
  client_id: string;
  description?: string;
  action_type?: string;
  actor?: string;
  reason?: string;
}

const EVENT_STYLES: Record<string, string> = {
  ACTION_QUEUED: "text-yellow-400 bg-yellow-400/10",
  ACTION_APPROVED: "text-green-400 bg-green-400/10",
  ACTION_REJECTED: "text-red-400 bg-red-400/10",
  ACTION_EXECUTED: "text-green-400 bg-green-400/10",
  ACTION_FAILED: "text-red-400 bg-red-400/10",
  ACTION_EXPIRED: "text-gray-400 bg-gray-700/40",
  ACTION_CANCELLED: "text-gray-400 bg-gray-700/40",
  TIER3_ATTEMPTED: "text-red-400 bg-red-400/10",
  ANOMALY_DETECTED: "text-orange-400 bg-orange-400/10",
  POLICY_VIOLATION: "text-orange-400 bg-orange-400/10",
};

function formatTs(iso: string) {
  try {
    return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

export default function SettingsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");

  const loadAudit = () => {
    if (!isAdmin) return;
    setAuditLoading(true);
    setAuditError("");
    apiFetch<{ total: number; entries: AuditEntry[] }>("/api/v1/audit?limit=50")
      .then((data) => setAuditEntries(data.entries))
      .catch((err) => setAuditError(err.message))
      .finally(() => setAuditLoading(false));
  };

  useEffect(() => { loadAudit(); }, [isAdmin]);

  return (
    <DashboardLayout>
      <div className="p-6 max-w-3xl space-y-6">
        <div>
          <h1 className="text-xl font-bold text-white">Settings</h1>
          <p className="text-sm text-gray-400 mt-0.5">Safety rules, team access, and notification channels</p>
        </div>

        <Section title="Safety Limits" icon={<Shield className="w-4 h-4" />}>
          <p className="text-xs text-gray-500 mb-3">
            Configured in <code className="bg-gray-800 px-1 rounded text-gray-300">config/safety.yaml</code> — edit the file to change limits.
          </p>
          <Row label="Max daily spend per client" value="₹50,000" />
          <Row label="Max single budget change" value="₹10,000" />
          <Row label="Require approval above" value="₹5,000" />
          <Row label="Max new campaigns per day" value="5" />
          <Row label="Cool-down after rejection" value="60 minutes" />
          <Row label="Pending action expiry" value="24 hours" />
          <Row label="Auto-pause CPC spike" value="200% above 7-day avg" />
          <Row label="Auto-pause spend overrun" value="120% of daily budget" />
        </Section>

        <Section title="Action Tiers" icon={<Database className="w-4 h-4" />}>
          <div className="space-y-2">
            {[
              { tier: "Tier 1 — Auto", desc: "Read-only operations. Execute immediately, no approval needed.", color: "text-green-400 bg-green-400/10 border-green-400/20" },
              { tier: "Tier 2 — Approve", desc: "Spend-affecting changes. Manager or Admin must approve before execution.", color: "text-yellow-400 bg-yellow-400/10 border-yellow-400/20" },
              { tier: "Tier 3 — Admin Only", desc: "Destructive actions (delete, override). Admin must approve.", color: "text-red-400 bg-red-400/10 border-red-400/20" },
            ].map(({ tier, desc, color }) => (
              <div key={tier} className={`px-3 py-2 rounded-lg border text-xs ${color}`}>
                <p className="font-semibold">{tier}</p>
                <p className="mt-0.5 opacity-80">{desc}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Team Access" icon={<Users className="w-4 h-4" />}>
          <p className="text-xs text-gray-500 mb-3">
            Configured in <code className="bg-gray-800 px-1 rounded text-gray-300">config/clients/tickets99.yaml</code>
          </p>
          {[
            { name: "Vishnu", role: "Admin", access: "All clients · Tier 1/2/3" },
            { name: "Siva", role: "Manager", access: "Tickets99 · Tier 1/2" },
            { name: "Vyas", role: "Viewer", access: "Tickets99 · Read only" },
          ].map(({ name, role, access }) => (
            <div key={name} className={`flex items-center justify-between py-2.5 border-b border-gray-800 last:border-0 ${user?.username === name.toLowerCase() ? "opacity-100" : "opacity-70"}`}>
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-full bg-yellow-400/20 text-yellow-400 flex items-center justify-center text-xs font-bold">{name[0]}</div>
                <div>
                  <p className="text-sm text-white font-medium">
                    {name}
                    {user?.username === name.toLowerCase() && <span className="ml-2 text-xs text-yellow-400">(you)</span>}
                  </p>
                  <p className="text-xs text-gray-500">{access}</p>
                </div>
              </div>
              <span className="text-xs text-gray-400 bg-gray-800 px-2 py-0.5 rounded-full capitalize">{role}</span>
            </div>
          ))}
        </Section>

        <Section title="Notification Channels" icon={<Bell className="w-4 h-4" />}>
          {[
            { channel: "WhatsApp", status: "Live", note: "Approval requests + daily digest + anomaly alerts" },
            { channel: "WebSocket", status: "Live", note: "Real-time dashboard updates" },
          ].map(({ channel, status, note }) => (
            <div key={channel} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
              <div>
                <p className="text-sm text-white">{channel}</p>
                <p className="text-xs text-gray-500">{note}</p>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-green-400/10 text-green-400">{status}</span>
            </div>
          ))}
        </Section>

        {isAdmin && (
          <Section title="Audit Log" icon={<ClipboardList className="w-4 h-4" />}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-gray-500">Every action, approval, rejection, and anomaly. Immutable.</p>
              <button onClick={loadAudit} disabled={auditLoading} className="p-1.5 text-gray-400 hover:text-white transition-colors disabled:opacity-40">
                <RefreshCw className={`w-3.5 h-3.5 ${auditLoading ? "animate-spin" : ""}`} />
              </button>
            </div>
            {auditError && <p className="text-xs text-red-400 mb-3">{auditError}</p>}
            {auditLoading && (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => <div key={i} className="h-10 bg-gray-800 rounded animate-pulse" />)}
              </div>
            )}
            {!auditLoading && auditEntries.length === 0 && !auditError && (
              <p className="text-xs text-gray-500 text-center py-6">No audit entries yet. Queue and approve some actions.</p>
            )}
            {!auditLoading && auditEntries.length > 0 && (
              <div className="space-y-1.5 max-h-96 overflow-y-auto pr-1">
                {auditEntries.map((entry) => (
                  <div key={entry.id} className="flex items-start gap-3 px-3 py-2 bg-gray-800/60 rounded-lg">
                    <span className={`shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded mt-0.5 ${EVENT_STYLES[entry.event_type] ?? "text-gray-400 bg-gray-700"}`}>
                      {entry.event_type.replace(/_/g, " ")}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-white truncate">{entry.description ?? entry.action_type ?? "—"}</p>
                      <p className="text-[10px] text-gray-500 mt-0.5">
                        {formatTs(entry.timestamp)}{entry.actor && ` · ${entry.actor}`}{entry.reason && ` · ${entry.reason}`}
                      </p>
                    </div>
                    <span className="shrink-0 text-[10px] text-gray-600">{entry.client_id}</span>
                  </div>
                ))}
              </div>
            )}
          </Section>
        )}
      </div>
    </DashboardLayout>
  );
}
