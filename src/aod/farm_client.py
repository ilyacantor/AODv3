import httpx
from typing import Optional
from src.aod.config import FARM_URL


class FarmClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or FARM_URL
        self.client = httpx.AsyncClient(timeout=60.0)

    async def create_enterprise(self, archetype: str, scale: str) -> dict:
        url = f"{self.base_url}/api/farm/enterprise/new"
        response = await self.client.post(url, json={
            "archetype": archetype,
            "scale": scale
        })
        response.raise_for_status()
        return response.json()

    async def get_ground_truth(self, tenant_id: str) -> dict:
        url = f"{self.base_url}/api/farm/enterprise/{tenant_id}/ground-truth"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_enterprise(self, tenant_id: str) -> dict:
        url = f"{self.base_url}/api/farm/enterprise/{tenant_id}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def list_enterprises(self) -> dict:
        url = f"{self.base_url}/api/farm/enterprises"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()


farm_client = FarmClient()
