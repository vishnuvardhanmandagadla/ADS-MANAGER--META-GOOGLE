/**
 * API client — wraps fetch with auth headers, token management,
 * and automatic redirect to /login on 401/403.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Token storage ──────────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ads_token");
}

export function setToken(token: string): void {
  localStorage.setItem("ads_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("ads_token");
  localStorage.removeItem("ads_user");
}

// ── Core fetch wrapper ─────────────────────────────────────────────────────────

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 || res.status === 403) {
    clearToken();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ClientSummary {
  client_id: string;
  name: string;
  currency: string;
  platforms_enabled: string[];
  max_daily_spend: number | null;
}

export interface ApprovalAction {
  id: string;
  client_id: string;
  platform: string;
  tier: number;
  action_type: string;
  description: string;
  reason: string;
  estimated_impact: string;
  status: string;
  status_emoji: string;
  created_at: string;
  reviewed_by?: string;
  rejection_reason?: string;
}

export interface ApprovalsListResponse {
  pending_count: number;
  actions: ApprovalAction[];
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(username: string, password: string) {
  const data = await apiFetch<{
    access_token: string;
    username: string;
    role: string;
  }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.access_token);
  if (typeof window !== "undefined") {
    localStorage.setItem(
      "ads_user",
      JSON.stringify({ username: data.username, role: data.role })
    );
  }
  return data;
}

// ── Clients ───────────────────────────────────────────────────────────────────

export async function getClients(): Promise<ClientSummary[]> {
  return apiFetch<ClientSummary[]>("/api/v1/clients");
}

// ── Approvals ─────────────────────────────────────────────────────────────────

export async function getPendingApprovals(): Promise<ApprovalsListResponse> {
  return apiFetch<ApprovalsListResponse>("/api/v1/approvals");
}

export async function getAllApprovals(
  status?: string
): Promise<ApprovalsListResponse> {
  const q = status ? `?status=${status}` : "";
  return apiFetch<ApprovalsListResponse>(`/api/v1/approvals/all${q}`);
}

export async function approveAction(
  id: string,
  reviewer: string
): Promise<ApprovalAction> {
  return apiFetch<ApprovalAction>(`/api/v1/approvals/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ reviewer }),
  });
}

export async function rejectAction(
  id: string,
  reviewer: string,
  reason: string
): Promise<ApprovalAction> {
  return apiFetch<ApprovalAction>(`/api/v1/approvals/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reviewer, reason }),
  });
}

export async function cancelAction(id: string): Promise<ApprovalAction> {
  return apiFetch<ApprovalAction>(`/api/v1/approvals/${id}/cancel`, {
    method: "POST",
  });
}

// ── AI ────────────────────────────────────────────────────────────────────────

export async function aiChat(client_id: string, message: string) {
  return apiFetch<{
    message: string;
    proposed_actions: unknown[];
    queued_actions: ApprovalAction[];
    queued_count: number;
  }>("/api/v1/ai/chat", {
    method: "POST",
    body: JSON.stringify({ client_id, message }),
  });
}

// ── Campaigns ─────────────────────────────────────────────────────────────────

export interface CampaignSummary {
  id: string;
  client_id: string;
  name: string;
  status: "active" | "paused" | "archived" | "deleted";
  objective: string | null;
  daily_budget: number;
  spend: number;
  clicks: number;
  impressions: number;
  cpc: number;
  ctr: number;
  roas: number | null;
  conversions: number;
}

export async function getCampaigns(
  client_id: string
): Promise<CampaignSummary[]> {
  return apiFetch<CampaignSummary[]>(`/api/v1/clients/${client_id}/campaigns`);
}

// ── Direct action creation ────────────────────────────────────────────────────

export interface CreateActionPayload {
  client_id: string;
  platform?: string;
  action_type: string;
  description: string;
  reason: string;
  estimated_impact: string;
  payload?: Record<string, unknown>;
}

export async function createAction(
  data: CreateActionPayload
): Promise<ApprovalAction> {
  return apiFetch<ApprovalAction>("/api/v1/actions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function aiCopy(
  client_id: string,
  product: string,
  audience: string,
  count = 3
) {
  return apiFetch<{ variations: unknown[]; count: number }>("/api/v1/ai/copy", {
    method: "POST",
    body: JSON.stringify({ client_id, product, audience, count }),
  });
}
