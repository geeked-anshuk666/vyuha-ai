"""
Tests for Vyuha AI Dynamic Reverse Proxy.
Verifies config loading, weighted routing, API-driven config updates, and error handling.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from proxy.main import app, runtime, ProxyConfig, RouteEntry, ProxyRuntime


@pytest.fixture(autouse=True)
def reset_runtime(tmp_path):
    """Reset proxy state and use a temp config file for each test."""
    config_data = {
        "formation": "test-balanced",
        "routes": [
            {"name": "node-a", "url": "http://node-a:8000", "weight": 50, "active": True},
            {"name": "node-b", "url": "http://node-b:8000", "weight": 50, "active": True},
        ],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    runtime.config = ProxyConfig.model_validate(config_data)
    runtime.config_last_loaded = 0.0
    runtime.config_mtime = 0.0
    runtime.total_requests = 0

    with patch("proxy.main.CONFIG_PATH", config_file):
        yield config_file


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- /proxy/status ---

@pytest.mark.anyio
async def test_proxy_status_returns_config(client):
    resp = await client.get("/proxy/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["formation"] == "test-balanced"
    assert len(data["routes"]) == 2
    assert data["total_requests"] == 0


# --- /proxy/config ---

@pytest.mark.anyio
async def test_update_config_via_api(client, reset_runtime):
    new_config = {
        "formation": "failover-b",
        "routes": [
            {"name": "node-a", "url": "http://node-a:8000", "weight": 0, "active": False},
            {"name": "node-b", "url": "http://node-b:8000", "weight": 100, "active": True},
        ],
    }

    with patch("proxy.main.CONFIG_PATH", reset_runtime):
        resp = await client.put(
            "/proxy/config",
            json=new_config,
            headers={"X-Vyuha-API-Key": "vyuha-default-secret-key"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["formation"] == "failover-b"
    assert data["routes"][0]["active"] is False
    assert data["routes"][1]["weight"] == 100


# --- Weighted Routing ---

def test_select_upstream_returns_active_route():
    runtime.config = ProxyConfig(
        formation="test",
        routes=[
            RouteEntry(name="a", url="http://a:8000", weight=100, active=True),
            RouteEntry(name="b", url="http://b:8000", weight=0, active=False),
        ],
    )

    for _ in range(20):
        selected = runtime.select_upstream()
        assert selected is not None
        assert selected.name == "a"


def test_select_upstream_returns_none_when_no_active():
    runtime.config = ProxyConfig(
        formation="dead",
        routes=[
            RouteEntry(name="a", url="http://a:8000", weight=50, active=False),
            RouteEntry(name="b", url="http://b:8000", weight=50, active=False),
        ],
    )

    selected = runtime.select_upstream()
    assert selected is None


def test_weighted_distribution():
    """Test that 90/10 weight distributes roughly correctly over 1000 selections."""
    runtime.config = ProxyConfig(
        formation="skewed",
        routes=[
            RouteEntry(name="heavy", url="http://h:8000", weight=90, active=True),
            RouteEntry(name="light", url="http://l:8000", weight=10, active=True),
        ],
    )

    counts = {"heavy": 0, "light": 0}
    for _ in range(1000):
        selected = runtime.select_upstream()
        assert selected is not None
        counts[selected.name] += 1

    assert counts["heavy"] > 700, f"Heavy should dominate, got {counts}"
    assert counts["light"] > 20, f"Light should appear sometimes, got {counts}"


# --- Config File Loading ---

def test_load_config_from_file(reset_runtime):
    with patch("proxy.main.CONFIG_PATH", reset_runtime):
        runtime.config_mtime = 0.0
        changed = runtime.load_config()
        assert changed is True
        assert runtime.config.formation == "test-balanced"
        assert len(runtime.config.routes) == 2


def test_load_config_no_change_on_same_mtime(reset_runtime):
    with patch("proxy.main.CONFIG_PATH", reset_runtime):
        runtime.config_mtime = 0.0
        runtime.load_config()
        changed = runtime.load_config()
        assert changed is False


# --- Forward Request Error Handling ---

@pytest.mark.anyio
async def test_forward_returns_502_when_no_active_upstreams(client):
    runtime.config = ProxyConfig(
        formation="dead",
        routes=[
            RouteEntry(name="a", url="http://a:8000", weight=50, active=False),
        ],
    )

    resp = await client.get("/some/path")
    assert resp.status_code == 502
    assert "No active upstream" in resp.json()["detail"]
