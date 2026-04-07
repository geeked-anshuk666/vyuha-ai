<div align="center">
  <img src="https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/cpu.svg" width="80" height="80" alt="Vyuha AI Logo">
  <h1>⚡ Vyuha AI: Mission Control</h1>
  <h3>Autonomous Multi-Cloud Recovery Orchestrator</h3>
  <p><b>Triple-Cloud Failover Intelligence — AWS • Azure • GCP</b></p>

  <p>
    An intelligent, agent-driven control plane that detects cloud failures in real-time,
    reasons through them using <b>GLM-5.1</b>, and dynamically reroutes traffic
    before your on-call engineer even wakes up.
  </p>

  <div>
    <img src="https://img.shields.io/badge/AI-GLM--5.1-emerald?style=for-the-badge" alt="GLM 5.1">
    <img src="https://img.shields.io/badge/Infrastructure-Triple--Cloud-blue?style=for-the-badge" alt="Triple-Cloud">
    <img src="https://img.shields.io/badge/UI-Next.js%2014-white?style=for-the-badge" alt="Next.js">
    <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge" alt="FastAPI">
    <img src="https://img.shields.io/badge/Memory-SQLite-003B57?style=for-the-badge" alt="SQLite">
  </div>

  <br/>

  <a href="https://vyuha-ai.vercel.app"><img src="https://img.shields.io/badge/🚀 Live Dashboard-vyuha--ai.vercel.app-black?style=for-the-badge" alt="Live Demo"></a>
  <a href="https://vyuha-ai-backend.onrender.com/docs"><img src="https://img.shields.io/badge/📡 API Docs-Render-46E3B7?style=for-the-badge" alt="API Docs"></a>

</div>

---

## 🌌 What Is Vyuha AI?

Most monitoring tools tell you **what broke**. Vyuha AI tells you **what to do about it** — and then does it.

Vyuha is a **Triple-Cloud Mission Control** that monitors AWS, Azure, and GCP nodes simultaneously. The moment a node fails — whether it's a hard crash, intermittent packet loss, or a latency spike — the **Z.ai Companion** (powered by GLM-5.1) analyzes the situation, generates a failover plan, and presents it to a human operator for approval.

After approval, the dynamic reverse proxy reroutes traffic instantly. Zero manual SSH. Zero runbook hunting. Zero downtime.

### 🧬 Evolutionary Memory
Every incident makes Vyuha smarter. After every human decision (approved or rejected), the agent reflects on the outcome and stores a **lesson learned**. The next time a similar failure occurs, the AI reads its own history before proposing a fix. It is a self-improving SRE.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   GLOBAL USERS (Traffic)                 │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
             ┌─────────────────────────┐
             │  Vyuha Dynamic Proxy    │  ← Intelligent traffic router
             │     (Port 8000)         │
             └──────┬────────┬────────┘
                    │        │        │
           ┌────────▼┐  ┌────▼──┐  ┌──▼────┐
           │  AWS    │  │ Azure │  │  GCP  │
           │ :8001   │  │ :8002 │  │ :8003 │
           └─────────┘  └───────┘  └───────┘
                    ▲        ▲        ▲
                    └────────┴────────┘
                             │ Monitor (5s interval)
             ┌───────────────▼─────────────────┐
             │   Z.ai Orchestrator / Control    │
             │   Plane (GLM-5.1 + SQLite)       │
             │         (Port 9000)              │
             └─────────────────────────────────┘
                             │
             ┌───────────────▼─────────────────┐
             │  Load Tester + Metrics Engine    │
             │  (Parallel probing all 3 nodes)  │
             │         (Port 8005)              │
             └─────────────────────────────────┘
```

---

## ⚡ Key Features

| Feature | Description |
|---|---|
| 🔴 **Chaos Lab** | Inject Hard Kill, Flaky (25% packet drop), or 1.5s Latency into any node live |
| 🤖 **GLM-5.1 Triage** | AI analyzes failure severity, builds a failover formation, explains its reasoning |
| 🧑‍✈️ **Human-in-the-Loop** | No action is taken without operator approval — agentic AI with a human conscience |
| 📈 **Chaos-Reactive Graph** | Throughput graph is wired to all 3 nodes — FAIL RATE % badge appears on chaos injection |
| 🧠 **Evolutionary Memory** | Every approved/rejected proposal becomes a lesson stored in the AI's long-term memory |
| 🔄 **Auto-Heal + Auto-Close** | Hit HEAL → node recovers → incident auto-closes. No manual cleanup |
| 🛡️ **Shadow Validator** | AI proposals are sandboxed and validated for idempotency before human sees them |
| ⚡ **Circuit Breaker** | If the AI fails 3 times consecutively, it locks itself out. Requires manual reset |

---

## 🎬 Demo Video

> **Watch the full demo:** *[Add your YouTube link here]*

---

## 🚀 Try It Live — Step-by-Step

> ⚠️ **IMPORTANT: Read this before opening the dashboard.**
>
> The backend runs on Render's **free tier**, which **spins down after inactivity**.
> You MUST wake the backend first, or the dashboard will show no data.

### Step 1 — Wake the Backend (Do This First!)

1. Open the backend in a new tab: **https://vyuha-ai-backend.onrender.com/docs**
2. Wait for the Swagger UI to fully load (this can take **30–60 seconds** on a cold start)
3. You'll see a list of API endpoints — that means the backend is alive ✅

### Step 2 — Open the Dashboard

1. Once the backend is confirmed awake, open: **https://vyuha-ai.vercel.app**
2. You should see the **Mission Control** dashboard load with all 3 nodes **GREEN** and the throughput graph streaming live data
3. Uptime counter (top right) should be ticking ✅

### Step 3 — Run the Chaos Demo

Follow this sequence for the best demo experience:

```
1. Observe: All 3 nodes ONLINE (green cards, latency visible, graph active)

2. HARD KILL GCP:
   → Click "HARD KILL (DEAD)" under GCP in Chaos Experiments
   → GCP card turns RED with "FATAL ERROR"
   → Graph shows red spike (FAIL RATE % badge appears)
   → Z.ai Companion Insight activates with AI analysis (~5 seconds)

3. APPROVE the proposal:
   → Read the AI's step-by-step reasoning
   → Click APPROVE
   → Incident moves to "Applied / Monitoring Recovery" state
   → Traffic is rerouted away from GCP

4. HEAL GCP:
   → Click "HEAL (RECOVER)" under GCP
   → Node returns GREEN
   → Incident auto-closes
   → Learning is recorded in Evolutionary Memory Log

5. Repeat with FLAKY (AWS) or 1.5s LATENCY (Azure) for different failure modes
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, Recharts, Framer Motion, Lucide Icons |
| **Backend** | FastAPI (Python), Uvicorn |
| **AI Agent** | GLM-5.1 via ZhipuAI API (long-horizon reasoning) |
| **Database** | SQLite + aiosqlite (incidents, proposals, learnings) |
| **Proxy** | Custom FastAPI Dynamic Reverse Proxy |
| **Load Tester** | Custom parallel node prober (10 RPS per node) |
| **Deployment** | Render (backend monolith) + Vercel (dashboard) |

---

## 📡 API Reference

Full interactive docs: **https://vyuha-ai-backend.onrender.com/docs**

| Endpoint | Method | Description |
|---|---|---|
| `/monitor/status` | GET | Full system state — nodes, incidents, proposals |
| `/chaos/{node}/fail` | POST | Inject failure state into a node |
| `/chaos/{node}/recover` | POST | Heal a node |
| `/proposals` | GET | List all pending AI proposals |
| `/approve` | POST | Approve an agent proposal |
| `/reject` | POST | Reject an agent proposal |
| `/learnings` | GET | Retrieve evolutionary memory log |
| `/trigger-triage` | POST | Manually force AI triage (Force Triage button) |
| `/monitor/metrics` | GET | Live traffic metrics from load generator |

---

## 🧪 Local Development

```bash
# 1. Clone
git clone https://github.com/geeked-anshuk666/vyuha-ai.git
cd vyuha-ai

# 2. Install Python deps
pip install -r requirements.txt

# 3. Set your GLM API key
export GLM_API_KEY=your_key_here

# 4. Start the full backend stack (all services in one process)
python scripts/prod_consolidator.py

# 5. Start the dashboard (separate terminal)
cd dashboard
npm install
npm run dev
```

> The consolidator starts: AWS node (8001) → Azure (8002) → GCP (8003) → Proxy (8000) → Load Tester (8005) → Orchestrator (9000)

---

## 🌐 Deployment

### Backend → Render

1. Push repo to GitHub
2. Create a **Render Web Service**
3. Set **Start Command**: `python scripts/prod_consolidator.py`
4. Add environment variables:
   - `GLM_API_KEY` = your ZhipuAI key
   - `RENDER` = `true`
   - `VYUHA_DB_PATH` = `/app/vyuha.db`
5. Deploy ✅

### Dashboard → Vercel

1. Import the `dashboard/` folder as a Vercel project
2. Set environment variable:
   - `NEXT_PUBLIC_ORCHESTRATOR_URL` = `https://vyuha-ai-backend.onrender.com`
3. Deploy ✅

---

## 🎯 Incident Lifecycle

```
Node Fails
    ↓
DETECTED  →  TRIAGING  →  PROPOSED  →  [Human Approves]  →  APPLIED
                                                                 ↓
                                                          Node Heals (HEAL button)
                                                                 ↓
                                                           REFLECTED (auto-closed)
                                                                 ↓
                                                        Learning Stored in Memory
```

---

*Built for the Z.ai Hackathon — Engineering Resilient Infrastructure with Long-Horizon Intelligence.*

*⭐ Star this repo if you think autonomous infrastructure is the future.*
