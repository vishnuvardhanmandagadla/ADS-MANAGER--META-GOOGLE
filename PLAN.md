# Ads Engine - Complete Build Plan

## 🎯 Overview

A human-in-the-loop advertising management system that uses AI (Claude) to analyze performance, suggest optimizations, and generate ad copy—but **requires human approval** before executing any actions that spend money or modify campaigns.

**Core Principle:** AI suggests, humans approve, system executes. No money gets spent without your ✅.

---

## 🛡️ Control System Design

### 3 Tiers of Actions

```
┌─────────────────────────────────────────────────┐
│  TIER 1 — AUTO (no approval needed)             │
│  • Pull reports / analytics                     │
│  • Generate ad copy drafts                      │
│  • Budget alerts & notifications                │
│  • Performance monitoring                       │
│  • A/B test data collection                     │
│  • Fetch audience insights                      │
├─────────────────────────────────────────────────┤
│  TIER 2 — APPROVE FIRST (human must approve)    │
│  • Create campaign / adset / ad                 │
│  • Publish / activate any ad                    │
│  • Change budget (increase or decrease)         │
│  • Modify targeting / audience                  │
│  • Duplicate campaigns                          │
│  • Edit ad copy / creatives                     │
├─────────────────────────────────────────────────┤
│  TIER 3 — RESTRICTED (only admin)               │
│  • Delete campaigns                             │
│  • Remove client accounts                       │
│  • Change platform credentials                  │
│  • Override budget caps                         │
│  • Disable safety rules                        │
└─────────────────────────────────────────────────┘
```

### How Approval Works

```
Claude AI suggests       You review in          One click to
  an action        →    approval queue     →    approve/reject
                        (WhatsApp/Web UI)

Example flow:

1. Claude analyzes Tickets99 performance
2. Claude says: "Ad Set 'Broad' is wasting ₹3000/day, 
   I recommend pausing it and creating a new 
   Lookalike 1% ad set with this copy: ..."
3. This goes to APPROVAL QUEUE (not executed)
4. You get a WhatsApp message:

   "🔔 Pending Action — Tickets99
    Action: Pause AdSet 'Broad Audience'
    Reason: CPC ₹8.4 (3x above target)
    Impact: Save ~₹3000/day
    
    Reply: ✅ to approve, ❌ to reject"

5. You reply ✅ → system executes
6. You reply ❌ → nothing happens, logged
```

---

## 🏗️ Architecture

### Directory Structure

```
ads-engine/
├── backend/                         # Python (FastAPI)
│   ├── ads_engine/
│   │   ├── platforms/               # Meta, Google, TikTok adapters
│   │   ├── models/                  # Pydantic models
│   │   ├── core/                    # Engine, middleware, scheduler
│   │   ├── ai/                      # Claude-powered intelligence
│   │   ├── approval/                # Human-in-the-loop system
│   │   │   ├── queue.py             # Pending actions queue (DB-backed)
│   │   │   ├── action.py            # Action model (what, why, impact, tier)
│   │   │   ├── reviewer.py          # Send to human, wait for response
│   │   │   ├── executor.py          # Execute approved actions only
│   │   │   └── policies.py          # Tier rules (what needs approval)
│   │   ├── api/                     # FastAPI endpoints
│   │   ├── db/                      # Database models & migrations
│   │   └── utils/
│   ├── config/
│   │   ├── settings.yaml
│   │   ├── safety.yaml              # Spend limits, rules
│   │   └── clients/
│   ├── tests/
│   ├── main.py
│   └── requirements.txt
│
├── frontend/                        # Next.js (React)
│   ├── app/
│   │   ├── dashboard/               # Home overview
│   │   ├── clients/                 # Client management
│   │   ├── campaigns/               # Campaign control
│   │   ├── approvals/               # Approval queue
│   │   ├── ai-chat/                 # AI assistant
│   │   └── settings/                # Config & team
│   ├── components/
│   │   ├── charts/
│   │   ├── tables/
│   │   └── approval-card/
│   └── package.json
│
└── README.md
```

### The Action Model

```python
# Every action that touches ad platforms goes through this

class PendingAction:
    id: str
    client_id: str
    platform: str                    # meta / google / tiktok
    tier: int                        # 1=auto, 2=approve, 3=restricted
    action_type: str                 # create_campaign, update_budget, pause_ad...
    description: str                 # Human-readable: "Pause AdSet 'Broad'"
    reason: str                      # AI-generated: "CPC 3x above target"
    estimated_impact: str            # "Save ~₹3000/day"
    payload: dict                    # Actual API call parameters
    status: str                      # pending → approved → executed / rejected
    created_at: datetime
    reviewed_by: str                 # who approved
    reviewed_at: datetime
    executed_at: datetime
```

---

## 🔔 Approval Channels

| Channel | How |
|---|---|
| **WhatsApp** | Bot sends action summary, reply ✅/❌ |
| **Web Dashboard** | Queue page with approve/reject buttons |
| **Telegram** | Inline buttons on bot messages |
| **Email** | Action summary with approve/reject links |
| **API** | `PATCH /actions/{id}/approve` for custom integrations |

---

## ⚠️ Safety Rules (Non-Negotiable)

```yaml
# config/safety.yaml
rules:
  max_daily_spend_per_client: 50000
  max_single_budget_change: 10000         # Can't change more than ₹10K at once
  require_approval_above: 5000            # Any spend > ₹5K needs approval
  max_campaigns_per_day: 5                # Don't create more than 5 campaigns/day
  cool_down_after_reject: 60              # Wait 60 min before re-suggesting
  auto_pause_on_anomaly: true             # If CPC spikes 200%, auto-pause
  never_delete_without_admin: true        # Tier 3 enforced
  log_everything: true                    # Every action, approved or not
```

---

## 🎨 UI Stack

| Layer | Tech | Why |
|---|---|---|
| **Frontend** | Next.js (React) | Fast, SSR, great UI libraries |
| **UI Components** | shadcn/ui + Tailwind | Clean, professional, free |
| **Charts** | Recharts | Lightweight, React-native |
| **Real-time** | WebSocket | Live updates on dashboard |
| **Auth** | NextAuth.js | Login system for you + clients |
| **Backend** | FastAPI (our ads-engine) | Already building this |

---

## 📱 Dashboard Pages

### 1. Login & Role System

```
You (Admin)     → See everything, approve everything, all clients
Siva (Manager)  → See Tickets99 only, can request actions, can approve tier 2
Vyas (Viewer)   → See reports only, no actions
Client B team   → See only their data
```

### 2. Main Dashboard (Home)

```
┌──────────────────────────────────────────────────────────┐
│  ads-engine                    🔔 3 pending    👤 Vishnu │
├──────────┬───────────────────────────────────────────────┤
│          │                                               │
│ 📊 Home  │  Today's Overview                             │
│ 👥 Clients│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│ 📢 Campaigns│ │ ₹24,500 │ │ 12,340  │ │ ₹3.2    │       │
│ ✅ Approvals│ │ Spend   │ │ Clicks  │ │ Avg CPC │       │
│ 🤖 AI Logs│  └─────────┘ └─────────┘ └─────────┘       │
│ ⚙️ Settings│                                             │
│          │  Clients Performance                          │
│          │  ┌──────────────────────────────────────┐     │
│          │  │ Tickets99  ● Meta  ₹12.4K  ✅ Good  │     │
│          │  │ Client B   ● Google ₹8.1K  ⚠️ High │     │
│          │  │ Client C   ● Meta  ₹4.0K  ✅ Good  │     │
│          │  └──────────────────────────────────────┘     │
│          │                                               │
│          │  [Spend chart across all clients this week]   │
│          │                                               │
└──────────┴───────────────────────────────────────────────┘
```

### 3. Approval Queue (Most Important Page)

```
┌──────────────────────────────────────────────────────────┐
│  ✅ Approval Queue                    3 pending actions  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  🟡 PENDING — 2 min ago                                  │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Create Campaign "Chennai Weekend Events"            │  │
│  │ Client: Tickets99  |  Platform: Meta               │  │
│  │                                                    │  │
│  │ AI Reason: "Weekend events get 2x engagement in    │  │
│  │ Chennai. Suggested budget ₹3000/day, targeting     │  │
│  │ 18-35, interests: concerts, nightlife"             │  │
│  │                                                    │  │
│  │ Budget: ₹3,000/day  |  Duration: 7 days           │  │
│  │ Estimated reach: 45,000  |  Est. CPC: ₹2.8        │  │
│  │                                                    │  │
│  │ 📋 Preview Ad Copy:                                │  │
│  │ "Weekend plans sorted! 🎶 Book now on Tickets99"   │  │
│  │                                                    │  │
│  │  [✅ Approve]  [✏️ Edit & Approve]  [❌ Reject]    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  🟡 PENDING — 15 min ago                                 │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Pause AdSet "Broad Audience"                       │  │
│  │ Client: Tickets99  |  Platform: Meta               │  │
│  │                                                    │  │
│  │ AI Reason: "CPC ₹8.4, 3x above target. Spent     │  │
│  │ ₹4,200 with only 12 conversions. Recommend        │  │
│  │ shifting budget to Lookalike 1%"                   │  │
│  │                                                    │  │
│  │  [✅ Approve]  [❌ Reject]  [⏸️ Decide Later]     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ✅ APPROVED — 1 hour ago                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Budget increase "Hyderabad Events" ₹2000 → ₹3500  │  │
│  │ Approved by: Vishnu  |  Executed: ✅               │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 4. Campaign Control Panel

```
┌──────────────────────────────────────────────────────────┐
│  📢 Tickets99 > Meta > Campaign: Hyderabad Events       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Status: ● Active     Budget: ₹3,500/day                │
│  [⏸️ Pause]  [✏️ Edit Budget]  [📋 Duplicate]           │
│                                                          │
│  Performance (Last 7 Days)                               │
│  ┌────────────────────────────────────────────┐          │
│  │  📈 [Line chart: Spend, Clicks, CPC]      │          │
│  │     Mon  Tue  Wed  Thu  Fri  Sat  Sun      │          │
│  └────────────────────────────────────────────┘          │
│                                                          │
│  Ad Sets                                                 │
│  ┌──────────────┬──────┬───────┬─────┬────────────────┐  │
│  │ Name         │ Spend│ Clicks│ CPC │ Status         │  │
│  ├──────────────┼──────┼───────┼─────┼────────────────┤  │
│  │ Lookalike 1% │₹1800 │  620  │₹2.9 │ ● Active      │  │
│  │ Interest     │₹1200 │  380  │₹3.2 │ ● Active      │  │
│  │ Broad        │₹ 500 │   60  │₹8.3 │ ⚠️ Flagged   │  │
│  └──────────────┴──────┴───────┴─────┴────────────────┘  │
│                                                          │
│  🤖 AI Insight:                                          │
│  "Lookalike 1% is your best performer. Consider          │
│   increasing its budget by 30%. Broad audience           │
│   should be paused — CPC 3x above target."               │
│                                                          │
│  [🤖 Ask AI to Optimize]  [📊 Full Report]              │
└──────────────────────────────────────────────────────────┘
```

### 5. AI Chat Panel (Built-in)

```
┌──────────────────────────────────────────────────────────┐
│  🤖 AI Assistant                                         │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  You: "Create a campaign for Tickets99 targeting         │
│        college students in Hyderabad for weekend         │
│        concerts, budget ₹5000/day"                       │
│                                                          │
│  AI: "Here's what I'll set up:                           │
│                                                          │
│   Campaign: Hyd College Weekend Concerts                 │
│   Platform: Meta                                         │
│   Budget: ₹5,000/day                                    │
│   Targeting:                                             │
│     Age: 18-24                                           │
│     Location: Hyderabad (25km radius)                    │
│     Interests: Live music, concerts, college events      │
│   Ad Copy (3 variations):                                │
│     A: "Your weekend just got better 🎵..."              │
│     B: "College night out? Book now..."                  │
│     C: "₹299 only! Hyderabad's hottest..."              │
│                                                          │
│   ⚡ This will be sent to your approval queue.           │
│   Want me to proceed?"                                   │
│                                                          │
│  You: "yes but change budget to 3000"                    │
│                                                          │
│  AI: "Done. Sent to approval queue with ₹3,000/day      │
│   budget. Check your approvals tab to publish."          │
│                                                          │
│  [Type a message...]                              [Send] │
└──────────────────────────────────────────────────────────┘
```

### 6. Settings Page

```
┌──────────────────────────────────────────────────────────┐
│  ⚙️ Settings                                             │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Safety Rules                                            │
│  ├── Max daily spend per client    [₹ 50,000  ]         │
│  ├── Max single budget change      [₹ 10,000  ]         │
│  ├── Auto-pause on CPC spike       [✅ enabled ]  [200%]│
│  └── Require approval above        [₹  5,000  ]         │
│                                                          │
│  Notification Channels                                   │
│  ├── WhatsApp alerts               [✅] +91XXXXXXXXXX   │
│  ├── Telegram alerts               [❌] not configured   │
│  └── Email digest                  [✅] daily at 9 AM   │
│                                                          │
│  Approval Settings                                       │
│  ├── Auto-approve reports          [✅]                  │
│  ├── Auto-approve pause on anomaly [❌]                  │
│  └── Expiry for pending actions    [ 24 hours ]          │
│                                                          │
│  Team                                                    │
│  ┌──────────┬──────────┬────────────┐                    │
│  │ Name     │ Role     │ Client     │                    │
│  ├──────────┼──────────┼────────────┤                    │
│  │ Vishnu   │ Admin    │ All        │                    │
│  │ Siva     │ Manager  │ Tickets99  │                    │
│  │ Vyas     │ Viewer   │ Tickets99  │                    │
│  └──────────┴──────────┴────────────┘                    │
│  [+ Add Team Member]                                     │
└──────────────────────────────────────────────────────────┘
```

---

## 🚀 Build Order

| Phase | What | Output |
|---|---|---|
| **1** | Backend scaffold + config + platform base | Working Python project with config system |
| **2** | Meta adapter + basic campaign operations | Can pull/create campaigns via Meta API |
| **3** | **Approval system (queue + policies)** | Actions require ✅ before execution |
| **4** | FastAPI endpoints + WebSocket | Backend API ready for frontend |
| **5** | Claude AI layer | Smart suggestions + ad copy generation |
| **6** | Frontend — Dashboard + Approval Queue | You can see & approve actions |
| **7** | Frontend — Campaign control + AI chat | Full control UI |
| **8** | Google Ads adapter | Second platform support |
| **9** | WhatsApp/Telegram notifications | Approve from phone |
| **10** | Safety rules engine + audit logs | Production-ready with full logging |

---

## 🔑 Key Principles

1. **Human-in-the-loop is non-negotiable** - No money gets spent without approval
2. **AI suggests, humans decide** - Claude provides analysis and recommendations, you make the call
3. **Full transparency** - Every action is logged, every decision is tracked
4. **Safety first** - Multiple layers of protection (tiers, rules, caps)
5. **Multi-channel approval** - Approve via web, WhatsApp, Telegram, or API
6. **Role-based access** - Different users see different data and have different permissions

---

## 📋 Next Steps

1. Start with Phase 1: Backend scaffold
2. Build approval system early (Phase 3) - this is the core differentiator
3. Get basic UI working (Phase 6) so you can see and approve actions
4. Iterate on AI suggestions (Phase 5) to make them more valuable
5. Add platforms incrementally (Phase 8+)

**You control everything from one screen. AI does the thinking. You press the button.**
