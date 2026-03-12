"use client";

import DashboardLayout from "../components/DashboardLayout";
import { useAuth } from "../lib/auth";
import { Shield, Users, Bell, Database } from "lucide-react";

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
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

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <DashboardLayout>
      <div className="p-6 max-w-3xl space-y-6">
        <div>
          <h1 className="text-xl font-bold text-white">Settings</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Safety rules, team access, and notification channels
          </p>
        </div>

        {/* Safety Rules */}
        <Section
          title="Safety Limits"
          icon={<Shield className="w-4 h-4" />}
        >
          <p className="text-xs text-gray-500 mb-3">
            Configured in{" "}
            <code className="bg-gray-800 px-1 rounded text-gray-300">
              config/safety.yaml
            </code>{" "}
            — edit the file to change limits.
          </p>
          <Row label="Max daily spend per client" value="₹50,000" />
          <Row label="Max single budget change" value="₹10,000" />
          <Row label="Require approval above" value="₹5,000" />
          <Row label="Max new campaigns per day" value="5" />
          <Row label="Cool-down after rejection" value="60 minutes" />
          <Row label="Pending action expiry" value="24 hours" />
          <Row label="Auto-pause CPC spike" value="200% above 7-day avg" />
        </Section>

        {/* Tier System */}
        <Section
          title="Action Tiers"
          icon={<Database className="w-4 h-4" />}
        >
          <div className="space-y-2">
            {[
              {
                tier: "Tier 1 — Auto",
                desc: "Read-only operations. Execute immediately, no approval needed.",
                color: "text-green-400 bg-green-400/10 border-green-400/20",
              },
              {
                tier: "Tier 2 — Approve",
                desc: "Spend-affecting changes. Manager or Admin must approve before execution.",
                color: "text-yellow-400 bg-yellow-400/10 border-yellow-400/20",
              },
              {
                tier: "Tier 3 — Admin Only",
                desc: "Destructive actions (delete, override). Admin must approve.",
                color: "text-red-400 bg-red-400/10 border-red-400/20",
              },
            ].map(({ tier, desc, color }) => (
              <div
                key={tier}
                className={`px-3 py-2 rounded-lg border text-xs ${color}`}
              >
                <p className="font-semibold">{tier}</p>
                <p className="mt-0.5 opacity-80">{desc}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* Team */}
        <Section title="Team Access" icon={<Users className="w-4 h-4" />}>
          <p className="text-xs text-gray-500 mb-3">
            Configured in{" "}
            <code className="bg-gray-800 px-1 rounded text-gray-300">
              config/clients/tickets99.yaml
            </code>
          </p>
          {[
            { name: "Vishnu", role: "Admin", access: "All clients · Tier 1/2/3" },
            { name: "Siva", role: "Manager", access: "Tickets99 · Tier 1/2" },
            { name: "Vyas", role: "Viewer", access: "Tickets99 · Read only" },
          ].map(({ name, role, access }) => (
            <div
              key={name}
              className={`flex items-center justify-between py-2.5 border-b border-gray-800 last:border-0 ${
                user?.username === name.toLowerCase()
                  ? "opacity-100"
                  : "opacity-70"
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-full bg-yellow-400/20 text-yellow-400 flex items-center justify-center text-xs font-bold">
                  {name[0]}
                </div>
                <div>
                  <p className="text-sm text-white font-medium">
                    {name}
                    {user?.username === name.toLowerCase() && (
                      <span className="ml-2 text-xs text-yellow-400">
                        (you)
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-gray-500">{access}</p>
                </div>
              </div>
              <span className="text-xs text-gray-400 bg-gray-800 px-2 py-0.5 rounded-full capitalize">
                {role}
              </span>
            </div>
          ))}
        </Section>

        {/* Notifications */}
        <Section
          title="Notification Channels"
          icon={<Bell className="w-4 h-4" />}
        >
          <p className="text-xs text-gray-500 mb-3">
            WhatsApp and Telegram wired in Phase 9.
          </p>
          {[
            { channel: "WhatsApp", status: "Phase 9", note: "Approval requests + daily digest" },
            { channel: "Telegram", status: "Phase 9", note: "Inline approve/reject buttons" },
            { channel: "WebSocket", status: "Live", note: "Real-time dashboard updates" },
          ].map(({ channel, status, note }) => (
            <div
              key={channel}
              className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0"
            >
              <div>
                <p className="text-sm text-white">{channel}</p>
                <p className="text-xs text-gray-500">{note}</p>
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  status === "Live"
                    ? "bg-green-400/10 text-green-400"
                    : "bg-gray-700 text-gray-400"
                }`}
              >
                {status}
              </span>
            </div>
          ))}
        </Section>
      </div>
    </DashboardLayout>
  );
}
