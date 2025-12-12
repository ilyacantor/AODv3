import httpx
import logging
from typing import Optional, Dict, Any, List

from src.aod.config import FARM_URL

logger = logging.getLogger(__name__)


def normalize_ground_truth(
    raw_response: Any,
    tenant_id: str = "",
    run_id: str = ""
) -> Dict[str, Any]:
    """
    Normalize Farm ground truth response to a consistent shape.
    
    Handles multiple inbound shapes:
    - {"ground_truth": {"expected_assets": [...]}}  (old format)
    - {"ground_truth": [...]}  (new format)
    - [...]  (top-level list)
    - Any error/malformed content
    
    Returns:
        {"expected_assets": [...], "raw_shape": "...", "parse_error": None|str}
    """
    result = {
        "expected_assets": [],
        "raw_shape": "unknown",
        "parse_error": None
    }
    
    try:
        if raw_response is None:
            result["raw_shape"] = "null"
            result["parse_error"] = "Farm returned null response"
            logger.warning(
                f"Farm ground truth shape drift: shape=null tenant_id={tenant_id} run_id={run_id}"
            )
            return result
        
        if isinstance(raw_response, list):
            result["raw_shape"] = "top_level_list"
            result["expected_assets"] = raw_response
            logger.warning(
                f"Farm ground truth shape drift: shape=top_level_list tenant_id={tenant_id} run_id={run_id}"
            )
            return result
        
        if not isinstance(raw_response, dict):
            result["raw_shape"] = f"unexpected_type:{type(raw_response).__name__}"
            result["parse_error"] = f"Farm returned unexpected type: {type(raw_response).__name__}"
            logger.warning(
                f"Farm ground truth shape drift: shape={result['raw_shape']} tenant_id={tenant_id} run_id={run_id}"
            )
            return result
        
        ground_truth = raw_response.get("ground_truth")
        
        if ground_truth is None:
            if "expected_assets" in raw_response:
                result["raw_shape"] = "dict:expected_assets_top_level"
                assets = raw_response.get("expected_assets", [])
                result["expected_assets"] = assets if isinstance(assets, list) else []
                return result
            
            result["raw_shape"] = "dict:no_ground_truth_key"
            result["parse_error"] = "Farm response missing 'ground_truth' key"
            logger.warning(
                f"Farm ground truth shape drift: shape=dict:no_ground_truth_key tenant_id={tenant_id} run_id={run_id}"
            )
            return result
        
        if isinstance(ground_truth, list):
            result["raw_shape"] = "dict:ground_truth=list"
            result["expected_assets"] = ground_truth
            logger.info(
                f"Farm ground truth normalized: shape=dict:ground_truth=list (new format) tenant_id={tenant_id}"
            )
            return result
        
        if isinstance(ground_truth, dict):
            expected = ground_truth.get("expected_assets")
            if isinstance(expected, list):
                result["raw_shape"] = "dict:ground_truth=dict:expected_assets=list"
                result["expected_assets"] = expected
                return result
            elif expected is None:
                result["raw_shape"] = "dict:ground_truth=dict:no_expected_assets"
                result["parse_error"] = "Farm ground_truth dict missing 'expected_assets'"
                logger.warning(
                    f"Farm ground truth shape drift: shape={result['raw_shape']} tenant_id={tenant_id} run_id={run_id}"
                )
                return result
            else:
                result["raw_shape"] = f"dict:ground_truth=dict:expected_assets={type(expected).__name__}"
                result["parse_error"] = f"expected_assets is not a list: {type(expected).__name__}"
                logger.warning(
                    f"Farm ground truth shape drift: shape={result['raw_shape']} tenant_id={tenant_id} run_id={run_id}"
                )
                return result
        
        result["raw_shape"] = f"dict:ground_truth={type(ground_truth).__name__}"
        result["parse_error"] = f"ground_truth has unexpected type: {type(ground_truth).__name__}"
        logger.warning(
            f"Farm ground truth shape drift: shape={result['raw_shape']} tenant_id={tenant_id} run_id={run_id}"
        )
        return result
        
    except Exception as e:
        result["raw_shape"] = "parse_exception"
        result["parse_error"] = f"Exception during parsing: {str(e)}"
        logger.error(
            f"Farm ground truth parse exception: error={str(e)} tenant_id={tenant_id} run_id={run_id}"
        )
        return result


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
