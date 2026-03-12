"use client";

import DashboardLayout from "../components/DashboardLayout";
import { Megaphone } from "lucide-react";

export default function CampaignsPage() {
  return (
    <DashboardLayout>
      <div className="p-6 max-w-4xl">
        <h1 className="text-xl font-bold text-white">Campaigns</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          Campaign control panel — Phase 7
        </p>
        <div className="mt-8 flex flex-col items-center text-center text-gray-500 py-16 bg-gray-900 border border-gray-800 rounded-xl">
          <Megaphone className="w-10 h-10 mb-3 text-gray-700" />
          <p className="font-medium text-white">Coming in Phase 7</p>
          <p className="text-sm mt-1">
            Campaign list, ad set controls, and performance charts.
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
