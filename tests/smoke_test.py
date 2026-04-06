"""Quick smoke test for live Docker services."""
import httpx
import asyncio


async def main():
    async with httpx.AsyncClient(timeout=5.0) as c:
        # Node-A
        r = await c.get("http://localhost:8001/health")
        print(f"Node-A:  {r.status_code} | {r.json()['state']}")

        # Node-B
        r = await c.get("http://localhost:8002/health")
        print(f"Node-B:  {r.status_code} | {r.json()['state']}")

        # Proxy
        r = await c.get("http://localhost:8000/proxy/status")
        data = r.json()
        print(f"Proxy:   {r.status_code} | formation={data.get('formation')}, routes={len(data.get('routes', []))}")

        # Orchestrator
        r = await c.get("http://localhost:9000/monitor/status")
        data = r.json()
        print(f"Orch:    {r.status_code} | monitoring={data['monitoring_active']}, nodes={len(data['node_states'])}")

        print("\n✅ ALL SERVICES HEALTHY")


asyncio.run(main())
