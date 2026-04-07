"""
Vyuha AI — Walled Garden Tools
Strict, constrained tools that the GLM agent can invoke.
The agent NEVER has direct shell access — only these API-level tools.
"""

import json
import logging
from datetime import datetime

import httpx

from control_plane.models import (
    NodeHealthSnapshot, NodeState, FormationChange,
    FormationAction, IncidentSeverity,
)

logger = logging.getLogger("vyuha-tools")

import os

IS_RENDER = os.getenv("RENDER", "false").lower() == "true"

if IS_RENDER:
    PROXY_URL = "http://127.0.0.1:8000"
    NODE_URLS = {
        "aws": "http://127.0.0.1:8001",
        "azure": "http://127.0.0.1:8002",
        "gcp": "http://127.0.0.1:8003",
    }
else:
    PROXY_URL = "http://vyuha-proxy:8000"
    NODE_URLS = {
        "aws": "http://aws:8000",
        "azure": "http://azure:8000",
        "gcp": "http://gcp:8000",
    }


async def tool_check_node_health(node_name: str) -> NodeHealthSnapshot:
    """Check the health of a specific node. Returns a snapshot."""
    url = NODE_URLS.get(node_name)
    if not url:
        return NodeHealthSnapshot(
            node_name=node_name, url="unknown",
            state=NodeState.UNKNOWN, error=f"Unknown node: {node_name}",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.utcnow()
            resp = await client.get(f"{url}/health")
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000

            if resp.status_code == 200:
                data = resp.json()
                return NodeHealthSnapshot(
                    node_name=node_name, url=url,
                    state=NodeState(data["state"]),
                    response_time_ms=round(elapsed, 2),
                )
            elif resp.status_code == 503:
                detail = resp.json().get("detail", {})
                return NodeHealthSnapshot(
                    node_name=node_name, url=url,
                    state=NodeState.DEAD,
                    response_time_ms=round(elapsed, 2),
                    error=detail.get("reason", "503 Service Unavailable"),
                )
            else:
                return NodeHealthSnapshot(
                    node_name=node_name, url=url,
                    state=NodeState.UNKNOWN,
                    response_time_ms=round(elapsed, 2),
                    error=f"Unexpected status: {resp.status_code}",
                )
    except httpx.ConnectError:
        return NodeHealthSnapshot(
            node_name=node_name, url=url,
            state=NodeState.DEAD,
            error="Connection refused — node unreachable",
        )
    except httpx.TimeoutException:
        return NodeHealthSnapshot(
            node_name=node_name, url=url,
            state=NodeState.DEAD,
            error="Health check timed out (>5s)",
        )


async def tool_check_all_nodes() -> list[NodeHealthSnapshot]:
    """Check health of all known nodes."""
    results = []
    for name in NODE_URLS:
        snapshot = await tool_check_node_health(name)
        results.append(snapshot)
    return results


async def tool_get_current_formation() -> dict:
    """Get the current proxy routing configuration."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{PROXY_URL}/proxy/status")
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Proxy returned {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


import os

PROXY_API_KEY = os.getenv("VYUHA_API_KEY", "vyuha-default-secret-key")

async def tool_apply_formation_change(formation_change: FormationChange) -> dict:
    """
    Apply a formation change by updating the proxy config.
    This is the primary mechanism for the agent to affect the infrastructure.
    Authenticates with the proxy using VYUHA_API_KEY.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.put(
                f"{PROXY_URL}/proxy/config",
                json=formation_change.proposed_config,
                headers={"X-Vyuha-API-Key": PROXY_API_KEY}
            )
            if resp.status_code == 200:
                logger.info(f"Formation change applied: {formation_change.action}")
                return {"success": True, "new_config": resp.json()}
            return {"success": False, "error": f"Proxy returned {resp.status_code}: {resp.text}"}
    except Exception as e:
        logger.error(f"Failed to apply formation change: {e}")
        return {"success": False, "error": str(e)}


async def tool_restart_node(node_name: str) -> dict:
    """
    Attempt to auto-remediate a node failure by restarting it (hitting its /recover endpoint).
    Simulates an SRE-level action like bouncing a pod or restarting a systemctl service.
    """
    url = NODE_URLS.get(node_name)
    if not url:
        return {"success": False, "error": f"Unknown node: {node_name}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{url}/recover")
            if resp.status_code == 200:
                logger.info(f"Remediation successful: {node_name} recovered")
                return {"success": True, "details": resp.json()}
            return {"success": False, "error": f"Node returned {resp.status_code}: {resp.text}"}
    except Exception as e:
        logger.error(f"Failed to remediate node {node_name}: {e}")
        return {"success": False, "error": str(e)}


def tool_assess_severity(node_states: list[NodeHealthSnapshot]) -> IncidentSeverity:
    """Determine incident severity based on current node states."""
    dead_count = sum(1 for n in node_states if n.state == NodeState.DEAD)
    degraded_count = sum(1 for n in node_states if n.state in (NodeState.DEGRADED, NodeState.HIGH_LATENCY, NodeState.FLAKY))
    total = len(node_states)

    if dead_count == total:
        return IncidentSeverity.CRITICAL
    elif dead_count >= 1:
        return IncidentSeverity.HIGH
    elif degraded_count >= 1:
        return IncidentSeverity.MEDIUM
    return IncidentSeverity.LOW


def tool_build_failover_config(
    healthy_nodes: list[str],
    dead_nodes: list[str],
    node_urls: dict[str, str] | None = None,
) -> dict:
    """
    Build a new proxy config that routes traffic only to healthy nodes.
    This is a deterministic tool — the agent decides WHICH nodes, this tool builds the config.
    """
    urls = node_urls or NODE_URLS
    total_weight = 100
    num_healthy = len(healthy_nodes)

    if num_healthy == 0:
        return {
            "formation": "emergency-no-healthy-nodes",
            "routes": [
                {"name": name, "url": urls.get(name, "unknown"), "weight": 0, "active": False}
                for name in list(healthy_nodes) + list(dead_nodes)
            ],
        }

    weight_per_node = total_weight // num_healthy
    routes = []

    for name in healthy_nodes:
        routes.append({
            "name": name,
            "url": urls.get(name, "unknown"),
            "weight": weight_per_node,
            "active": True,
        })

    for name in dead_nodes:
        routes.append({
            "name": name,
            "url": urls.get(name, "unknown"),
            "weight": 0,
            "active": False,
        })

    formation_name = f"failover-{'_'.join(healthy_nodes)}"
    return {"formation": formation_name, "routes": routes}


# --- Tool Registry (for the agent to enumerate available tools) ---

TOOL_REGISTRY = {
    "check_node_health": {
        "description": "Check the health status of a specific node by name",
        "parameters": {"node_name": "string — the node identifier (e.g., 'node-a')"},
        "function": tool_check_node_health,
    },
    "check_all_nodes": {
        "description": "Check health of all known upstream nodes",
        "parameters": {},
        "function": tool_check_all_nodes,
    },
    "get_current_formation": {
        "description": "Get the current proxy routing configuration and traffic distribution",
        "parameters": {},
        "function": tool_get_current_formation,
    },
    "apply_formation_change": {
        "description": "Apply a new routing formation to the proxy",
        "parameters": {"formation_change": "FormationChange object"},
        "function": tool_apply_formation_change,
    },
    "assess_severity": {
        "description": "Assess the severity of the current situation based on node states",
        "parameters": {"node_states": "list of NodeHealthSnapshot"},
        "function": tool_assess_severity,
    },
    "build_failover_config": {
        "description": "Build a proxy config that routes only to healthy nodes",
        "parameters": {
            "healthy_nodes": "list of healthy node names",
            "dead_nodes": "list of dead node names",
        },
        "function": tool_build_failover_config,
    },
    "restart_node": {
        "description": "Attempt an autonomous SRE remediation by restarting the target node service",
        "parameters": {"node_name": "string — the node identifier"},
        "function": tool_restart_node,
    },
}
