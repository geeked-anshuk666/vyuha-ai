<div align="center">
  <img src="https://img.shields.io/badge/Vyuha%20AI-Z.ai%20Hackathon-blue?style=for-the-badge&logo=openai" alt="Vyuha AI Logo">
  <h1>Vyuha AI: Autonomous Multi-Cloud Recovery Orchestrator</h1>
  <p>An intelligent, agent-driven control plane that dynamically routes traffic away from failing data centers using GLM 5.1 long-horizon reasoning.</p>

  [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/geeked-anshuk666/vyuha-ai)
  [![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fgeeked-anshuk666%2Fvyuha-ai&root-directory=dashboard)
</div>

---

## 🌩️ Zero-Cost ($0) Production Architecture
Vyuha AI is architected for zero-cost, high-availability deployments during hackathons and demos using a **Split-Provider Monolith** strategy:

1.  **Backend (Render Free Tier)**: The Orchestrator, Proxy, and Nodes are consolidated into a single monolithic Docker container via `prod_consolidator.py`. This bypasses service limits while maintaining internal microservice logic over `localhost`.
2.  **Frontend (Vercel Free Tier)**: The Next.js Mission Control dashboard is deployed as a standalone high-performance edge application, communicating with the Render backend via secure cross-domain API calls.

---

## 🛡️ Key Features
- **Dynamic Reverse Proxy**: Seamless traffic rerouting without application restarts.
- **Shadow Validation Engine**: Ensures zero AI-induced outages by sandboxing and simulating routing topology changes before they are applied.
- **Glass Break Approval**: A sleek Next.js Mission Control dashboard keeps humans in the loop for critical failover events.
- **Evolutionary Memory**: Powered by **GLM 5.1**, the system learns from every incident and human rejection—building long-term wisdom.

---

## 🚀 Deployment Guide

### 1. Backend (Render)
1. Push this repo to GitHub.
2. Create a new **Web Service** on Render.
3. Render will automatically detect the `render.yaml` Blueprint.
4. Set your `GLM_API_KEY` in the Environment Variables.
5. Note your backend URL (e.g., `https://vyuha-ai-backend.onrender.com`).

### 2. Frontend (Vercel)
1. Import the repository to Vercel.
2. Set the **Root Directory** to `dashboard`.
3. Add the following Environment Variable:
   - `NEXT_PUBLIC_ORCHESTRATOR_URL`: (Your Render Backend URL)

---

## 🧪 Local Development (Docker Compose)
For local testing with full service isolation:
```bash
docker compose up -d --build
```
| Service | URL |
|---------|-----|
| Mission Control | `http://localhost:3000` |
| User Proxy | `http://localhost:8000` |
| Control Plane API | `http://localhost:9000` |

---
*Built for the Z.ai Hackathon — Demonstrating safety, speed, and intelligence in production infrastructure.*
