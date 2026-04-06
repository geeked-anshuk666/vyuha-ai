"""
Vyuha AI — Mock Cloud Node Service
Simulates a cloud provider endpoint (AWS/Azure/GCP).
Each instance is configured via environment variables to represent a different cloud region.
"""

import os
import time
import asyncio
import random
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


# --- Models ---

class NodeState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    HIGH_LATENCY = "high_latency"
    FLAKY = "flaky"
    DEAD = "dead"


class HealthResponse(BaseModel):
    node_name: str
    cloud_provider: str
    region: str
    state: NodeState
    uptime_seconds: float = Field(ge=0)
    request_count: int = Field(ge=0)


class StatusResponse(BaseModel):
    node_name: str
    cloud_provider: str
    region: str
    state: NodeState
    uptime_seconds: float
    request_count: int
    failure_reason: str | None = None


class InfoResponse(BaseModel):
    node_name: str
    cloud_provider: str
    region: str
    version: str = "1.0.0"
    capabilities: list[str]


class FailRequest(BaseModel):
    state: NodeState = NodeState.DEAD
    reason: str = "Manual chaos injection"


class FailResponse(BaseModel):
    node_name: str
    previous_state: NodeState
    new_state: NodeState
    reason: str


class RecoverResponse(BaseModel):
    node_name: str
    previous_state: NodeState
    new_state: NodeState = NodeState.HEALTHY


# --- Runtime State ---

class NodeRuntime:
    """Mutable runtime state for this node instance."""

    def __init__(self) -> None:
        self.node_name: str = os.getenv("NODE_NAME", "node-unknown")
        self.cloud_provider: str = os.getenv("CLOUD_PROVIDER", "unknown")
        self.region: str = os.getenv("REGION", "us-east-1")
        self.state: NodeState = NodeState.HEALTHY
        self.failure_reason: str | None = None
        self.start_time: float = time.time()
        self.request_count: int = 0

    @property
    def uptime_seconds(self) -> float:
        return round(time.time() - self.start_time, 2)

    def increment_requests(self) -> None:
        self.request_count += 1


runtime = NodeRuntime()


# --- App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Reset runtime state on startup."""
    runtime.__init__()
    yield


app = FastAPI(
    title=f"Vyuha Node — {runtime.node_name}",
    description="Mock cloud node for Vyuha AI multi-cloud recovery simulation",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Endpoints ---

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Primary health endpoint polled by the Orchestrator.
    Returns current node state. If the node is DEAD, returns 503.
    """
    runtime.increment_requests()

    if runtime.state == NodeState.HIGH_LATENCY:
        await asyncio.sleep(1.5)  # Simulate severe network degradation
        
    if runtime.state == NodeState.FLAKY:
        if random.random() < 0.25:  # 25% drop rate
            raise HTTPException(
                status_code=503,
                detail={
                    "node_name": runtime.node_name,
                    "state": runtime.state.value,
                    "reason": "Intermittent packet drop (Flaky)"
                }
            )

    if runtime.state == NodeState.DEAD:
        raise HTTPException(
            status_code=503,
            detail={
                "node_name": runtime.node_name,
                "state": runtime.state.value,
                "reason": runtime.failure_reason or "Node is dead",
            },
        )

    return HealthResponse(
        node_name=runtime.node_name,
        cloud_provider=runtime.cloud_provider,
        region=runtime.region,
        state=runtime.state,
        uptime_seconds=runtime.uptime_seconds,
        request_count=runtime.request_count,
    )


@app.get("/status", response_model=StatusResponse)
async def detailed_status():
    """
    Detailed status endpoint — always returns 200 even when dead.
    Used by the dashboard for display purposes (not health checks).
    """
    runtime.increment_requests()

    return StatusResponse(
        node_name=runtime.node_name,
        cloud_provider=runtime.cloud_provider,
        region=runtime.region,
        state=runtime.state,
        uptime_seconds=runtime.uptime_seconds,
        request_count=runtime.request_count,
        failure_reason=runtime.failure_reason,
    )


@app.get("/info", response_model=InfoResponse)
async def node_info():
    """Static node metadata — identity, capabilities, version."""
    runtime.increment_requests()

    return InfoResponse(
        node_name=runtime.node_name,
        cloud_provider=runtime.cloud_provider,
        region=runtime.region,
        capabilities=["http", "health-check", "chaos-injection", "graceful-degradation"],
    )


@app.post("/fail", response_model=FailResponse)
async def inject_failure(request: FailRequest):
    """
    Chaos endpoint — toggles the node into a degraded or dead state.
    Used to simulate cloud outages for the Orchestrator to detect and recover from.
    """
    runtime.increment_requests()
    previous_state = runtime.state

    if request.state == NodeState.HEALTHY:
        raise HTTPException(
            status_code=400,
            detail="Use POST /recover to restore to healthy state",
        )

    runtime.state = request.state
    runtime.failure_reason = request.reason

    return FailResponse(
        node_name=runtime.node_name,
        previous_state=previous_state,
        new_state=runtime.state,
        reason=request.reason,
    )


@app.post("/recover", response_model=RecoverResponse)
async def recover_node():
    """
    Restores the node to HEALTHY state.
    Called after the Orchestrator validates that the root cause is resolved.
    """
    runtime.increment_requests()
    previous_state = runtime.state

    runtime.state = NodeState.HEALTHY
    runtime.failure_reason = None

    return RecoverResponse(
        node_name=runtime.node_name,
        previous_state=previous_state,
    )
