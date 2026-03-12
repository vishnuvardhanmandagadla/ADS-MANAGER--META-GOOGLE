"use client";

import { useEffect, useRef, useCallback } from "react";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

export interface WsEvent {
  event: string;
  data: Record<string, unknown>;
  timestamp: string;
}

/**
 * Connect to the backend WebSocket and call onMessage for each event.
 * Automatically reconnects on disconnect (3s back-off).
 */
export function useWebSocket(onMessage: (event: WsEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(onMessage);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as WsEvent;
        onMessageRef.current(data);
      } catch {
        // ignore malformed frames
      }
    };

    ws.onclose = () => {
      // Reconnect after 3 s
      reconnectTimer.current = setTimeout(connect, 3000);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);
}
