"""
Vyuha AI — Control Plane Orchestrator
The Brain of the system: async health monitoring, agent triage, human approval loop.
"""

import asyncio
import time
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from control_plane.models import (
    NodeHealthSnapshot, NodeState, IncidentStatus,
    MonitorStatusResponse, ApprovalRequest, RejectionRequest,
    IncidentDetailResponse, AgentProposal, Learning,
)
from control_plane.tools import tool_check_all_nodes, tool_apply_formation_change
from control_plane.agent import triage_incident, reflect_on_outcome, get_learnings_context, chat_with_agent
from control_plane import db
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ORCHESTRATOR] %(message)s")
logger = logging.getLogger("vyuha-orchestrator")

HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "5"))
MAX_AGENT_FAILURES = int(os.getenv("MAX_AGENT_FAILURES", "3"))


class OrchestratorRuntime:
    def __init__(self) -> None:
        self.start_time: float = time.time()
        self.monitoring_active: bool = False
        self.node_states: list[NodeHealthSnapshot] = []
        self.circuit_breaker_active: bool = False
        self.consecutive_agent_failures: int = 0
        self._monitor_task: asyncio.Task | None = None
        self._known_dead_nodes: set[str] = set()

    @property
    def uptime_seconds(self) -> float:
        return round(time.time() - self.start_time, 2)


runtime = OrchestratorRuntime()


async def health_monitor_loop() -> None:
    """
    Core monitoring loop. Polls all nodes every HEALTH_CHECK_INTERVAL seconds.
    When a node failure is detected, triggers the agent triage pipeline.
    """
    runtime.monitoring_active = True
    logger.info(f"Health monitor started (interval={HEALTH_CHECK_INTERVAL}s)")

    while True:
        try:
            node_states = await tool_check_all_nodes()
            runtime.node_states = node_states

            active_incident_nodes = {i.node_name for i in await db.get_active_incidents()}

            # Only trigger triage if the node is UNHEALTHY AND not already in an active incident
            unhealthy_nodes = {n.node_name for n in node_states if n.state != NodeState.HEALTHY}
            new_unhealthy = (unhealthy_nodes - runtime._known_dead_nodes) - active_incident_nodes

            if new_unhealthy and not runtime.circuit_breaker_active:
                logger.warning(f"UNHEALTHY state detected (untracked): {new_unhealthy}")
                try:
                    learnings_ctx = await get_learnings_context()
                    proposal = await triage_incident(node_states, learnings_ctx)
                    if proposal:
                        logger.info(f"Agent proposal #{proposal.id} created — awaiting human approval")
                        runtime.consecutive_agent_failures = 0
                except Exception as e:
                    runtime.consecutive_agent_failures += 1
                    logger.error(f"Agent triage failed ({runtime.consecutive_agent_failures}/{MAX_AGENT_FAILURES}): {e}")

                    if runtime.consecutive_agent_failures >= MAX_AGENT_FAILURES:
                        runtime.circuit_breaker_active = True
                        logger.critical("CIRCUIT BREAKER ACTIVATED — Manual Override required")

            recovered = runtime._known_dead_nodes - unhealthy_nodes
            if recovered:
                logger.info(f"Nodes recovered: {recovered}")

            runtime._known_dead_nodes = unhealthy_nodes

        except Exception as e:
            logger.error(f"Monitor loop error: {e}")

        await asyncio.sleep(HEALTH_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    task = asyncio.create_task(health_monitor_loop())
    runtime._monitor_task = task
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Vyuha AI — Orchestrator (Control Plane)",
    description="Autonomous multi-cloud recovery companion with evolutionary memory",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rate Limiting (Simple In-Memory) ---
from collections import defaultdict
import time as time_mod

REQUEST_RATE_LIMIT = 100  # requests
RATE_LIMIT_WINDOW = 60.0  # seconds

client_requests = defaultdict(list)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time_mod.time()
    
    # Prune old requests
    client_requests[client_ip] = [t for t in client_requests[client_ip] if now - t < RATE_LIMIT_WINDOW]
    
    if len(client_requests[client_ip]) >= REQUEST_RATE_LIMIT:
        return Response("Rate limit exceeded", status_code=429)
        
    client_requests[client_ip].append(now)
    response = await call_next(request)
    return response


# --- Status & Monitoring ---

@app.get("/health")
async def health_check():
    return {"status": "healthy", "component": "orchestrator"}

@app.get("/monitor/status", response_model=MonitorStatusResponse)
async def get_monitor_status():
    """Dashboard endpoint: returns full system state at a glance."""
    active_incidents = await db.get_active_incidents()
    pending_proposals = await db.get_pending_proposals()

    return MonitorStatusResponse(
        orchestrator_uptime=runtime.uptime_seconds,
        monitoring_active=runtime.monitoring_active,
        node_states=runtime.node_states,
        active_incidents=active_incidents,
        pending_proposals=pending_proposals,
        circuit_breaker_active=runtime.circuit_breaker_active,
        consecutive_agent_failures=runtime.consecutive_agent_failures,
    )


@app.get("/monitor/nodes")
async def get_node_states():
    """Get the latest node health snapshots."""
    return {"nodes": [n.model_dump() for n in runtime.node_states]}


# --- Incident Management ---

@app.get("/incidents")
async def list_incidents():
    incidents = await db.get_active_incidents()
    return {"incidents": [i.model_dump() for i in incidents]}


@app.get("/incidents/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident_detail(incident_id: int):
    incident = await db.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    proposals = await db.get_proposals_for_incident(incident_id)
    learnings = await db.get_learnings_for_incident(incident_id)

    return IncidentDetailResponse(
        incident=incident,
        proposals=proposals,
        learnings=learnings,
    )


# --- Human Approval Loop ---

@app.get("/proposals")
async def list_proposals():
    proposals = await db.get_pending_proposals()
    return {"proposals": [p.model_dump() for p in proposals]}


@app.post("/approve")
async def approve_proposal(request: ApprovalRequest):
    """
    Human approves the agent's proposal.
    Triggers: shadow validation -> config application → reflection loop → memory update.
    """
    proposal = await db.get_proposal(request.proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    incident = await db.get_incident(proposal.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Associated incident not found")

    # 1. Shadow Validation
    from control_plane.validator import shadow_validator
    validation_result = await shadow_validator.validate(proposal)
    if not validation_result.passed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Shadow validation failed",
                "checks": validation_result.to_dict()
            }
        )
        
    # Idempotency check: abort if the shadow validation detected a no-op
    for check in validation_result.checks:
        if check.get("name") == "idempotency" and "matches current" in check.get("detail", ""):
            return {
                "status": "ignored",
                "reason": "Formation is already applied (idempotent no-op)",
                "proposal_id": proposal.id
            }

    # 2. Apply the formation change
    result = await tool_apply_formation_change(proposal.formation_change)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=f"Failed to apply formation change: {result.get('error')}",
        )

    # 3. Autonomous SRE Remediation
    if proposal.formation_change.remediation_action == "restart_node":
        from control_plane.tools import tool_restart_node
        logger.info(f"Triggering automated SRE action on {proposal.formation_change.target_node}")
        remediation_result = await tool_restart_node(proposal.formation_change.target_node)
        
        # Append remediation status to feedback for the agent reflection loop
        if remediation_result.get("success"):
            request.feedback += f" [SRE Action: Successfully restarted {proposal.formation_change.target_node}]."
        else:
            request.feedback += f" [SRE Action: Failed to restart {proposal.formation_change.target_node}]."

    # Trigger reflection loop
    learning = await reflect_on_outcome(
        incident=incident,
        proposal=proposal,
        was_approved=True,
        human_feedback=request.feedback or "Approved without additional feedback",
    )

    # Clear the dead node from known set so monitor doesn't re-trigger
    runtime._known_dead_nodes.discard(proposal.formation_change.target_node)

    return {
        "status": "approved_and_applied",
        "proposal_id": proposal.id,
        "formation_applied": result.get("new_config"),
        "learning": learning.model_dump(),
    }


@app.post("/reject")
async def reject_proposal(request: RejectionRequest):
    """
    Human rejects the agent's proposal.
    This triggers: reflection loop → lesson learned for future improvement.
    """
    proposal = await db.get_proposal(request.proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    incident = await db.get_incident(proposal.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Associated incident not found")

    learning = await reflect_on_outcome(
        incident=incident,
        proposal=proposal,
        was_approved=False,
        human_feedback=request.feedback,
    )

    return {
        "status": "rejected",
        "proposal_id": proposal.id,
        "learning": learning.model_dump(),
    }


# --- Agent Interrogation Console ---

@app.post("/chat")
async def interrogate_agent(request: ChatRequest):
    """
    Read-only human query endpoint for Quizzing the AI.
    Now includes system context for smarter interrogation.
    """
    active_incidents = await db.get_active_incidents()
    response = await chat_with_agent(
        request.message, 
        node_states=runtime.node_states, 
        active_incidents=active_incidents
    )
    return {"reply": response}

@app.get("/monitor/check-llm")
async def check_llm_health():
    """Verify Z.ai Cloud connectivity with a lightweight back-and-forth pulse."""
    import time
    start = time.perf_counter()
    try:
        # Simple prompt to verify API keys and network
        pulse = await chat_with_agent("Respond with 'PULSE_OK'.")
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {"status": "healthy", "reply": pulse, "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/monitor/check-proxy")
async def check_proxy_health():
    """Verify the Dynamic Proxy is alive on internal localhost:8000."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:8000/health")
            return {"status": "healthy", "reply": resp.json()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/chaos/{node_name}/health")
async def proxy_chaos_health(node_name: str):
    """Proxies health checks to internal nodes for diagnostics."""
    node_map = {"aws": "http://127.0.0.1:8001", "azure": "http://127.0.0.1:8002", "gcp": "http://127.0.0.1:8003"}
    if node_name not in node_map:
        raise HTTPException(status_code=404, detail="Node mapping not found")
        
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{node_map[node_name]}/health")
        return resp.json()


# --- Evolutionary Memory ---

@app.get("/learnings")
async def list_learnings():
    learnings = await db.get_all_learnings()
    return {"learnings": [l.model_dump() for l in learnings]}


# --- Circuit Breaker ---

@app.post("/circuit-breaker/reset")
async def reset_circuit_breaker():
    """Manual override to reset the circuit breaker and re-enable agent autonomy."""
    runtime.circuit_breaker_active = False
    runtime.consecutive_agent_failures = 0
    logger.info("Circuit breaker reset by human operator")
    return {"status": "circuit_breaker_reset", "agent_enabled": True}


# --- Chaos Proxy (Frontend Bridge) ---
import httpx

@app.post("/chaos/{node_name}/fail")
async def proxy_chaos_fail(node_name: str, request: Request):
    """Proxies chaos injection to internal nodes."""
    node_map = {
        "aws": "http://127.0.0.1:8001", 
        "azure": "http://127.0.0.1:8002", 
        "gcp": "http://127.0.0.1:8003"
    }
    if node_name not in node_map:
        raise HTTPException(status_code=404, detail="Node mapping not found")
        
    body = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{node_map[node_name]}/fail", json=body)
        return resp.json()

@app.post("/chaos/{node_name}/recover")
async def proxy_chaos_recover(node_name: str):
    """Proxies recovery commands to internal nodes."""
    node_map = {"aws": "http://127.0.0.1:8001", "azure": "http://127.0.0.1:8002", "gcp": "http://127.0.0.1:8003"}
    if node_name not in node_map:
        raise HTTPException(status_code=404, detail="Node mapping not found")
        
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{node_map[node_name]}/recover")
        return resp.json()

# --- Manual Trigger (for demos) ---

@app.post("/trigger-triage")
async def manual_triage():
    """
    Manually trigger the agent triage pipeline.
    Useful for demos — checks all nodes right now and creates a proposal if needed.
    """
    node_states = await tool_check_all_nodes()
    runtime.node_states = node_states

    learnings_ctx = await get_learnings_context()
    proposal = await triage_incident(node_states, learnings_ctx)

    if not proposal:
        return {"status": "no_action_needed", "all_nodes_healthy": True}

    return {
        "status": "proposal_created",
        "proposal": proposal.model_dump(),
    }


@app.get("/monitor/metrics")
async def get_metrics_bridge():
    """Bridge to the internal load generator metrics."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("http://127.0.0.1:8005/metrics")
            if resp.status_code == 200:
                return resp.json()
            return {"history": [], "error": f"Metrics server returned {resp.status_code}"}
    except Exception as e:
        return {"history": [], "error": str(e)}
