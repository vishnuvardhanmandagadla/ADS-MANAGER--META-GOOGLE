"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth";
import { getPendingApprovals } from "../lib/api";
import { useWebSocket, WsEvent } from "../lib/ws";
import Sidebar from "./Sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const [pendingCount, setPendingCount] = useState(0);

  const refreshPending = useCallback(() => {
    getPendingApprovals()
      .then((d) => setPendingCount(d.pending_count))
      .catch(() => {});
  }, []);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  // Load initial pending count
  useEffect(() => {
    if (user) refreshPending();
  }, [user, refreshPending]);

  // Real-time updates via WebSocket
  useWebSocket((event: WsEvent) => {
    if (
      event.event === "action_queued" ||
      event.event === "action_approved" ||
      event.event === "action_rejected"
    ) {
      refreshPending();
    }
  });

  if (isLoading || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-950">
        <div className="flex items-center gap-2 text-gray-400">
          <div className="w-4 h-4 border-2 border-gray-600 border-t-yellow-400 rounded-full animate-spin" />
          <span className="text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-gray-950 text-white">
      <Sidebar pendingCount={pendingCount} user={user} onLogout={logout} />
      <main className="flex-1 overflow-y-auto min-h-screen">{children}</main>
    </div>
  );
}
