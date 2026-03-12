"use client";

import { TrendingUp, TrendingDown, MousePointer, IndianRupee, Clock } from "lucide-react";

interface Metric {
  label: string;
  value: string;
  sub: string;
  trend?: "up" | "down" | "neutral";
  icon: React.ReactNode;
  highlight?: boolean;
}

function MetricCard({ label, value, sub, trend, icon, highlight }: Metric) {
  return (
    <div
      className={`rounded-xl p-5 border ${
        highlight
          ? "bg-yellow-400/10 border-yellow-400/30"
          : "bg-gray-900 border-gray-800"
      }`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">
            {label}
          </p>
          <p
            className={`text-2xl font-bold mt-1 ${
              highlight ? "text-yellow-400" : "text-white"
            }`}
          >
            {value}
          </p>
          <p className="text-xs text-gray-500 mt-1">{sub}</p>
        </div>
        <div
          className={`p-2 rounded-lg ${
            highlight ? "bg-yellow-400/20 text-yellow-400" : "bg-gray-800 text-gray-400"
          }`}
        >
          {icon}
        </div>
      </div>
      {trend && (
        <div className="mt-3 flex items-center gap-1">
          {trend === "up" ? (
            <TrendingUp className="w-3 h-3 text-green-400" />
          ) : trend === "down" ? (
            <TrendingDown className="w-3 h-3 text-red-400" />
          ) : null}
          <span
            className={`text-xs ${
              trend === "up"
                ? "text-green-400"
                : trend === "down"
                ? "text-red-400"
                : "text-gray-500"
            }`}
          >
            vs yesterday
          </span>
        </div>
      )}
    </div>
  );
}

interface MetricsBarProps {
  pendingCount: number;
  clientCount: number;
}

export default function MetricsBar({
  pendingCount,
  clientCount,
}: MetricsBarProps) {
  // Mock performance metrics — replaced with real Meta API data in Phase 8
  const metrics: Metric[] = [
    {
      label: "Today's Spend",
      value: "₹8,420",
      sub: "across all clients",
      trend: "up",
      icon: <IndianRupee className="w-4 h-4" />,
    },
    {
      label: "Total Clicks",
      value: "2,841",
      sub: "all campaigns",
      trend: "up",
      icon: <MousePointer className="w-4 h-4" />,
    },
    {
      label: "Avg CPC",
      value: "₹2.96",
      sub: `target ₹3.00`,
      trend: "up",
      icon: <TrendingUp className="w-4 h-4" />,
    },
    {
      label: "Pending Approvals",
      value: String(pendingCount),
      sub: `${clientCount} active client${clientCount !== 1 ? "s" : ""}`,
      highlight: pendingCount > 0,
      icon: <Clock className="w-4 h-4" />,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((m) => (
        <MetricCard key={m.label} {...m} />
      ))}
    </div>
  );
}
