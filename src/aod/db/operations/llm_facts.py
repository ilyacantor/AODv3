"""LLM facts operations for database."""

from datetime import datetime
from typing import Optional

import asyncpg


class LLMFactOperations:
    """Operations for LLM fact records."""

    def __init__(self, get_pool):
        self._get_pool = get_pool

    async def get_llm_fact(self, tenant_id: str, entity_key: str) -> Optional[dict]:
        """Get an LLM fact by tenant and entity key."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM llm_facts WHERE tenant_id = $1 AND entity_key = $2",
                tenant_id, entity_key
            )

        if not row:
            return None

        return {
            "fact_id": row["fact_id"],
            "tenant_id": row["tenant_id"],
            "entity_key": row["entity_key"],
            "asset_type": row["asset_type"],
            "entity_role": row["entity_role"],
            "canonical_vendor": row["canonical_vendor"],
            "canonical_product": row["canonical_product"],
            "cmdb_ci_id": row["cmdb_ci_id"],
            "idp_object_id": row["idp_object_id"],
            "confidence": row["confidence"],
            "reason": row["reason"],
            "llm_provider": row["llm_provider"],
            "llm_model_id": row["llm_model_id"],
            "created_at": row["created_at"]
        }

    async def upsert_llm_fact(
        self,
        fact_id: str,
        tenant_id: str,
        entity_key: str,
        asset_type: Optional[str],
        entity_role: Optional[str],
        canonical_vendor: Optional[str],
        canonical_product: Optional[str],
        cmdb_ci_id: Optional[str],
        idp_object_id: Optional[str],
        confidence: float,
        reason: str,
        llm_provider: str,
        llm_model_id: str,
        created_at: datetime
    ) -> None:
        """Insert or update an LLM fact."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_facts (
                    fact_id, tenant_id, entity_key, asset_type, entity_role,
                    canonical_vendor, canonical_product, cmdb_ci_id, idp_object_id,
                    confidence, reason, llm_provider, llm_model_id, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (tenant_id, entity_key)
                DO UPDATE SET
                    asset_type = EXCLUDED.asset_type,
                    entity_role = EXCLUDED.entity_role,
                    canonical_vendor = EXCLUDED.canonical_vendor,
                    canonical_product = EXCLUDED.canonical_product,
                    cmdb_ci_id = EXCLUDED.cmdb_ci_id,
                    idp_object_id = EXCLUDED.idp_object_id,
                    confidence = EXCLUDED.confidence,
                    reason = EXCLUDED.reason,
                    llm_provider = EXCLUDED.llm_provider,
                    llm_model_id = EXCLUDED.llm_model_id,
                    created_at = EXCLUDED.created_at
                """,
                fact_id, tenant_id, entity_key, asset_type, entity_role,
                canonical_vendor, canonical_product, cmdb_ci_id, idp_object_id,
                confidence, reason, llm_provider, llm_model_id, created_at.isoformat()
            )

    async def get_llm_facts_batch(self, tenant_id: str, entity_keys: list[str]) -> dict[str, dict]:
        """Get LLM facts for multiple entity keys in a batch."""
        if not entity_keys:
            return {}

        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM llm_facts WHERE tenant_id = $1 AND entity_key = ANY($2)",
                tenant_id, entity_keys
            )

        result = {}
        for row in rows:
            result[row["entity_key"]] = {
                "fact_id": row["fact_id"],
                "tenant_id": row["tenant_id"],
                "entity_key": row["entity_key"],
                "asset_type": row["asset_type"],
                "entity_role": row["entity_role"],
                "canonical_vendor": row["canonical_vendor"],
                "canonical_product": row["canonical_product"],
                "cmdb_ci_id": row["cmdb_ci_id"],
                "idp_object_id": row["idp_object_id"],
                "confidence": row["confidence"],
                "reason": row["reason"],
                "llm_provider": row["llm_provider"],
                "llm_model_id": row["llm_model_id"],
                "created_at": row["created_at"]
            }
        return result
