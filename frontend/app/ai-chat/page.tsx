"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Send, Bot, User, CheckCircle, Clock } from "lucide-react";
import DashboardLayout from "../components/DashboardLayout";
import {
  getClients,
  aiChat,
  ClientSummary,
  ApprovalAction,
} from "../lib/api";

interface Message {
  role: "user" | "assistant";
  text: string;
  queuedActions?: ApprovalAction[];
  ts: number;
}

const STARTERS = [
  "How are my campaigns performing?",
  "Pause underperforming campaigns",
  "Which campaign has the best ROAS?",
  "Generate ad copy for event tickets",
];

export default function AIChatPage() {
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [selectedClient, setSelectedClient] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingClients, setLoadingClients] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getClients()
      .then((data) => {
        setClients(data);
        if (data.length > 0) setSelectedClient(data[0].client_id);
      })
      .catch(console.error)
      .finally(() => setLoadingClients(false));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || !selectedClient || loading) return;
      const userMsg: Message = { role: "user", text: text.trim(), ts: Date.now() };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);
      try {
        const res = await aiChat(selectedClient, text.trim());
        const assistantMsg: Message = {
          role: "assistant",
          text: res.message,
          queuedActions: res.queued_actions,
          ts: Date.now(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err: unknown) {
        const errText =
          err instanceof Error ? err.message : "Something went wrong.";
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: `Error: ${errText}`, ts: Date.now() },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [selectedClient, loading]
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  const clientName =
    clients.find((c) => c.client_id === selectedClient)?.name ?? selectedClient;

  return (
    <DashboardLayout>
      <div className="flex flex-col h-[calc(100vh-2rem)] max-w-3xl mx-auto p-4 gap-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">AI Assistant</h1>
            <p className="text-sm text-gray-400 mt-0.5">
              Analyse performance, queue actions, generate copy — with your
              approval.
            </p>
          </div>

          {/* Client selector */}
          {!loadingClients && clients.length > 1 && (
            <select
              value={selectedClient}
              onChange={(e) => {
                setSelectedClient(e.target.value);
                setMessages([]);
              }}
              className="bg-gray-800 border border-gray-700 text-white text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-yellow-400/40"
            >
              {clients.map((c) => (
                <option key={c.client_id} value={c.client_id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {/* Welcome */}
          {messages.length === 0 && !loading && (
            <div className="flex flex-col items-center text-center py-12 gap-4">
              <div className="w-12 h-12 rounded-full bg-yellow-400/10 flex items-center justify-center">
                <Bot className="w-6 h-6 text-yellow-400" />
              </div>
              <div>
                <p className="font-semibold text-white">
                  Hi! I&apos;m your ads AI.
                </p>
                <p className="text-sm text-gray-400 mt-1 max-w-sm">
                  Ask me about {clientName}&apos;s campaigns. Any actions I
                  suggest go through the approval queue — nothing executes
                  automatically.
                </p>
              </div>
              <div className="flex flex-wrap gap-2 justify-center mt-2">
                {STARTERS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="text-xs px-3 py-1.5 rounded-full bg-gray-800 text-gray-300 hover:bg-gray-700 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.ts}
              className={`flex gap-3 ${
                msg.role === "user" ? "flex-row-reverse" : "flex-row"
              }`}
            >
              {/* Avatar */}
              <div
                className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
                  msg.role === "user"
                    ? "bg-yellow-400/10"
                    : "bg-gray-800"
                }`}
              >
                {msg.role === "user" ? (
                  <User className="w-3.5 h-3.5 text-yellow-400" />
                ) : (
                  <Bot className="w-3.5 h-3.5 text-gray-400" />
                )}
              </div>

              <div
                className={`max-w-[80%] space-y-2 ${
                  msg.role === "user" ? "items-end" : "items-start"
                } flex flex-col`}
              >
                {/* Bubble */}
                <div
                  className={`px-4 py-2.5 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed ${
                    msg.role === "user"
                      ? "bg-yellow-400 text-gray-950 rounded-tr-sm"
                      : "bg-gray-800 text-gray-100 rounded-tl-sm"
                  }`}
                >
                  {msg.text}
                </div>

                {/* Queued actions */}
                {msg.queuedActions && msg.queuedActions.length > 0 && (
                  <div className="space-y-1.5 w-full">
                    <p className="text-xs text-gray-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {msg.queuedActions.length} action
                      {msg.queuedActions.length > 1 ? "s" : ""} queued for
                      approval
                    </p>
                    {msg.queuedActions.map((a) => (
                      <div
                        key={a.id}
                        className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs space-y-0.5"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium text-white truncate">
                            {a.description}
                          </span>
                          <span className="shrink-0 flex items-center gap-1 text-yellow-400">
                            <CheckCircle className="w-3 h-3" />
                            Pending
                          </span>
                        </div>
                        {a.estimated_impact && (
                          <p className="text-gray-400">{a.estimated_impact}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {loading && (
            <div className="flex gap-3">
              <div className="shrink-0 w-7 h-7 rounded-full bg-gray-800 flex items-center justify-center">
                <Bot className="w-3.5 h-3.5 text-gray-400" />
              </div>
              <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1 items-center">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form
          onSubmit={handleSubmit}
          className="flex gap-2 bg-gray-900 border border-gray-700 rounded-xl p-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              selectedClient
                ? `Ask about ${clientName}…`
                : "Select a client first"
            }
            disabled={!selectedClient || loading}
            className="flex-1 bg-transparent text-sm text-white placeholder-gray-500 focus:outline-none px-2 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || !selectedClient || loading}
            className="p-2 bg-yellow-400 text-gray-950 rounded-lg hover:bg-yellow-300 disabled:opacity-40 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </DashboardLayout>
  );
}
