# How to Run the Project

Step-by-step guide to start the Ads Engine from scratch on any Windows machine.

---

## What You Need Installed First

| Tool | Download | How to check |
|---|---|---|
| Python 3.11+ | https://python.org/downloads | `python --version` |
| Node.js 20 LTS | https://nodejs.org | `node --version` |
| Git | https://git-scm.com | `git --version` |

---

## First Time Setup (do this once)

### Step 1 — Clone the Repository

Open Command Prompt and run:

```bash
git clone https://github.com/vishnuvardhanmandagadla/ADS-MANAGER--META-GOOGLE.git
cd "ADS-MANAGER--META-GOOGLE"
```

---

### Step 2 — Backend Setup

#### 2a. Go to the backend folder

```bash
cd backend
```

#### 2b. Create a virtual environment

```bash
python -m venv venv
```

#### 2c. Activate the virtual environment

**Windows Command Prompt:**
```bash
venv\Scripts\activate
```

**Windows PowerShell:**
```powershell
venv\Scripts\Activate.ps1
```

You will see `(venv)` appear at the start of your terminal. That means it worked.

#### 2d. Install Python packages

```bash
pip install -r requirements.txt
```

Takes 2–3 minutes on first run.

#### 2e. Create the .env file

```bash
copy .env.example .env
```

Open `.env` in Notepad and fill in these minimum values to run locally:

```env
APP_ENV=development
SECRET_KEY=         ← run: python -c "import secrets; print(secrets.token_hex(32))"
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./ads_engine.db
ANTHROPIC_API_KEY=sk-ant-...
```

Leave Meta / Google / WhatsApp keys blank for now — the UI will still load, just with empty campaign data.

> Full key setup guide → see `SETUP.md`

---

### Step 3 — Frontend Setup

Open a **new** Command Prompt window (leave the backend one open).

#### 3a. Go to the frontend folder

```bash
cd frontend
```

#### 3b. Install Node packages

```bash
npm install
```

Takes 1–2 minutes on first run.

#### 3c. Create the frontend .env file

The file `frontend/.env.local` already exists with the right content.
If it's missing, create it with:

```bash
echo VITE_API_URL=http://localhost:8000 > .env.local
echo VITE_WS_URL=ws://localhost:8000/ws >> .env.local
```

---

## Running the Project (every day)

### Easiest way — use the bat files on your Desktop

1. Double-click **`start-backend.bat`** → a black window opens, leave it running
2. Double-click **`start-frontend.bat`** → another black window opens, leave it running
3. Open your browser and go to **http://localhost:3000**

---

### Manual way — run in two terminals

**Terminal 1 — Backend:**

```bash
cd "C:\Users\vishn\Desktop\ADS-META & GOOGLE\backend"
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
[ads-engine] Starting in development mode
[ads-engine] Approval queue ready — 0 pending action(s)
[ads-engine] Audit log ready
```

**Terminal 2 — Frontend:**

```bash
cd "C:\Users\vishn\Desktop\ADS-META & GOOGLE\frontend"
npm run dev
```

You should see:
```
  VITE v6.x.x  ready in ~500ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: http://192.168.x.x:3000/
```

---

## Login

Open **http://localhost:3000** in your browser.

| Username | Password | Role | Access |
|---|---|---|---|
| `vishnu` | `admin123` | Admin | Full access — all pages, all actions, audit log |
| `siva` | `manager123` | Manager | Approve/reject actions for Tickets99 |
| `vyas` | `viewer123` | Viewer | Read-only — see reports, no actions |

---

## Pages in the Dashboard

| Page | URL | What it shows |
|---|---|---|
| Dashboard | `/dashboard` | Today's spend, clicks, CPC, pending approvals count |
| Campaigns | `/campaigns` | All campaigns — pause, activate, edit budget |
| Approvals | `/approvals` | Pending actions waiting for your ✅ |
| AI Chat | `/ai-chat` | Talk to Claude — it suggests optimisations |
| Settings | `/settings` | Safety limits, team, audit log (admin only) |

---

## Verify Everything is Working

1. Backend health check → open **http://localhost:8000/health**
   - Should return: `{"status":"ok","env":"development"}`

2. API docs → open **http://localhost:8000/docs**
   - Should show Swagger UI with all endpoints listed

3. Frontend → open **http://localhost:3000**
   - Should show the login page

---

## Troubleshooting

### Backend doesn't start — "ModuleNotFoundError"
You forgot to activate the virtual environment.
Run `venv\Scripts\activate` before starting uvicorn.

### Frontend doesn't start — "vite not found" or "Cannot find module"
You skipped `npm install`. Run it inside the `frontend` folder first, then `npm run dev`.

### Login page loads but login fails
The backend is not running. Start it first and confirm http://localhost:8000/health returns OK.

### Campaigns page shows no data
The backend is running but Meta/Google API keys are not filled in yet.
The UI works — it just shows empty data until real ad account IDs are connected.
See `SETUP.md` to fill in the keys.

### Port 3000 or 8000 already in use
Something else is using that port. Either close it or use a different port:

```bash
# Backend on a different port
uvicorn main:app --reload --port 8001

# Frontend on a different port
npm run dev -- --port 3001
```

If you change ports, also update `frontend/.env.local`:
```
VITE_API_URL=http://localhost:8001
VITE_WS_URL=ws://localhost:8001/ws
```

### PowerShell blocks venv activation — "cannot be loaded because running scripts is disabled"
Run this once in PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try activating again.

---

## What Runs Where

| Service | URL | Technology |
|---|---|---|
| Backend API | http://localhost:8000 | Python + FastAPI |
| API Docs (Swagger) | http://localhost:8000/docs | Auto-generated (debug mode only) |
| Frontend | http://localhost:3000 | React 18 + Vite |

---

## Frontend Tech (for reference)

The frontend is **plain React** — no Next.js.

| What | How |
|---|---|
| Framework | React 18 + Vite 6 |
| Routing | React Router DOM v6 |
| Styling | Tailwind CSS |
| Icons | Lucide React |
| Charts | Recharts |
| Entry point | `src/main.tsx` |
| Router setup | `src/App.tsx` |
| Pages | `src/pages/` |
| Shared components | `src/components/` |
| API calls | `src/lib/api.ts` |
| Auth state | `src/lib/auth.tsx` |
| WebSocket | `src/lib/ws.ts` |
| Env vars | `frontend/.env.local` (prefix: `VITE_`) |
