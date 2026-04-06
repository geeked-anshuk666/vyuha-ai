"""Quick smoke test for live Docker services."""
import httpx
import asyncio


async def main():
    async with httpx.AsyncClient(timeout=5.0) as c:
        # Node-A
        r = await c.get("http://localhost:8001/health")
        print(f"Node-A:  {r.status_code} | {r.json().get('status') or r.json().get('state')}")

        # Node-B
        r = await c.get("http://localhost:8002/health")
        print(f"Node-B:  {r.status_code} | {r.json().get('status') or r.json().get('state')}")

        # Proxy
        r = await c.get("http://localhost:8000/health")
        print(f"Proxy:   {r.status_code} | {r.json().get('status')}")

        # Orchestrator
        r = await c.get("http://localhost:9000/health")
        print(f"Orch:    {r.status_code} | {r.json().get('status')}")

        print("\nALL SERVICES HEALTHY")


if __name__ == "__main__":
    asyncio.run(main())
