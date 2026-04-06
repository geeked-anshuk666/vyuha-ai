import time
import asyncio
import httpx
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

async def traffic_generator():
    global current_success, current_fail
    async with httpx.AsyncClient(timeout=2.0) as client:
        while True:
            try:
                # We hit the proxy, which forwards to node-a / node-b
                resp = await client.get("http://localhost:8000/health")
                if resp.status_code == 200:
                    current_success += 1
                else:
                    current_fail += 1
            except httpx.RequestError:
                current_fail += 1
            
            # Fire at approx 50 requests per second (using small sleep to yield loop)
            await asyncio.sleep(0.02)

async def metrics_aggregator():
    global current_success, current_fail
    while True:
        # Every 1 second, snapshot the metrics
        await asyncio.sleep(1.0)
        snapshot = {
            "time": time.strftime("%H:%M:%S"),
            "success": current_success,
            "fail": current_fail
        }
        TRAFFIC_HISTORY.append(snapshot)
        # Reset counters for the next second
        current_success = 0
        current_fail = 0

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
    # Start the traffic generator in a background thread
    t = threading.Thread(target=start_background_loop, daemon=True)
    t.start()
    
    # Run the metrics API on port 8005
    logging.info("Starting Load Generator Metrics on port 8005...")
    uvicorn.run(app, host="0.0.0.0", port=8005)
