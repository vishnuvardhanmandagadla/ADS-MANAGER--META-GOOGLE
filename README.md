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
**Status: COMPLETE — Audited & Verified (2026-03-12)**

- [x] Project directory structure (`backend/` + `frontend/`)
- [x] `requirements.txt` — all Python dependencies pinned
- [x] `.env.example` — all secrets documented (Meta, Google, Claude, WhatsApp)
- [x] `config/settings.yaml` — app config (CORS, scheduler, AI model)
- [x] `config/safety.yaml` — spend limits, anomaly rules, Tier 3 restrictions
- [x] `config/clients/tickets99.yaml` — first client config
- [x] `ads_engine/models/base.py` — all Pydantic models (Campaign, AdSet, Ad, Targeting, PerformanceReport...)
- [x] `ads_engine/platforms/base.py` — abstract platform adapter interface with Tier 1/2/3 annotations
- [x] `ads_engine/core/config.py` — settings loader (env + YAML, cached)
- [x] `main.py` — FastAPI app with CORS, lifespan, /health endpoint
- [x] Frontend scaffold — Next.js 15, Tailwind, all page routes stubbed
- [x] `frontend/next.config.ts` — API proxy to FastAPI backend
- [x] `frontend/postcss.config.mjs` — required for Tailwind CSS to compile
- [x] `frontend/app/clients/page.tsx` — clients page stub (was in architecture, missing from initial build)

#### Audit Log (2026-03-12) — Initial build + post-audit fixes
| # | Issue | Fix |
|---|---|---|
| Bug 1 | `config.py` ROOT path `parents[3]` → project root, YAML files would not load | Fixed to `parents[2]` → `backend/` |
| Bug 2 | `httpx` duplicated in `requirements.txt` | Removed duplicate |
| Bug 3 | Unused imports (`os`, `field_validator`) in `config.py` | Removed |
| Missing 1 | `frontend/app/clients/page.tsx` missing from initial build | Added |
| Missing 2 | `frontend/postcss.config.mjs` missing — Tailwind would not compile | Added |

#### Cross-phase audit (2026-03-12) — All phases reviewed together
| # | Issue | File | Fix |
|---|---|---|---|
| Bug 4 | `datetime.utcnow()` deprecated in Python 3.12 (1 occurrence) | `models/base.py` | Replaced with `datetime.now(timezone.utc)` |

#### Audit Log (2026-03-12)
> Full file-by-file review conducted after initial build. 3 bugs found and fixed, 2 missing files added.

| # | Issue | Fix |
|---|---|---|
| Bug 1 | `config.py` ROOT path used `parents[3]` → pointed to project root, config files would not load at runtime | Fixed to `parents[2]` → resolves to `backend/` correctly (verified) |
| Bug 2 | `httpx` listed twice in `requirements.txt` | Removed duplicate |
| Bug 3 | Unused imports in `config.py` (`import os`, `from pydantic import field_validator`) | Removed |
| Missing 1 | `frontend/app/clients/page.tsx` listed in architecture nav but not created | Added |
| Missing 2 | `frontend/postcss.config.mjs` required for Tailwind CSS compilation — `npm run dev` would fail without it | Added |

---

### Phase 2 — Meta Ads platform adapter
**Status: COMPLETE — Audited & Verified (2026-03-12) — 15/15 tests passing**

- [x] `ads_engine/platforms/meta.py` — full Meta Marketing API v21.0 implementation
- [x] Authentication with long-lived access tokens (`/me` validation)
- [x] `get_campaigns()` — fetch all campaigns for a client account
- [x] `get_adsets()` — fetch ad sets with targeting (age, gender, location, interests)
- [x] `get_ads()` — fetch ads with creative (headline, body, image, CTA)
- [x] `get_campaign_performance()` / `get_adset_performance()` — pull Insights (spend, clicks, CPC, CPM, CTR, ROAS, conversions)
- [x] `create_campaign()` — always creates as PAUSED, never goes live without review
- [x] `create_adset()` — builds Meta targeting spec from our Targeting model
- [x] `create_ad()` — creates ad creative then links ad, starts PAUSED
- [x] `update_campaign_budget()` — budget in INR, converted to paise for Meta API
- [x] `set_campaign_status()` / `set_adset_status()` — pause / activate (rejects invalid statuses)
- [x] `update_adset_targeting()` — modify audience targeting on existing ad sets
- [x] `delete_campaign()` — Tier 3, sets status to DELETED + warning log
- [x] `duplicate_campaign()` — uses Meta's `/copies` endpoint, deep copy, starts PAUSED
- [x] Rate limit handling — detects code 17/32, exponential backoff, 3 retries
- [x] Timeout retry — 3 attempts with backoff on `httpx.TimeoutException`
- [x] `tests/test_meta_adapter.py` — 15 unit tests, all passing, zero real API calls

#### Test Results (2026-03-12)
```
15 passed in 0.13s
```
#### Audit Log (2026-03-12) — Cross-phase review
| # | Issue | Fix |
|---|---|---|
| Bug 5 | `datetime.utcnow()` deprecated (5 occurrences) | Replaced with `datetime.now(timezone.utc)` + added `timezone` import |
| Bug 6 | `str(dict).replace("'", '"')` fragile JSON in `create_adset`, `create_ad`, `update_adset_targeting`, `duplicate_campaign` — breaks if any string value contains a single quote | Replaced all 4 occurrences with `json.dumps()` + added `import json` |

| Test | Result |
|---|---|
| `test_authenticate_success` | PASSED |
| `test_authenticate_failure` | PASSED |
| `test_get_campaigns_returns_list` | PASSED |
| `test_get_campaigns_empty` | PASSED |
| `test_get_adsets` | PASSED |
| `test_get_campaign_performance` | PASSED |
| `test_get_campaign_performance_no_data` | PASSED |
| `test_set_campaign_status_active` | PASSED |
| `test_set_campaign_status_invalid` | PASSED |
| `test_update_campaign_budget` | PASSED |
| `test_meta_api_error_propagates` | PASSED |
| `test_parse_status_known_values` | PASSED |
| `test_parse_status_unknown_defaults_to_paused` | PASSED |
| `test_parse_metrics_empty` | PASSED |
| `test_parse_metrics_full` | PASSED |

---

### Phase 3 — Approval system (human-in-the-loop)
**Status: COMPLETE — Audited & Verified (2026-03-12) — 45/45 tests passing**

- [x] `ads_engine/approval/action.py` — `PendingAction` model with full state machine (PENDING → APPROVED → EXECUTED / REJECTED / FAILED / EXPIRED / CANCELLED)
- [x] `ActionType` enum — all 16 action types classified by tier (GET_CAMPAIGNS through DELETE_CAMPAIGN)
- [x] Factory helpers — `PendingAction.tier1()`, `.tier2()`, `.tier3()` for clean construction
- [x] `ads_engine/approval/policies.py` — `ApprovalPolicy` with 5 safety checks:
  - Daily spend cap per client (₹50,000)
  - Max single budget change (₹10,000)
  - Max new campaigns per day (5)
  - Cool-down after rejection (60 min — won't re-suggest same action)
  - Absolute Tier 3 restrictions (delete, disable safety, override caps)
- [x] `ads_engine/approval/queue.py` — in-memory queue with JSON file persistence (survives restarts). Full CRUD: enqueue, approve, reject, cancel, expire, mark_executed, mark_failed
- [x] `ads_engine/approval/executor.py` — `ActionExecutor` dispatches approved actions to the correct platform adapter method. Refuses to run unapproved actions.
- [x] `ads_engine/approval/reviewer.py` — `ActionReviewer` formats WhatsApp messages and dashboard cards. Phase 9 will wire up real channels.
- [x] Queue initialised at app startup in `main.py` lifespan
- [x] `tests/test_approval.py` — 45 unit tests covering all components

#### Audit Log (2026-03-12) — Cross-phase review
| # | Issue | File | Fix |
|---|---|---|---|
| Bug 7 | `datetime.utcnow()` deprecated (8 occurrences in action.py, 3 in policies.py) | `action.py`, `policies.py` | Replaced all with `datetime.now(timezone.utc)` + added `timezone` import |
| Bug 8 | `from datetime import timedelta` imported but never used | `policies.py` | Removed |
| Bug 9 | `if TYPE_CHECKING: pass` — dead code block | `policies.py` | Removed |

#### Test Results (2026-03-12) — Post-audit, zero deprecation warnings
```
60 passed total (15 Phase 2 + 45 Phase 3) in 0.21s — 0 warnings
```

---

### Phase 4 — FastAPI endpoints + WebSocket
**Status: COMPLETE — Audited & Verified (2026-03-12) — 88/88 tests passing (28 new)**

- [x] `ads_engine/api/schemas.py` — all request/response Pydantic models (LoginRequest, TokenResponse, ClientSummary, ActionCardResponse, ApproveRequest, RejectRequest, ApprovalsListResponse)
- [x] `ads_engine/api/auth.py` — JWT creation/verification + hardcoded users (sha256_crypt, no bcrypt dependency)
- [x] `ads_engine/api/deps.py` — FastAPI dependency injection: get_queue, get_current_user, require_admin, require_approver, check_client_access
- [x] `ads_engine/api/router.py` — assembles all sub-routers under `/api/v1`
- [x] `POST /api/v1/auth/login` — username + password → JWT token (8h sessions)
- [x] `GET /api/v1/auth/me` — return current user info from token
- [x] `GET /api/v1/clients` — list all clients (admin sees all; manager sees assigned)
- [x] `GET /api/v1/clients/{id}` — client detail (403 if wrong manager)
- [x] `GET /api/v1/approvals` — pending actions (scoped by role/client)
- [x] `GET /api/v1/approvals/all` — all actions with optional `?status=` filter
- [x] `GET /api/v1/approvals/{id}` — single action detail
- [x] `POST /api/v1/approvals/{id}/approve` — approve action (manager/admin only)
- [x] `POST /api/v1/approvals/{id}/reject` — reject with reason (manager/admin only)
- [x] `POST /api/v1/approvals/{id}/cancel` — cancel pending action
- [x] `WS /ws` — real-time event feed (connected, action_queued, action_approved, action_rejected, pong)
- [x] `ConnectionManager` — tracks all WebSocket connections, broadcasts per-client or global events
- [x] Role-based access: viewer=read-only, manager=assigned clients + approve/reject, admin=everything
- [x] `GET /health` — health check endpoint
- [x] `tests/test_api.py` — 28 tests covering all endpoints, auth flows, RBAC, and WebSocket

#### Audit Log (2026-03-12) — Phase 4 build + fixes
| # | Issue | Fix |
|---|---|---|
| Bug 10 | `passlib` + `bcrypt` version incompatibility — bcrypt's 72-byte self-test fails at import, crashing all tests | Switched from `bcrypt` to `sha256_crypt`; pre-computed hashes stored as string literals |
| Bug 11 | `deps.py` imported `approval_queue` at module load (captured `None`); reassignment in `init_queue()` was invisible to the dep function | Changed to access `_queue_module.approval_queue` live via module reference |
| Bug 12 | WebSocket route registered under `/api/v1` prefix → endpoint was at `/api/v1/ws` instead of `/ws` | Moved WebSocket router to app-level in `main.py` (no version prefix) |
| Bug 13 | `lifespan` always called `init_queue()` at startup, overwriting the test fixture's queue with a fresh empty one | Added guard: skip `init_queue()` if queue already initialised |

#### Test Results (2026-03-12) — 88 passing, 0 failing, 0 warnings
```
88 passed in 8.43s
```

---

### Phase 5 — Claude AI layer
**Status: COMPLETE — Audited & Verified (2026-03-12) — 121/121 tests passing (33 new)**

- [x] `ads_engine/ai/client.py` — Anthropic SDK wrapper: `complete(system, messages)` with model + token config from settings.yaml
- [x] `ads_engine/ai/context.py` — `build_system_prompt(client_id)` injects client name, industry, audience, spend limits, and CPC targets into every Claude call
- [x] `ads_engine/ai/chat.py` — `ChatSession` with stateful message history. Natural language → `PendingAction` via structured JSON. Auto-queues tier 2/3 actions for human approval.
- [x] `ads_engine/ai/analyst.py` — `analyze_performance()` takes PerformanceReports and returns structured insights (winners, underperformers, anomalies, recommended_actions)
- [x] `ads_engine/ai/optimizer.py` — `suggest_optimizations()` proposes budget shifts and audience changes as `list[PendingAction]`
- [x] `ads_engine/ai/copywriter.py` — `generate_copy()` produces headline + body + CTA variations for a product/audience
- [x] `POST /api/v1/ai/chat` — REST endpoint: message in, response + queued actions out
- [x] `POST /api/v1/ai/copy` — REST endpoint: generate ad copy variations (1-10)
- [x] Client context injected into every prompt — Tickets99's audience, CPC targets, spend limits
- [x] All suggestions route through approval queue — Claude never executes directly
- [x] Tier routing: AI suggestions become Tier 1 (auto), Tier 2 (approve), or Tier 3 (admin) based on action type
- [x] Graceful fallback: non-JSON Claude responses don't crash — return empty action list
- [x] `tests/test_ai.py` — 33 tests covering all AI modules + endpoints, zero real API calls (all mocked)

#### Audit Log (2026-03-12) — Phase 5 build + fixes
| # | Issue | Fix |
|---|---|---|
| Bug 14 | `_build_pending_action` did `.upper()` on action type but `ActionType` values are lowercase | Changed to `.lower()` — now accepts both `"PAUSE_ADSET"` and `"pause_adset"` from Claude |
| Bug 15 | `PendingAction.tier1()` called with `reason`/`estimated_impact` kwargs it doesn't accept | Tier 1 factory called with only the 5 params it expects |
| Bug 16 | `Platform.TIKTOK` exists — `"tiktok"` is a valid platform, test used wrong invalid value | Changed bad-platform test to `"facebook"` |
| Bug 17 | Test fixtures for `Campaign`, `AdSet`, `PerformanceReport` missing required fields (`client_id`, `created_at`, `updated_at`, `entity_type`, `date_from`, `date_to`) | All fixture helpers updated |

#### Test Results (2026-03-12) — 121 passing, 0 failing, 0 warnings
```
121 passed in 12.77s
```

---

### Phase 6 — Frontend: Dashboard + Approval Queue + Settings
**Status: COMPLETE — Build passing (2026-03-12) — 9/9 routes, 0 TypeScript errors**

- [x] `app/lib/api.ts` — typed fetch wrapper: JWT auth headers, 401 redirect, all backend API calls
- [x] `app/lib/auth.tsx` — React Context auth state (JWT stored in localStorage, role-aware)
- [x] `app/lib/ws.ts` — `useWebSocket` hook with auto-reconnect (3s back-off)
- [x] `app/components/Sidebar.tsx` — dark sidebar with nav links, pending badge (updates via WebSocket), user avatar + logout
- [x] `app/components/DashboardLayout.tsx` — auth guard + sidebar wrapper used by all dashboard pages
- [x] `app/login/page.tsx` — login form with JWT session creation + demo account shortcuts
- [x] `app/dashboard/page.tsx` — today's overview: metrics bar, spend chart, clients table
- [x] `app/dashboard/components/MetricsBar.tsx` — 4 stat cards: spend, clicks, avg CPC, pending approvals count
- [x] `app/dashboard/components/SpendChart.tsx` — 7-day spend area chart (Recharts)
- [x] `app/dashboard/components/ClientsTable.tsx` — per-client table with platform badges + daily cap
- [x] `app/approvals/page.tsx` — full approval queue with Pending / Approved / Rejected / Executed tabs + live WebSocket refresh
- [x] `app/approvals/components/ActionCard.tsx` — action card with approve (1-click) + reject (with reason input) + status display
- [x] `app/settings/page.tsx` — safety limits, tier system, team access, notification channels
- [x] `app/clients/page.tsx` — clients list from live API
- [x] RBAC enforced on all actions: viewer sees queue but cannot approve/reject
- [x] Build: `next build` passes clean — 9 routes, 0 TypeScript errors, 0 lint errors

#### Audit Log (2026-03-12) — Phase 6 build
| # | Issue | Fix |
|---|---|---|
| Bug 18 | `npm install` fails — `&` in directory path breaks cmd.exe postinstall scripts | Run with `--ignore-scripts` flag; native packages not needed |
| Bug 19 | `autoprefixer` missing (skipped by `--ignore-scripts`) — Next.js CSS pipeline fails at build | Installed separately with `--ignore-scripts` |

#### Build Output (2026-03-12)
```
✓ Compiled successfully
✓ 9 routes — 0 TypeScript errors
/login /dashboard /approvals /campaigns /clients /ai-chat /settings
```

---

### Phase 7 — Frontend: Campaign Control + AI Chat
**Status: COMPLETE — Build passing (2026-03-12) — 137/137 backend tests, 0 TypeScript errors**

#### Backend (16 new tests — 137 total)
- [x] `GET /api/v1/clients/{client_id}/campaigns` — returns 4 realistic mock campaigns (Chennai Events, Hyderabad Retargeting, Bangalore Comedy Night, Sports Lookalike)
- [x] `POST /api/v1/actions` — creates PendingAction directly from UI controls (manager/admin only via `require_approver`)
- [x] Platform + action_type validation — 400 on unknown values
- [x] Tier 3 gate — 403 if non-admin tries delete/disable/override actions
- [x] `tests/test_campaigns.py` — 16 tests, all passing

#### Frontend
- [x] `app/campaigns/components/BudgetModal.tsx` — modal to edit daily budget; shows ±delta, queues `update_budget` action
- [x] `app/campaigns/components/CampaignCard.tsx` — card per campaign with status badge (green/yellow/grey), 4-metric grid (Budget / Spend / CPC+CTR / ROAS with trend icon), Pause/Activate toggle + Edit Budget button (RBAC — hidden for viewers)
- [x] `app/campaigns/page.tsx` — full campaign list: client selector tabs, campaigns grouped Active → Paused → Other, refresh button, loading skeleton, green toast on queue
- [x] `app/ai-chat/page.tsx` — conversational Claude UI: message bubbles, typing indicator (3 bouncing dots), queued actions shown inline below each response with Pending badge, starter prompts on welcome screen, client selector resets conversation

#### Audit Log (2026-03-12)
| # | Issue | Fix |
|---|---|---|
| — | No bugs found — clean first build | — |

#### Build Output (2026-03-12)
```
✓ TypeScript: 0 errors
✓ Backend: 137/137 tests passing
✓ Routes: /login /dashboard /approvals /campaigns /clients /ai-chat /settings
```

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
