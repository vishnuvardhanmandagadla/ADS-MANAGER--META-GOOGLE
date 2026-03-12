"use client";

import DashboardLayout from "../components/DashboardLayout";
import { MessageSquare } from "lucide-react";

export default function AIChatPage() {
  return (
    <DashboardLayout>
      <div className="p-6 max-w-4xl">
        <h1 className="text-xl font-bold text-white">AI Assistant</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          Conversational campaign management — Phase 7
        </p>
        <div className="mt-8 flex flex-col items-center text-center text-gray-500 py-16 bg-gray-900 border border-gray-800 rounded-xl">
          <MessageSquare className="w-10 h-10 mb-3 text-gray-700" />
          <p className="font-medium text-white">Coming in Phase 7</p>
          <p className="text-sm mt-1 max-w-sm">
            Chat with Claude to analyse performance, pause underperformers,
            and generate ad copy — all with approval queue integration.
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
