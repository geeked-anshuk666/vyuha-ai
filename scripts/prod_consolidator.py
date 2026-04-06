import asyncio
import os
import signal
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CONSOLIDATOR] %(message)s")
logger = logging.getLogger("prod-consolidator")

class Service:
    def __init__(self, name, command, env=None):
        self.name = name
        self.command = command
        self.env = {**os.environ, **(env or {})}
        self.process = None

    async def start(self):
        logger.info(f"Starting {self.name}...")
        self.process = await asyncio.create_subprocess_shell(
            self.command,
            env=self.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        asyncio.create_task(self.log_output())

    async def log_output(self):
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            logger.info(f"[{self.name}] {line.decode().strip()}")

    async def wait(self):
        if self.process:
            return await self.process.wait()
        return 0

services = [
    # Node A (port 8001)
    Service("NODE-A", "python -m uvicorn nodes.main:app --host 0.0.0.0 --port 8001", {"NODE_NAME": "node-a", "CLOUD_PROVIDER": "aws", "REGION": "us-east-1"}),
    # Node B (port 8002)
    Service("NODE-B", "python -m uvicorn nodes.main:app --host 0.0.0.0 --port 8002", {"NODE_NAME": "node-b", "CLOUD_PROVIDER": "azure", "REGION": "westeurope"}),
    # Proxy (port 8000)
    Service("PROXY", "python -m uvicorn proxy.main:app --host 0.0.0.0 --port 8000", {"CONFIG_PATH": "/app/proxy/prod_config.json"}),
    # Orchestrator (port 9000 -> Expose this to Render via PORT env var)
    Service("ORCHESTRATOR", f"python -m uvicorn control_plane.main:app --host 0.0.0.0 --port {os.getenv('PORT', '9000')}")
]

async def main():
    try:
        logger.info("Initializing Vyuha AI Production Consolidation...")
        
        # Ensure we are in the right directory
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Effective UID: {os.getuid()}")

        # Ensure logs and proxy config exist
        try:
            os.makedirs("/app/data", exist_ok=True)
            logger.info("Data directory verified/created.")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to create /app/data: {e}")
            raise

        # Start all
        for s in services:
            await s.start()
            await asyncio.sleep(1) # Staggered start

        # Wait for completion (or kill)
        await asyncio.gather(*(s.wait() for s in services))
    except Exception as e:
        logger.exception(f"FATAL ERROR during startup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Termination signal received.")
    except Exception as e:
        logger.error(f"Unhandled exception in run loop: {e}")
        sys.exit(1)
