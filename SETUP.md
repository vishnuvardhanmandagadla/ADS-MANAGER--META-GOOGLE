# Ads Engine — Complete Setup Guide

Everything you need to provide to run this system end-to-end.
No keys or account IDs are baked into the code — all are injected via `.env` and YAML config files.

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [API Keys & Credentials](#2-api-keys--credentials)
   - [Anthropic (Claude AI)](#21-anthropic-claude-ai)
   - [Meta (Facebook) Ads](#22-meta-facebook-ads)
   - [WhatsApp Business Cloud](#23-whatsapp-business-cloud)
   - [Google Ads](#24-google-ads)
3. [Environment File (.env)](#3-environment-file-env)
4. [Client Config (YAML)](#4-client-config-yaml)
5. [Safety Config (YAML)](#5-safety-config-yaml)
6. [Backend Setup](#6-backend-setup)
7. [Frontend Setup](#7-frontend-setup)
8. [Running the System](#8-running-the-system)
9. [SDK & Library Reference](#9-sdk--library-reference)
10. [Webhook Setup (Meta / WhatsApp)](#10-webhook-setup-meta--whatsapp)
11. [First-Time Login](#11-first-time-login)

---

## 1. System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20 LTS |
| npm | 9 | 10 |
| OS | Windows 10 / macOS 12 / Ubuntu 22 | Any |
| RAM | 2 GB | 4 GB |
| Internet | Required (external APIs) | — |

---

## 2. API Keys & Credentials

### 2.1 Anthropic (Claude AI)

**What it does:** Powers the AI chat — Claude reads campaign data and suggests optimisation actions.

**How to get it:**
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in / create account
3. Go to **API Keys** → **Create Key**
4. Copy the key — starts with `sk-ant-...`

**What to fill in `.env`:**
```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

**Model used:** `claude-opus-4-5` (hardcoded in `ads_engine/api/routes/ai.py`)
**Billing:** Pay-per-token. Typical ad analysis chat: ~$0.01–0.05 per message.

---

### 2.2 Meta (Facebook) Ads

**What it does:** Reads and manages Facebook/Instagram ad campaigns for your clients.

**How to get it:**

#### Step 1 — Create a Meta App
1. Go to [developers.facebook.com](https://developers.facebook.com)
2. **My Apps** → **Create App** → choose **Business** type
3. Note your **App ID** and **App Secret** from Settings → Basic

#### Step 2 — Get an Access Token
1. In your app, add the **Marketing API** product
2. Go to **Tools** → **Graph API Explorer**
3. Select your app, click **Generate Access Token**
4. Add permissions: `ads_management`, `ads_read`, `business_management`, `pages_read_engagement`
5. Click **Generate** — copy the short-lived token
6. **Important:** Convert to a long-lived token (60-day):
   ```
   GET https://graph.facebook.com/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id=YOUR_APP_ID
     &client_secret=YOUR_APP_SECRET
     &fb_exchange_token=SHORT_LIVED_TOKEN
   ```
7. For production use a **System User Token** (never expires) — go to **Business Manager** → **System Users** → **Generate Token**

#### Step 3 — Find your Ad Account ID
1. Go to [business.facebook.com/adsmanager](https://business.facebook.com/adsmanager)
2. URL contains your account ID — format is `act_XXXXXXXXXX`
3. Also note your **Facebook Page ID** (from your Page's About section) and **Pixel ID** (Events Manager)

**What to fill in `.env`:**
```
META_APP_ID=1234567890
META_APP_SECRET=abcdef1234567890abcdef1234567890
META_ACCESS_TOKEN=EAAxxxxxxxxx...
```

**What to fill in `config/clients/tickets99.yaml`:**
```yaml
platforms:
  meta:
    ad_account_id: "act_1234567890"
    page_id: "123456789012345"
    pixel_id: "123456789012345"
```

---

### 2.3 WhatsApp Business Cloud

**What it does:** Sends approval request messages to your phone. You reply `APPROVE abc12345` or `REJECT abc12345 reason` to approve/reject actions without opening the dashboard.

**How to get it:**

#### Step 1 — Enable WhatsApp in your Meta App
1. In the same Meta App (from 2.2), add the **WhatsApp** product
2. Go to **WhatsApp** → **Getting Started**
3. You'll see a **Temporary Access Token** and a **Phone Number ID** — copy both
4. For production, generate a permanent System User token with `whatsapp_business_messaging` permission

#### Step 2 — Add a real phone number
1. Go to **WhatsApp** → **Phone Numbers** → **Add Phone Number**
2. Verify your business phone number with OTP
3. Note the **Phone Number ID** for this number

#### Step 3 — Set your verify token
- This is a secret string you invent yourself (e.g., `ads-engine-wh-secret-2024`)
- You'll enter the same string in both `.env` AND the Meta developer console when registering the webhook

**What to fill in `.env`:**
```
WHATSAPP_API_TOKEN=EAAxxxxxxxxx...        # Bearer token from Meta
WHATSAPP_PHONE_NUMBER_ID=123456789012345  # From WhatsApp > Phone Numbers
WHATSAPP_VERIFY_TOKEN=ads-engine-wh-secret-2024  # Your invented secret
ADMIN_WHATSAPP=+919876543210              # Your WhatsApp number (receives alerts)
```

---

### 2.4 Google Ads

**What it does:** Reads and manages Google Ads campaigns.

**How to get it:**

#### Step 1 — Developer Token
1. Go to [Google Ads API Center](https://developers.google.com/google-ads/api/docs/get-started/dev-token)
2. Sign into your **Google Ads Manager Account** (MCC)
3. **Tools & Settings** → **API Center** → Apply for basic access
4. Copy the **Developer Token** — looks like `ABcd1234efGH5678`

> **Note:** New developer tokens start with test access. You can test against test accounts immediately. Production access requires Google review.

#### Step 2 — OAuth 2.0 Client
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project (or use existing)
3. Enable the **Google Ads API**
4. Go to **APIs & Services** → **Credentials** → **Create OAuth Client ID**
5. Choose **Desktop App** type
6. Download the JSON — note `client_id` and `client_secret`

#### Step 3 — Refresh Token
Run this one-time locally to get a refresh token:
```bash
pip install google-auth-oauthlib
python -c "
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_secrets_file(
    'client_secret.json',
    scopes=['https://www.googleapis.com/auth/adwords']
)
creds = flow.run_local_server(port=0)
print('Refresh token:', creds.refresh_token)
"
```

#### Step 4 — Customer ID
- Your Google Ads Customer ID is the 10-digit number shown at the top right of Google Ads UI (format: `XXX-XXX-XXXX`)
- Remove dashes when entering in config: `1234567890`

**What to fill in `.env`:**
```
GOOGLE_ADS_DEVELOPER_TOKEN=ABcd1234efGH5678
GOOGLE_ADS_CLIENT_ID=123456789012-abc.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=GOCSPX-abcdefghij
GOOGLE_ADS_REFRESH_TOKEN=1//0g-xxxxxxxxxxxxxxxxxx
```

**What to fill in `config/clients/tickets99.yaml`:**
```yaml
platforms:
  google:
    enabled: true
    customer_id: "1234567890"  # 10 digits, no dashes
```

---

## 3. Environment File (.env)

Create `backend/.env` by copying the example:
```bash
cd backend
cp .env.example .env
```

Then fill in every value:

```env
# ── App ──────────────────────────────────────────────────────────────────
APP_ENV=production           # development | production
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
DEBUG=false

# ── Database ─────────────────────────────────────────────────────────────
# Option A — PostgreSQL (production)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ads_engine

# Option B — SQLite (local dev, no setup needed)
# DATABASE_URL=sqlite+aiosqlite:///./ads_engine.db

# ── Claude AI ────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-api03-...

# ── Meta (Facebook) Ads ──────────────────────────────────────────────────
META_APP_ID=1234567890
META_APP_SECRET=abcdef1234567890abcdef1234567890
META_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxxx

# ── Google Ads ───────────────────────────────────────────────────────────
GOOGLE_ADS_DEVELOPER_TOKEN=ABcd1234efGH5678
GOOGLE_ADS_CLIENT_ID=123456789012-abc.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=GOCSPX-abcdefghij
GOOGLE_ADS_REFRESH_TOKEN=1//0g-xxxxxxxxxxxxxxxxxx

# ── WhatsApp ─────────────────────────────────────────────────────────────
WHATSAPP_API_TOKEN=EAAxxxxxxxxxxxxxxxxx
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=ads-engine-wh-secret-2024   # your secret string

# ── Admin ────────────────────────────────────────────────────────────────
ADMIN_EMAIL=vishnu@example.com
ADMIN_WHATSAPP=+919876543210
```

> **Security:** Never commit `.env` to git. It is already in `.gitignore`.

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 4. Client Config (YAML)

Location: `backend/config/clients/tickets99.yaml`

```yaml
client_id: "tickets99"
name: "Tickets99"
industry: "Event Ticketing"
currency: "INR"
timezone: "Asia/Kolkata"

platforms:
  meta:
    enabled: true
    ad_account_id: "act_1234567890"     # From Meta Ads Manager URL
    page_id: "123456789012345"           # From your Facebook Page
    pixel_id: "123456789012345"          # From Meta Events Manager

  google:
    enabled: true
    customer_id: "1234567890"            # 10-digit Google Ads customer ID

spend_limits:
  max_daily_spend: 20000                 # ₹20,000 (must be ≤ global limit in safety.yaml)
  max_single_budget_change: 5000         # ₹5,000

team_access:
  - user: "vishnu"
    role: "admin"
  - user: "siva"
    role: "manager"
  - user: "vyas"
    role: "viewer"

ai_context: |
  Tickets99 is an event ticketing platform operating in South India.
  Target cities: Chennai, Hyderabad, Bangalore.
  Audience: 18-35, interests in concerts, comedy shows, sports.
  Target CPC: ₹3.00. Target ROAS: 4x.
```

**To add a new client:** duplicate this file, change `client_id` and fill in their account IDs.

---

## 5. Safety Config (YAML)

Location: `backend/config/safety.yaml`

These are the global hard limits. No action in the system can exceed them regardless of what Claude suggests.

```yaml
spend_limits:
  max_daily_spend_per_client: 50000     # ₹50,000/day — absolute max across all clients
  max_single_budget_change: 10000       # Largest single budget edit allowed
  require_approval_above: 5000          # Any spend action >₹5K needs human approval
  max_new_campaigns_per_day: 5          # Max new campaigns created per client per day

anomaly_detection:
  auto_pause_on_cpc_spike: true
  cpc_spike_threshold_pct: 200          # Alert if CPC is 200% above 7-day average
  auto_pause_on_spend_overrun: true
  spend_overrun_threshold_pct: 120      # Alert if daily spend hits 120% of budget

approval:
  cool_down_after_reject_minutes: 60    # Wait 60 min before re-suggesting rejected actions
  auto_approve_reports: true            # Tier 1 read-only actions: no approval needed
  auto_approve_pause_on_anomaly: false  # Even anomaly pauses need human ✅

audit:
  log_everything: true
  retention_days: 365                   # Keep 1 year of audit history

restrictions:                           # Tier 3 — cannot be changed from the UI
  never_delete_without_admin: true
  never_disable_safety_rules: true
  never_remove_client_account: true
  never_override_budget_caps: true
```

---

## 6. Backend Setup

```bash
cd backend

# 1. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env
cp .env.example .env
# Fill in all values (see Section 3 above)

# 4. Run the server
uvicorn main:app --reload --port 8000
```

**Verify it's running:**
- Health check: http://localhost:8000/health → `{"status": "ok"}`
- API docs: http://localhost:8000/docs (only in `DEBUG=true` mode)

**Run tests:**
```bash
pytest tests/ -v
# Expected: 204 passed
```

---

## 7. Frontend Setup

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Create environment file
# Create frontend/.env.local with:
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# 3. Start dev server
npm run dev
```

**Dashboard:** http://localhost:3000

**Build for production:**
```bash
npm run build
npm start
```

---

## 8. Running the System

### Development (both servers)

Terminal 1 — Backend:
```bash
cd backend
venv\Scripts\activate    # or source venv/bin/activate
uvicorn main:app --reload --port 8000
```

Terminal 2 — Frontend:
```bash
cd frontend
npm run dev
```

Open http://localhost:3000 and log in.

### Production

For production you will also need:
- A public HTTPS URL for the backend (required for Meta/WhatsApp webhooks) — use a service like **ngrok** for testing or deploy to a VPS/cloud
- A PostgreSQL database (`DATABASE_URL` in `.env`)
- A process manager like **pm2** or **systemd** to keep both servers running

---

## 9. SDK & Library Reference

### Backend (Python)

| Package | Version | What it's for |
|---|---|---|
| `fastapi` | 0.115.5 | Web framework, REST API |
| `uvicorn` | 0.32.1 | ASGI server |
| `pydantic` | 2.10.3 | Data validation, schemas |
| `pydantic-settings` | 2.6.1 | Reads settings from `.env` |
| `python-dotenv` | 1.0.1 | Loads `.env` file |
| `pyyaml` | 6.0.2 | Reads YAML config files |
| `sqlalchemy` | 2.0.36 | ORM (database models) |
| `alembic` | 1.14.0 | Database migrations |
| `asyncpg` | 0.30.0 | PostgreSQL async driver |
| `aiosqlite` | 0.20.0 | SQLite driver (local dev) |
| `httpx` | 0.28.1 | Async HTTP client (Meta/WhatsApp API calls) |
| `python-jose[cryptography]` | 3.3.0 | JWT token generation + verification |
| `passlib[bcrypt]` | 1.7.4 | Password hashing |
| `python-multipart` | 0.0.19 | Form data parsing (login) |
| `websockets` | 14.1 | WebSocket support (live dashboard) |
| `anthropic` | 0.40.0 | Claude AI SDK |
| `google-ads` | 24.1.0 | Google Ads API v18 client |
| `apscheduler` | 3.10.4 | Task scheduler (daily digest) |
| `python-dateutil` | 2.9.0 | Date parsing utilities |
| `pytz` | 2024.2 | Timezone handling |
| `pytest` | 8.3.4 | Test framework |
| `pytest-asyncio` | 0.24.0 | Async test support |

Install all:
```bash
pip install -r requirements.txt
```

### Frontend (Node.js / React)

| Package | Version | What it's for |
|---|---|---|
| `next` | 15.1.3 | React framework (App Router) |
| `react` | 19.0.0 | UI library |
| `react-dom` | 19.0.0 | React DOM renderer |
| `typescript` | 5.x | Type safety |
| `tailwindcss` | 3.4.1 | Utility-first CSS |
| `lucide-react` | 0.468.0 | Icons |
| `recharts` | 2.14.1 | Charts (spend, CPC graphs) |
| `@radix-ui/react-dialog` | 1.1.4 | Modal dialogs (budget edit) |
| `@radix-ui/react-dropdown-menu` | 2.1.4 | Dropdown menus |
| `@radix-ui/react-select` | 2.1.4 | Select inputs |
| `@radix-ui/react-tabs` | 1.1.2 | Tab navigation |
| `@radix-ui/react-toast` | 1.2.4 | Toast notifications |
| `@radix-ui/react-tooltip` | 1.1.6 | Tooltips |
| `clsx` | 2.1.1 | Conditional CSS class merging |
| `tailwind-merge` | 2.6.0 | Tailwind class deduplication |
| `next-auth` | 5.0.0-beta | Authentication helpers |

Install all:
```bash
npm install
```

---

## 10. Webhook Setup (Meta / WhatsApp)

Meta requires a publicly reachable HTTPS URL to send webhook events to (WhatsApp message replies).

### For local development — use ngrok

```bash
# Install ngrok: https://ngrok.com/download
ngrok http 8000
# Note the https URL: e.g. https://abc123.ngrok.io
```

### Register the webhook in Meta Developer Console

1. Go to [developers.facebook.com](https://developers.facebook.com) → your app
2. **WhatsApp** → **Configuration** → **Webhook**
3. Set:
   - **Callback URL:** `https://your-domain.com/webhooks/whatsapp`
   - **Verify Token:** same value as `WHATSAPP_VERIFY_TOKEN` in your `.env`
4. Click **Verify and Save**
5. Subscribe to the **messages** webhook field

### How WhatsApp approval works

When an action is queued, you receive a WhatsApp message like:
```
[Ads Engine] Action Queued
Client: Tickets99 | Platform: meta
Action: pause_campaign
Description: Pause Chennai Events Campaign
Reason: CPC spike — 275% above 7-day avg
Tier: 2 (Approval required)
ID: abc12345

Reply:
  APPROVE abc12345
  REJECT abc12345 <reason>
```

Reply directly from WhatsApp to approve or reject.

---

## 11. First-Time Login

Default credentials (change after first login):

| Username | Password | Role |
|---|---|---|
| `vishnu` | `admin123` | Admin — full access, Tier 1/2/3 |
| `siva` | `manager123` | Manager — Tickets99, Tier 1/2 |
| `vyas` | `viewer123` | Viewer — read-only |

Login at: http://localhost:3000/login

> **Change passwords** in `backend/ads_engine/core/config.py` → `USERS` dict. Passwords are stored as `sha256_crypt` hashes.

---

## Quick Checklist

Before going live, make sure you have:

- [ ] `ANTHROPIC_API_KEY` — from console.anthropic.com
- [ ] `META_APP_ID` + `META_APP_SECRET` + `META_ACCESS_TOKEN` — from Meta Developer Console
- [ ] `meta.ad_account_id` in client YAML — from Ads Manager URL (`act_XXXXXXXX`)
- [ ] `meta.page_id` in client YAML — from your Facebook Page
- [ ] `meta.pixel_id` in client YAML — from Meta Events Manager
- [ ] `GOOGLE_ADS_DEVELOPER_TOKEN` — from Google Ads API Center
- [ ] `GOOGLE_ADS_CLIENT_ID` + `GOOGLE_ADS_CLIENT_SECRET` — from Google Cloud Console
- [ ] `GOOGLE_ADS_REFRESH_TOKEN` — generated via OAuth flow (one-time)
- [ ] `google.customer_id` in client YAML — 10-digit ID from Google Ads UI
- [ ] `WHATSAPP_API_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID` — from Meta Developer Console → WhatsApp
- [ ] `WHATSAPP_VERIFY_TOKEN` — your secret string (same value in `.env` and Meta console)
- [ ] `ADMIN_WHATSAPP` — your phone number (receives approval requests)
- [ ] `SECRET_KEY` — long random string (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Webhook registered in Meta console pointing to `/webhooks/whatsapp`
- [ ] Default passwords changed
