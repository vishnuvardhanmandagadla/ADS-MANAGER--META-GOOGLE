# Ads Engine

AI-powered ad management platform with human-in-the-loop approval.
Claude AI suggests actions. You approve. System executes. No money moves without your ✅.

---

## What It Does

- Manages Meta and Google ad campaigns across multiple clients from one dashboard
- AI analyzes performance and suggests optimizations (pause bad ad sets, increase budgets, write copy)
- Every spend-affecting action goes into an **approval queue** — you approve or reject before anything runs
- Real-time dashboard with spend, CPC, clicks, and AI insights per client

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + Python |
| Frontend | Next.js 15 + shadcn/ui + Tailwind CSS |
| Charts | Recharts |
| Real-time | WebSocket |
| Auth | NextAuth.js |
| AI | Claude API (claude-sonnet-4-6) |
| Database | PostgreSQL (SQLite for local dev) |
| Platforms | Meta Ads API, Google Ads API |

---

## 3-Tier Action System

| Tier | Who approves | Examples |
|---|---|---|
| **Tier 1 — Auto** | No one | Pull reports, analytics, monitoring, drafts |
| **Tier 2 — Approve** | You (or Manager) | Create campaign, change budget, pause ad set, edit copy |
| **Tier 3 — Restricted** | Admin only | Delete campaigns, remove accounts, override caps |

---

## Build Progress

### Phase 1 — Backend scaffold + config + platform base
**Status: COMPLETE**

- [x] Project directory structure (`backend/` + `frontend/`)
- [x] `requirements.txt` — all Python dependencies pinned
- [x] `.env.example` — all secrets documented (Meta, Google, Claude, WhatsApp)
- [x] `config/settings.yaml` — app config (CORS, scheduler, AI model)
- [x] `config/safety.yaml` — spend limits, anomaly rules, Tier 3 restrictions
- [x] `config/clients/tickets99.yaml` — first client config
- [x] `ads_engine/models/base.py` — all Pydantic models (Campaign, AdSet, Ad, Targeting, PerformanceReport...)
- [x] `ads_engine/platforms/base.py` — abstract platform adapter interface
- [x] `ads_engine/core/config.py` — settings loader (env + YAML, cached)
- [x] `main.py` — FastAPI app with CORS, lifespan, /health endpoint
- [x] Frontend scaffold — Next.js 15, Tailwind, all page routes stubbed
- [x] `frontend/next.config.ts` — API proxy to FastAPI backend

---

### Phase 2 — Meta Ads platform adapter
**Status: NOT STARTED**

- [ ] `ads_engine/platforms/meta.py` — full Meta Marketing API implementation
- [ ] Authentication with long-lived access tokens
- [ ] `get_campaigns()` — fetch all campaigns for a client account
- [ ] `get_adsets()` / `get_ads()` — fetch ad sets and ads
- [ ] `get_campaign_performance()` / `get_adset_performance()` — pull metrics
- [ ] `create_campaign()` / `create_adset()` / `create_ad()` — write operations (Tier 2)
- [ ] `update_campaign_budget()` — budget changes (Tier 2)
- [ ] `set_campaign_status()` / `set_adset_status()` — pause / activate (Tier 2)
- [ ] `delete_campaign()` — Tier 3, admin only
- [ ] `duplicate_campaign()` — clone campaigns with all ad sets
- [ ] Rate limit handling + retry logic
- [ ] Unit tests for Meta adapter

---

### Phase 3 — Approval system (human-in-the-loop)
**Status: NOT STARTED**

- [ ] `ads_engine/approval/action.py` — `PendingAction` model (id, tier, type, reason, impact, payload, status)
- [ ] `ads_engine/approval/queue.py` — DB-backed queue (create, list, expire)
- [ ] `ads_engine/approval/policies.py` — tier rules (what needs approval, cool-down logic)
- [ ] `ads_engine/approval/executor.py` — execute approved actions only
- [ ] `ads_engine/approval/reviewer.py` — send to human, wait for response

---

### Phase 4 — FastAPI endpoints + WebSocket
**Status: NOT STARTED**

- [ ] `ads_engine/api/router.py` — main API router
- [ ] `GET /clients` — list all clients
- [ ] `GET /clients/{id}/campaigns` — list campaigns with metrics
- [ ] `GET /approvals` — pending action queue
- [ ] `POST /approvals/{id}/approve` — approve an action
- [ ] `POST /approvals/{id}/reject` — reject an action
- [ ] `POST /ai/chat` — send message to Claude, get suggestion + queue item
- [ ] `WS /ws` — real-time updates to dashboard
- [ ] API key / JWT auth middleware

---

### Phase 5 — Claude AI layer
**Status: NOT STARTED**

- [ ] `ads_engine/ai/analyst.py` — performance analysis (flag anomalies, find winners/losers)
- [ ] `ads_engine/ai/copywriter.py` — generate ad copy variations per audience
- [ ] `ads_engine/ai/optimizer.py` — suggest budget shifts, audience changes, new campaigns
- [ ] `ads_engine/ai/chat.py` — conversational interface (natural language → pending action)
- [ ] Client context injection (Tickets99 audience info, CPC targets injected into every prompt)
- [ ] Suggestions always route through approval queue, never execute directly

---

### Phase 6 — Frontend: Dashboard + Approval Queue + Settings
**Status: NOT STARTED**

- [ ] `app/dashboard/page.tsx` — today's overview (spend, clicks, CPC across clients)
- [ ] `app/dashboard/components/MetricsBar.tsx` — spend / clicks / CPC stat cards
- [ ] `app/dashboard/components/ClientsTable.tsx` — per-client status table
- [ ] `app/dashboard/components/SpendChart.tsx` — weekly spend line chart (Recharts)
- [ ] `app/approvals/page.tsx` — approval queue with approve / reject / edit buttons
- [ ] `app/approvals/components/ActionCard.tsx` — full action card with AI reason + impact
- [ ] `app/settings/page.tsx` — safety rules editor, notification channels, team management
- [ ] Sidebar layout with nav, pending badge, user avatar
- [ ] WebSocket connection for live updates
- [ ] NextAuth login (admin / manager / viewer roles)

---

### Phase 7 — Frontend: Campaign Control + AI Chat
**Status: NOT STARTED**

- [ ] `app/campaigns/page.tsx` — campaign list per client
- [ ] `app/campaigns/[id]/page.tsx` — campaign detail (ad sets table, performance chart, AI insight)
- [ ] Pause / activate / edit budget controls (routes through approval queue)
- [ ] `app/ai-chat/page.tsx` — conversational UI with Claude
- [ ] Chat sends to `/api/ai/chat`, response shows proposed action + "Send to approvals" button

---

### Phase 8 — Google Ads adapter
**Status: NOT STARTED**

- [ ] `ads_engine/platforms/google.py` — Google Ads API implementation
- [ ] OAuth 2.0 refresh token flow
- [ ] Campaign / ad group / ad fetch
- [ ] Performance metrics (clicks, spend, conversions, ROAS)
- [ ] Write operations (Tier 2 — same approval flow as Meta)
- [ ] Enable in `config/clients/tickets99.yaml`

---

### Phase 9 — WhatsApp + Telegram notifications
**Status: NOT STARTED**

- [ ] `ads_engine/notifications/whatsapp.py` — send approval requests via WhatsApp Business API
- [ ] Webhook handler — parse ✅ / ❌ reply, call approve/reject endpoint
- [ ] `ads_engine/notifications/telegram.py` — Telegram bot with inline approve/reject buttons
- [ ] Daily spend digest (auto-sent at 9 AM)
- [ ] Anomaly alerts (CPC spike, budget overrun)
- [ ] Approval expiry reminders (4h if no response)

---

### Phase 10 — Safety rules engine + audit logs
**Status: NOT STARTED**

- [ ] `ads_engine/core/safety.py` — enforce all rules in `config/safety.yaml` before any execution
- [ ] Hard caps: max daily spend, max single budget change, max campaigns/day
- [ ] Auto-pause: CPC spike detection, spend overrun detection
- [ ] `ads_engine/db/audit.py` — immutable audit log (every action, who approved, when executed)
- [ ] Audit log viewer in settings page
- [ ] Alert on Tier 3 attempts

---

## Running Locally

### Backend

```bash
cd backend
cp .env.example .env        # fill in your API keys
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- Dashboard: http://localhost:3000

---

## Clients

| Client | Platform | Status |
|---|---|---|
| Tickets99 | Meta | Configured (add account IDs to `config/clients/tickets99.yaml`) |
| — | Google | Phase 8 |

---

## Team & Roles

| Name | Role | Access |
|---|---|---|
| Vishnu | Admin | All clients, all actions, Tier 3 |
| Siva | Manager | Tickets99 only, Tier 1 + 2 |
| Vyas | Viewer | Tickets99 reports only, no actions |

---

## Safety Limits (configurable in `config/safety.yaml`)

| Rule | Default |
|---|---|
| Max daily spend per client | ₹50,000 |
| Max single budget change | ₹10,000 |
| Require approval above | ₹5,000 |
| Max new campaigns per day | 5 |
| Auto-pause CPC spike threshold | 200% above 7-day avg |
| Pending action expiry | 24 hours |
