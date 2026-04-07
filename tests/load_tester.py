import time
import asyncio
import httpx
import os
from collections import deque
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading
import uvicorn
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [LOAD] %(message)s")

app = FastAPI(title="Vyuha Load Tester Metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep the last 60 seconds of traffic history
TRAFFIC_HISTORY = deque(maxlen=60)

# Current second accumulators
current_success = 0
current_fail = 0
current_latency_total = 0.0
current_latency_count = 0

# Hit ALL 3 nodes directly so chaos is immediately visible in graph
NODE_URLS = {
    "aws":   os.getenv("AWS_URL",   "http://localhost:8001"),
    "azure": os.getenv("AZURE_URL", "http://localhost:8002"),
    "gcp":   os.getenv("GCP_URL",   "http://localhost:8003"),
}

async def probe_node(client: httpx.AsyncClient, name: str, url: str):
    global current_success, current_fail, current_latency_total, current_latency_count
    try:
        start = time.perf_counter()
        resp = await client.get(f"{url}/health", timeout=2.0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if resp.status_code == 200:
            current_success += 1
        else:
            current_fail += 1
        current_latency_total += elapsed_ms
        current_latency_count += 1
    except httpx.RequestError:
        current_fail += 1

async def traffic_generator():
    load_delay = float(os.getenv("LOAD_DELAY", "0.1"))
    logging.info(f"Starting multi-node traffic generator ({load_delay}s delay, ~{1/load_delay:.0f} RPS per node)")

    async with httpx.AsyncClient() as client:
        while True:
            # Probe all nodes in parallel every tick
            await asyncio.gather(*[
                probe_node(client, name, url)
                for name, url in NODE_URLS.items()
            ])
            await asyncio.sleep(load_delay)

async def metrics_aggregator():
    global current_success, current_fail, current_latency_total, current_latency_count
    while True:
        await asyncio.sleep(1.0)
        avg_latency = (
            round(current_latency_total / current_latency_count, 1)
            if current_latency_count > 0 else 0
        )
        snapshot = {
            "time": time.strftime("%H:%M:%S"),
            "success": current_success,
            "fail": current_fail,
            "latency_ms": avg_latency,
        }
        TRAFFIC_HISTORY.append(snapshot)
        current_success = 0
        current_fail = 0
        current_latency_total = 0.0
        current_latency_count = 0

def start_background_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(traffic_generator())
    loop.create_task(metrics_aggregator())
    loop.run_forever()

@app.get("/metrics")
def get_metrics():
    return {"history": list(TRAFFIC_HISTORY)}

if __name__ == "__main__":
    t = threading.Thread(target=start_background_loop, daemon=True)
    t.start()
    logging.info("Starting Load Generator Metrics on port 8005...")
    metrics_port = int(os.getenv("METRICS_PORT", "8005"))
    uvicorn.run(app, host="0.0.0.0", port=metrics_port)

