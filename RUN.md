# How to Run the Project

Complete step-by-step guide to get the Ads Engine running on Windows.

---

## IMPORTANT — Folder Name Issue

The project folder is named **`ADS-META & GOOGLE`**.
The `&` character causes problems in Windows terminals when running npm scripts.

**Fix — rename the folder before starting:**

1. Close all open terminals
2. Right-click the folder on Desktop
3. Rename it to **`ADS-ENGINE`** (no spaces, no special characters)
4. Use `C:\Users\vishn\Desktop\ADS-ENGINE` as your path from now on

> If you don't rename it, `npm run dev` will fail with a "Cannot find module" error.
> The package.json has a workaround built in — but renaming is cleaner and avoids all future issues.

---

## Prerequisites

Install these before anything else:

| Tool | Download | Verify with |
|---|---|---|
| Python 3.11+ | https://python.org/downloads | `python --version` |
| Node.js 20 LTS | https://nodejs.org | `node --version` |
| Git | https://git-scm.com | `git --version` |

---

## First Time Setup (do this once)

### Step 1 — Clone the Repository

```bash
git clone https://github.com/vishnuvardhanmandagadla/ADS-MANAGER--META-GOOGLE.git
```

Then rename the cloned folder from `ADS-MANAGER--META-GOOGLE` to `ADS-ENGINE` (or any name without special characters).

---

### Step 2 — Backend Setup

Open Command Prompt and run:

```bash
cd "C:\Users\vishn\Desktop\ADS-ENGINE\backend"
```

#### 2a. Create virtual environment

```bash
python -m venv venv
```

#### 2b. Activate virtual environment

```bash
venv\Scripts\activate
```

You will see `(venv)` at the start of the line. That means it worked.

#### 2c. Install Python packages

```bash
pip install -r requirements.txt
```

Takes 2–3 minutes first time.

#### 2d. Create the .env file

```bash
copy .env.example .env
```

Open `.env` in Notepad and set these minimum values:

```env
APP_ENV=development
SECRET_KEY=your-secret-key-here
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./ads_engine.db
ANTHROPIC_API_KEY=sk-ant-...
```

To generate a SECRET_KEY, run:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as the SECRET_KEY value.

> Leave Meta / Google / WhatsApp keys blank for now — the dashboard will still load, just with empty campaign data. See `SETUP.md` for how to get those keys.

---

### Step 3 — Frontend Setup

Open a **new** Command Prompt window (keep the backend one open).

```bash
cd "C:\Users\vishn\Desktop\ADS-ENGINE\frontend"
```

#### 3a. Install Node packages

```bash
npm install
```

Takes 1–2 minutes first time.

#### 3b. Check the .env.local file

The file `frontend/.env.local` should already exist with:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

If it's missing, create it manually in Notepad with that content.

---

## Running Every Day

After first-time setup, starting the project every day is just two commands in two terminals.

---

### Terminal 1 — Backend

```bash
cd "C:\Users\vishn\Desktop\ADS-ENGINE\backend"
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
[ads-engine] Starting in development mode
[ads-engine] Approval queue ready — 0 pending action(s)
[ads-engine] Audit log ready
```

**Keep this window open.**

---

### Terminal 2 — Frontend

```bash
cd "C:\Users\vishn\Desktop\ADS-ENGINE\frontend"
npm run dev
```

Expected output:
```
  VITE v6.x.x  ready in ~500ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: http://192.168.x.x:3000/
```

**Keep this window open.**

---

### Or — Use the Bat Files on Desktop

1. Double-click **`start-backend.bat`** → leave that window open
2. Double-click **`start-frontend.bat`** → leave that window open
3. Open **http://localhost:3000** in browser

> Update the paths inside the bat files if you renamed the folder.

---

## Login

Open **http://localhost:3000** in your browser.

| Username | Password | Role | What they can do |
|---|---|---|---|
| `vishnu` | `admin123` | Admin | Full access — all pages, all actions, audit log |
| `siva` | `manager123` | Manager | Approve/reject actions for Tickets99 |
| `vyas` | `viewer123` | Viewer | Read-only — reports only, no actions |

---

## Pages

| Page | URL | What it shows |
|---|---|---|
| Dashboard | `/dashboard` | Spend, clicks, CPC, pending approvals |
| Campaigns | `/campaigns` | All campaigns — pause, activate, edit budget |
| Approvals | `/approvals` | Pending actions waiting for ✅ |
| AI Chat | `/ai-chat` | Talk to Claude — it suggests optimisations |
| Settings | `/settings` | Safety limits, team access, audit log (admin only) |

---

## Verify It's Working

| Check | How |
|---|---|
| Backend running | Open http://localhost:8000/health → should return `{"status":"ok"}` |
| API docs | Open http://localhost:8000/docs → Swagger UI |
| Frontend running | Open http://localhost:3000 → login page |

---

## Troubleshooting

### `npm run dev` fails — "Cannot find module vite"
The `&` in the folder name is breaking the path.
**Fix:** Rename the folder to `ADS-ENGINE` (remove the `&`).

### Backend — "ModuleNotFoundError"
Virtual environment is not activated.
Run `venv\Scripts\activate` before uvicorn.

### Login fails after backend starts
Backend may have crashed on startup.
Check the backend terminal for errors.
Most common cause: `DATABASE_URL` in `.env` is pointing to PostgreSQL instead of SQLite.
Make sure this line is uncommented:
```
DATABASE_URL=sqlite+aiosqlite:///./ads_engine.db
```

### Campaigns page shows no data
Normal — Meta/Google API keys are not filled in yet.
The UI loads fine, just no real campaign data until you connect ad accounts.
See `SETUP.md`.

### Port already in use

```bash
# Backend on a different port
uvicorn main:app --reload --port 8001

# Frontend on a different port
npm run dev -- --port 3001
```

If you change the backend port, also update `frontend/.env.local`:
```
VITE_API_URL=http://localhost:8001
VITE_WS_URL=ws://localhost:8001/ws
```

### PowerShell blocks venv — "running scripts is disabled"
Run this once in PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## What Runs Where

| Service | URL | Tech |
|---|---|---|
| Backend API | http://localhost:8000 | Python + FastAPI |
| API Docs | http://localhost:8000/docs | Swagger (debug mode only) |
| Frontend | http://localhost:3000 | React 18 + Vite 6 |

---

## Frontend Structure (for reference)

```
frontend/
├── src/
│   ├── main.tsx              ← entry point
│   ├── App.tsx               ← router (all 6 routes defined here)
│   ├── index.css             ← Tailwind base styles
│   ├── lib/
│   │   ├── api.ts            ← all API calls to backend
│   │   ├── auth.tsx          ← login state (React Context)
│   │   └── ws.ts             ← WebSocket auto-reconnect hook
│   ├── components/
│   │   ├── Sidebar.tsx       ← left nav with pending badge
│   │   └── DashboardLayout.tsx  ← auth guard + sidebar wrapper
│   └── pages/
│       ├── LoginPage.tsx
│       ├── DashboardPage.tsx
│       ├── CampaignsPage.tsx
│       ├── ApprovalsPage.tsx
│       ├── AiChatPage.tsx
│       ├── SettingsPage.tsx
│       ├── dashboard/        ← MetricsBar, SpendChart, ClientsTable
│       ├── campaigns/        ← CampaignCard, BudgetModal
│       └── approvals/        ← ActionCard
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── .env.local                ← VITE_API_URL, VITE_WS_URL
└── package.json
```
