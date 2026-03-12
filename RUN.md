# How to Run the Project

Step-by-step guide to start the Ads Engine from scratch on any Windows machine.

---

## Prerequisites

Install these before anything else:

| Tool | Download | Check if installed |
|---|---|---|
| Python 3.11+ | https://python.org/downloads | `python --version` |
| Node.js 20 LTS | https://nodejs.org | `node --version` |
| Git | https://git-scm.com | `git --version` |

---

## Step 1 — Clone the Repository

Open Command Prompt or PowerShell and run:

```bash
git clone https://github.com/vishnuvardhanmandagadla/ADS-MANAGER--META-GOOGLE.git
cd "ADS-MANAGER--META-GOOGLE"
```

---

## Step 2 — Backend Setup

### 2a. Create a virtual environment

```bash
cd backend
python -m venv venv
```

### 2b. Activate the virtual environment

```bash
# Windows Command Prompt
venv\Scripts\activate

# Windows PowerShell
venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

You will see `(venv)` appear at the start of your terminal line. That means it worked.

### 2c. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, Anthropic SDK, Google Ads SDK, and all other backend libraries.
Takes about 2–3 minutes on first run.

### 2d. Create the environment file

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Then open `.env` in any text editor and fill in:

```env
APP_ENV=development
SECRET_KEY=          # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
DEBUG=true

# Use SQLite for local dev (no database setup needed)
DATABASE_URL=sqlite+aiosqlite:///./ads_engine.db

# Your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-...

# Leave Meta / Google / WhatsApp blank for now if you just want to see the UI
META_APP_ID=
META_APP_SECRET=
META_ACCESS_TOKEN=
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
WHATSAPP_API_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_VERIFY_TOKEN=
ADMIN_WHATSAPP=+91XXXXXXXXXX
```

> Refer to `SETUP.md` for how to get each API key.

### 2e. Start the backend server

```bash
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
[ads-engine] Starting in development mode
[ads-engine] Approval queue ready — 0 pending action(s)
[ads-engine] Audit log ready
```

Verify it works — open your browser and go to:
```
http://localhost:8000/health
```
You should see: `{"status":"ok","env":"development"}`

**Keep this terminal window open.**

---

## Step 3 — Frontend Setup

Open a **new** terminal window (keep the backend one running).

### 3a. Go to the frontend folder

```bash
cd frontend
```

### 3b. Install Node.js dependencies

```bash
npm install
```

Takes about 1–2 minutes on first run.

### 3c. Create the frontend environment file

Create a file called `.env.local` inside the `frontend` folder with this content:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Windows Command Prompt:**
```bash
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
```

**PowerShell:**
```powershell
"NEXT_PUBLIC_API_URL=http://localhost:8000" | Out-File .env.local -Encoding utf8
```

### 3d. Start the frontend server

```bash
npx next dev --port 3000
```

You should see:
```
▲ Next.js 15.1.3
   - Local:   http://localhost:3000
   ✓ Ready in ~2s
```

**Keep this terminal window open.**

---

## Step 4 — Open the Dashboard

Open your browser and go to:

```
http://localhost:3000
```

You will see the login page.

---

## Step 5 — Login

Use one of these default accounts:

| Username | Password | Role | What they can do |
|---|---|---|---|
| `vishnu` | `admin123` | Admin | Everything — all clients, all tiers, audit log |
| `siva` | `manager123` | Manager | Approve/reject actions for Tickets99 |
| `vyas` | `viewer123` | Viewer | Read-only — see reports, no actions |

---

## Step 6 — Explore the UI

| Page | URL | What it shows |
|---|---|---|
| Dashboard | `/dashboard` | Spend, clicks, CPC, pending approvals count |
| Campaigns | `/campaigns` | All campaigns with budget, spend, CPC, CTR, ROAS |
| Approvals | `/approvals` | Pending actions waiting for your ✅ |
| AI Chat | `/ai-chat` | Talk to Claude — it suggests optimisations |
| Settings | `/settings` | Safety limits, team, audit log (admin only) |

---

## Everyday Startup (after first setup)

You only need to do Steps 1–3 once. After that, starting the project every day is just:

### Option A — Use the bat files on Desktop (Windows only)

1. Double-click **`start-backend.bat`**
2. Double-click **`start-frontend.bat`**
3. Open **http://localhost:3000**

### Option B — Run in terminals manually

**Terminal 1 — Backend:**
```bash
cd "ADS-META & GOOGLE/backend"
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd "ADS-META & GOOGLE/frontend"
npx next dev --port 3000
```

---

## Troubleshooting

### "Module not found" or import errors (backend)
You forgot to activate the venv. Run `venv\Scripts\activate` first.

### "Cannot find module" (frontend)
You skipped `npm install`. Run it inside the `frontend` folder.

### Login fails
Make sure the backend is running on port 8000. Check `http://localhost:8000/health`.

### Page loads but data is empty
API keys for Meta/Google are not filled in yet. The UI works — it just shows empty data until you connect real ad accounts. See `SETUP.md` for how to get the keys.

### Port already in use
Something else is using port 8000 or 3000. Either stop that process or change the port:
```bash
# Backend on port 8001
uvicorn main:app --reload --port 8001

# Frontend on port 3001
npx next dev --port 3001
```
If you change ports, update `NEXT_PUBLIC_API_URL` in `frontend/.env.local` to match.

### Backend crashes on startup
Check your `.env` file — make sure `DATABASE_URL` is set to the SQLite line, not the PostgreSQL line (which requires a running database).

---

## Summary — What runs where

| Service | URL | Technology |
|---|---|---|
| Backend API | http://localhost:8000 | Python / FastAPI |
| API Docs | http://localhost:8000/docs | Auto-generated Swagger (debug mode only) |
| Frontend | http://localhost:3000 | Next.js / React |
