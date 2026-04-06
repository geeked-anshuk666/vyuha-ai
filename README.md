<div align="center">
  <img src="https://img.shields.io/badge/Vyuha%20AI-Z.ai%20Hackathon-blue?style=for-the-badge&logo=openai" alt="Vyuha AI Logo">
  <h1>Vyuha AI: Autonomous Multi-Cloud Recovery Orchestrator</h1>
  <p>An intelligent, agent-driven control plane that dynamically routes traffic away from failing data centers using GLM 5.1 long-horizon reasoning and evolutionary memory.</p>
</div>

---

## 🌩️ The Problem
During massive-scale data center failures (e.g., fiber cuts, regional outages), manual intervention is too slow. Traditional load balancers fail blindly without understanding the *context* or the business impact. 

## 🛡️ The Solution: Vyuha AI
Vyuha AI introduces a **Control Plane Orchestrator** that bridges the gap between raw infrastructure and human operator intent. 

- **Dynamic Reverse Proxy**: Seamless traffic rerouting without application restarts.
- **Shadow Validation Engine**: Ensures zero AI-induced outages by sandboxing and simulating routing topology changes before they are applied.
- **Glass Break Approval**: A sleek Next.js Mission Control dashboard keeps humans in the loop for critical failover events.
- **Evolutionary Memory**: The GLM 5.1 agent learns from every incident and human rejection—building long-term wisdom to prevent identical mistakes in the future.

---

## 🛠️ Architecture

### 1. Data Plane (Infrastructure)
* **Node-A & Node-B**: Simulated cloud zones (e.g., AWS vs Azure).
* **Vyuha Proxy**: A lightning-fast, dynamically configurable reverse proxy that isolates users from downstream failures.

### 2. Control Plane (The Brain)
* **Orchestrator**: Polls Node health async. When a failure is detected, it summons the GLM Agent.
* **Triage Pipeline**: Parses node failures and assesses severity.
* **Agent Proposal**: GLM evaluates the outage, cross-references its **Learning DB**, and securely leverages walled-garden tools to build a failover routing table.

### 3. Mission Control (Human Loop)
* Sleek Next.js frontend built with Tailwind and Framer Motion.
* Provides a real-time topology view and hosts the **Glass Break Modal** where humans can `Approve` or `Reject` the GLM's proposal with feedback.

---

## 🚀 Quick Start (Local Docker Deploy)

Boot up the entire Vyuha AI cluster with a single command:

```bash
docker compose up -d --build
```

### Exposing Services
| Service | URL | Function |
|---------|-----|----------|
| **Mission Control Dashboard** | `http://localhost:3000` | Human-in-the-loop UI |
| **User Proxy** | `http://localhost:8000` | The entrypoint for end-user traffic |
| **Control Plane API** | `http://localhost:9000` | Orchestrator and agent health checks |

---

## 🧪 Simulating an Outage (End-to-End)

1. **Open the Dashboard**: Navigate to `http://localhost:3000`. You will see all nodes marked as `HEALTHY`.
2. **Break a Node**: Run this command to kill `Node-A`:
   ```bash
   docker stop vyuha-node-a
   ```
3. **Observe the AI**: 
   - The Orchestrator detects the failure in < 5 seconds.
   - The GLM Agent is summoned and formulates a Proposal to shift 100% of traffic to `Node-B`.
   - A `Companion Insight` alert appears on the dashboard.
4. **Approve & Reflect**: 
   - Click `Approve` via the UI.
   - Vyuha runs **Shadow Validation**.
   - The new proxy rule is instantly applied without downtime.
   - The Agent reflects on the success and updates the **Evolutionary Memory Log** available on your dashboard screen!

---
*Built for the Z.ai Hackathon — Demonstrating safety, speed, and intelligence in production infrastructure.*
