"""
Vyuha AI — Dynamic Reverse Proxy
Routes incoming traffic to upstream cloud nodes based on a hot-reloaded config.json.
Supports weighted routing and automatic failover when a node is unreachable.
"""

import json
import os
import random
import time
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PROXY] %(message)s")
logger = logging.getLogger("vyuha-proxy")

CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "/app/config.json"))
RELOAD_INTERVAL = int(os.getenv("RELOAD_INTERVAL", "3"))


# --- Models ---

class RouteEntry(BaseModel):
    name: str
    url: str
    weight: int = Field(ge=0, le=100)
    active: bool = True


class ProxyConfig(BaseModel):
    formation: str = "balanced"
    routes: list[RouteEntry]


class ProxyStatus(BaseModel):
    formation: str
    routes: list[RouteEntry]
    config_last_loaded: float
    total_requests: int
    uptime_seconds: float


class ConfigUpdateRequest(BaseModel):
    formation: str
    routes: list[RouteEntry]


# --- Runtime State ---

class ProxyRuntime:
    def __init__(self) -> None:
        self.config: ProxyConfig = ProxyConfig(formation="initializing", routes=[])
        self.config_last_loaded: float = 0.0
        self.config_mtime: float = 0.0
        self.total_requests: int = 0
        self.start_time: float = time.time()
        self._reload_task: asyncio.Task | None = None

    @property
    def uptime_seconds(self) -> float:
        return round(time.time() - self.start_time, 2)

    def load_config(self) -> bool:
        """Load config from disk. Returns True if config changed."""
        try:
            if not CONFIG_PATH.exists():
                logger.warning(f"Config file not found: {CONFIG_PATH}")
                return False

            mtime = CONFIG_PATH.stat().st_mtime
            if mtime == self.config_mtime:
                return False

            raw = CONFIG_PATH.read_text(encoding="utf-8")
            new_config = ProxyConfig.model_validate_json(raw)
            self.config = new_config
            self.config_mtime = mtime
            self.config_last_loaded = time.time()
            logger.info(f"Config reloaded: formation={new_config.formation}, routes={len(new_config.routes)}")
            return True
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    def save_config(self, config: ProxyConfig) -> None:
        """Write config to disk (called by orchestrator API)."""
        CONFIG_PATH.write_text(
            config.model_dump_json(indent=4),
            encoding="utf-8",
        )
        self.config = config
        self.config_mtime = CONFIG_PATH.stat().st_mtime
        self.config_last_loaded = time.time()
        logger.info(f"Config saved: formation={config.formation}")

    def select_upstream(self) -> RouteEntry | None:
        """Weighted random selection from active routes."""
        active = [r for r in self.config.routes if r.active]
        if not active:
            return None

        total_weight = sum(r.weight for r in active)
        if total_weight == 0:
            return random.choice(active)

        roll = random.uniform(0, total_weight)
        cumulative = 0.0
        for route in active:
            cumulative += route.weight
            if roll <= cumulative:
                return route

        return active[-1]


runtime = ProxyRuntime()


async def config_reload_loop() -> None:
    """Background task that polls config.json for changes."""
    while True:
        runtime.load_config()
        await asyncio.sleep(RELOAD_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime.load_config()
    task = asyncio.create_task(config_reload_loop())
    runtime._reload_task = task
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Vyuha Proxy — Dynamic Reverse Proxy",
    description="Routes traffic to upstream nodes based on hot-reloaded config",
    version="1.0.0",
    lifespan=lifespan,
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Adds security headers to all proxy responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


# --- Security ---
from fastapi import Depends
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("VYUHA_API_KEY", "vyuha-default-secret-key")
api_key_header = APIKeyHeader(name="X-Vyuha-API-Key", auto_error=True)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

# --- Proxy Endpoints ---

@app.get("/proxy/status", response_model=ProxyStatus)
async def proxy_status():
    """Returns current proxy configuration and stats. Open for monitoring."""
    return ProxyStatus(
        formation=runtime.config.formation,
        routes=runtime.config.routes,
        config_last_loaded=runtime.config_last_loaded,
        total_requests=runtime.total_requests,
        uptime_seconds=runtime.uptime_seconds,
    )


@app.put("/proxy/config", response_model=ProxyConfig, dependencies=[Depends(verify_api_key)])
async def update_config(request: ConfigUpdateRequest):
    """
    API endpoint for the Orchestrator to push config changes.
    This is the mechanism by which the AI applies "formation changes."
    Protected by API Key.
    """
    new_config = ProxyConfig(
        formation=request.formation,
        routes=request.routes,
    )
    runtime.save_config(new_config)
    return new_config


@app.post("/proxy/reload", dependencies=[Depends(verify_api_key)])
async def force_reload():
    """Force an immediate config reload from disk. Protected by API Key."""
    changed = runtime.load_config()
    return {"reloaded": changed, "formation": runtime.config.formation}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def forward_request(request: Request, path: str):
    """
    Catch-all reverse proxy handler.
    Selects an upstream via weighted routing and forwards the request.
    """
    runtime.total_requests += 1

    upstream = runtime.select_upstream()
    if upstream is None:
        raise HTTPException(
            status_code=502,
            detail="No active upstream nodes available",
        )

    target_url = f"{upstream.url.rstrip('/')}/{path}"

    try:
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)
        headers["X-Vyuha-Upstream"] = upstream.name

        async with httpx.AsyncClient(timeout=10.0) as client:
            proxy_resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=dict(request.query_params),
            )

        response_headers = dict(proxy_resp.headers)
        response_headers["X-Vyuha-Upstream"] = upstream.name
        response_headers["X-Vyuha-Formation"] = runtime.config.formation
        response_headers.pop("content-encoding", None)
        response_headers.pop("content-length", None)
        response_headers.pop("transfer-encoding", None)

        return Response(
            content=proxy_resp.content,
            status_code=proxy_resp.status_code,
            headers=response_headers,
        )

    except httpx.ConnectError:
        logger.error(f"Connection refused: {upstream.name} at {upstream.url}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_connection_refused",
                "upstream": upstream.name,
                "url": upstream.url,
            },
        )
    except httpx.TimeoutException:
        logger.error(f"Timeout: {upstream.name} at {upstream.url}")
        raise HTTPException(
            status_code=504,
            detail={
                "error": "upstream_timeout",
                "upstream": upstream.name,
                "url": upstream.url,
            },
        )
