"""
Tests for Proxy and Orchestrator security features.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from pathlib import Path

# Make sure we don't accidentally write to real config from proxy
import os
os.environ["CONFIG_PATH"] = "test_config_tmp.json"
with open("test_config_tmp.json", "w") as f:
    f.write('{"formation": "init", "routes": []}')

from unittest.mock import patch

from proxy.main import app as proxy_app
from proxy.main import runtime
from control_plane.main import app as control_app

@pytest.fixture
async def proxy_client():
    transport = ASGITransport(app=proxy_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
async def control_client():
    transport = ASGITransport(app=control_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.anyio
async def test_proxy_config_requires_auth(proxy_client):
    # Without Auth
    new_config = {
        "formation": "hacked",
        "routes": [{"name": "node-a", "url": "http://node-a:8000", "weight": 100, "active": True}]
    }
    resp = await proxy_client.put("/proxy/config", json=new_config)
    assert resp.status_code == 403

@pytest.mark.anyio
async def test_proxy_config_accepts_valid_auth(proxy_client):
    new_config = {
        "formation": "authorized",
        "routes": [{"name": "node-a", "url": "http://node-a:8000", "weight": 100, "active": True}]
    }
    with patch("proxy.main.CONFIG_PATH", Path("test_config_tmp.json")):
        # reset runtime to prevent trying to write to non-existent objects
        runtime.config_last_loaded = 0
        resp = await proxy_client.put(
            "/proxy/config",
            json=new_config,
            headers={"X-Vyuha-API-Key": "vyuha-default-secret-key"}
        )
    assert resp.status_code == 200

@pytest.mark.anyio
async def test_proxy_security_headers(proxy_client):
    resp = await proxy_client.get("/proxy/status")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"

@pytest.mark.anyio
async def test_control_plane_rate_limiter(control_client):
    responses = []
    # REQUEST_RATE_LIMIT is 100
    for _ in range(105):
        resp = await control_client.get("/monitor/nodes")
        responses.append(resp.status_code)

    assert 429 in responses
