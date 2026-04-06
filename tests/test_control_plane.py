"""
Tests for Vyuha AI Control Plane — DB, Tools, Agent, and Orchestrator API.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from httpx import ASGITransport, AsyncClient

from control_plane.models import (
    NodeHealthSnapshot, NodeState, Incident, IncidentSeverity,
    IncidentStatus, FormationChange, FormationAction, AgentProposal,
)
from control_plane import db
from control_plane.tools import tool_assess_severity, tool_build_failover_config
from control_plane.main import app


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Use a temp database for each test."""
    test_db = tmp_path / "test_vyuha.db"
    with patch.object(db, "DB_PATH", test_db):
        await db.init_db()
        yield test_db


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# === DB Tests ===

@pytest.mark.anyio
async def test_create_and_get_incident():
    incident = Incident(
        node_name="node-a",
        severity=IncidentSeverity.HIGH,
        description="Node-A is unreachable",
    )
    created = await db.create_incident(incident)
    assert created.id is not None

    fetched = await db.get_incident(created.id)
    assert fetched is not None
    assert fetched.node_name == "node-a"
    assert fetched.severity == IncidentSeverity.HIGH


@pytest.mark.anyio
async def test_update_incident_status():
    incident = await db.create_incident(Incident(
        node_name="node-b", severity=IncidentSeverity.MEDIUM,
        description="Degraded performance",
    ))
    await db.update_incident_status(incident.id, IncidentStatus.TRIAGING)

    fetched = await db.get_incident(incident.id)
    assert fetched.status == IncidentStatus.TRIAGING


@pytest.mark.anyio
async def test_create_and_get_proposal():
    incident = await db.create_incident(Incident(
        node_name="node-a", severity=IncidentSeverity.HIGH,
        description="Dead node",
    ))

    fc = FormationChange(
        incident_id=incident.id,
        action=FormationAction.REROUTE,
        target_node="node-a",
        reasoning="Reroute to node-b",
        proposed_config={"formation": "failover-b", "routes": []},
        confidence=0.85,
    )
    proposal = AgentProposal(
        incident_id=incident.id,
        formation_change=fc,
        agent_reasoning="Node-a is dead, routing traffic to node-b",
    )
    created = await db.create_proposal(proposal)
    assert created.id is not None

    fetched = await db.get_proposal(created.id)
    assert fetched is not None
    assert fetched.formation_change.action == FormationAction.REROUTE


@pytest.mark.anyio
async def test_get_active_incidents():
    await db.create_incident(Incident(
        node_name="node-a", severity=IncidentSeverity.HIGH,
        status=IncidentStatus.DETECTED, description="Dead",
    ))
    await db.create_incident(Incident(
        node_name="node-b", severity=IncidentSeverity.LOW,
        status=IncidentStatus.REFLECTED, description="Old resolved",
    ))

    active = await db.get_active_incidents()
    assert len(active) == 1
    assert active[0].node_name == "node-a"


# === Tool Tests ===

def test_assess_severity_critical():
    states = [
        NodeHealthSnapshot(node_name="a", url="x", state=NodeState.DEAD),
        NodeHealthSnapshot(node_name="b", url="y", state=NodeState.DEAD),
    ]
    assert tool_assess_severity(states) == IncidentSeverity.CRITICAL


def test_assess_severity_high():
    states = [
        NodeHealthSnapshot(node_name="a", url="x", state=NodeState.DEAD),
        NodeHealthSnapshot(node_name="b", url="y", state=NodeState.HEALTHY),
    ]
    assert tool_assess_severity(states) == IncidentSeverity.HIGH


def test_assess_severity_medium():
    states = [
        NodeHealthSnapshot(node_name="a", url="x", state=NodeState.DEGRADED),
        NodeHealthSnapshot(node_name="b", url="y", state=NodeState.HEALTHY),
    ]
    assert tool_assess_severity(states) == IncidentSeverity.MEDIUM


def test_build_failover_config():
    config = tool_build_failover_config(
        healthy_nodes=["node-b"],
        dead_nodes=["node-a"],
        node_urls={"node-a": "http://a:8000", "node-b": "http://b:8000"},
    )
    assert config["formation"] == "failover-node-b"
    assert len(config["routes"]) == 2

    active_routes = [r for r in config["routes"] if r["active"]]
    assert len(active_routes) == 1
    assert active_routes[0]["name"] == "node-b"
    assert active_routes[0]["weight"] == 100


def test_build_failover_config_no_healthy():
    config = tool_build_failover_config(
        healthy_nodes=[],
        dead_nodes=["node-a", "node-b"],
        node_urls={"node-a": "http://a:8000", "node-b": "http://b:8000"},
    )
    assert "emergency" in config["formation"]
    active_routes = [r for r in config["routes"] if r["active"]]
    assert len(active_routes) == 0
