"""
Tests for Vyuha AI Mock Cloud Node Service.
Verifies all endpoints, state transitions, and error handling.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from nodes.main import app, runtime, NodeState


@pytest.fixture(autouse=True)
def reset_runtime():
    """Reset node state before each test."""
    runtime.node_name = "test-node"
    runtime.cloud_provider = "aws-mock"
    runtime.region = "us-east-1"
    runtime.state = NodeState.HEALTHY
    runtime.failure_reason = None
    runtime.request_count = 0
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- /health ---

@pytest.mark.anyio
async def test_health_returns_200_when_healthy(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_name"] == "test-node"
    assert data["cloud_provider"] == "aws-mock"
    assert data["state"] == "healthy"
    assert data["uptime_seconds"] >= 0
    assert data["request_count"] >= 1


@pytest.mark.anyio
async def test_health_returns_503_when_dead(client):
    runtime.state = NodeState.DEAD
    runtime.failure_reason = "Simulated outage"

    resp = await client.get("/health")
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["state"] == "dead"
    assert detail["reason"] == "Simulated outage"


@pytest.mark.anyio
async def test_health_returns_200_when_degraded(client):
    runtime.state = NodeState.DEGRADED

    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["state"] == "degraded"


# --- /status ---

@pytest.mark.anyio
async def test_status_always_returns_200(client):
    runtime.state = NodeState.DEAD
    runtime.failure_reason = "Total failure"

    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "dead"
    assert data["failure_reason"] == "Total failure"


@pytest.mark.anyio
async def test_status_shows_healthy_by_default(client):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "healthy"
    assert data["failure_reason"] is None


# --- /info ---

@pytest.mark.anyio
async def test_info_returns_metadata(client):
    resp = await client.get("/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_name"] == "test-node"
    assert data["version"] == "1.0.0"
    assert "chaos-injection" in data["capabilities"]


# --- /fail ---

@pytest.mark.anyio
async def test_fail_sets_node_to_dead(client):
    resp = await client.post("/fail", json={"state": "dead", "reason": "Chaos test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["previous_state"] == "healthy"
    assert data["new_state"] == "dead"
    assert data["reason"] == "Chaos test"
    assert runtime.state == NodeState.DEAD


@pytest.mark.anyio
async def test_fail_sets_node_to_degraded(client):
    resp = await client.post("/fail", json={"state": "degraded", "reason": "Partial failure"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["new_state"] == "degraded"
    assert runtime.state == NodeState.DEGRADED


@pytest.mark.anyio
async def test_fail_rejects_healthy_state(client):
    resp = await client.post("/fail", json={"state": "healthy"})
    assert resp.status_code == 400


# --- /recover ---

@pytest.mark.anyio
async def test_recover_restores_healthy(client):
    runtime.state = NodeState.DEAD
    runtime.failure_reason = "Outage"

    resp = await client.post("/recover")
    assert resp.status_code == 200
    data = resp.json()
    assert data["previous_state"] == "dead"
    assert data["new_state"] == "healthy"
    assert runtime.state == NodeState.HEALTHY
    assert runtime.failure_reason is None


# --- Request Counter ---

@pytest.mark.anyio
async def test_request_counter_increments(client):
    await client.get("/health")
    await client.get("/status")
    await client.get("/info")
    assert runtime.request_count == 3
