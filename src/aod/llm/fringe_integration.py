"""Fringe integration - connects LLM fringe resolver to correlation pipeline"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from .client import GeminiClient, OpenAIClient
from .config import is_llm_enabled, get_llm_mode, LLMMode
from .fringe_resolver import resolve_fringe, FringeResolution, FringeInput, CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class LLMExplainability:
    """LLM explainability fields for an entity"""
    llm_used: bool = False
    llm_confidence: float = 0.0
    llm_reason: str = ""
    llm_asset_type: Optional[str] = None
    llm_canonical_vendor: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model_id: Optional[str] = None
    cmdb_match_method: Optional[str] = None
    idp_match_method: Optional[str] = None
    exclusion_reason: Optional[str] = None
    fact_id: Optional[str] = None


def should_trigger_fringe(
    entity: Any,
    cmdb_matched: bool,
    idp_matched: bool,
    asset_type: Optional[str],
    vendor: Optional[str],
) -> tuple[bool, str]:
    """
    Determine if fringe resolution should be triggered for an entity.
    
    Trigger conditions:
    1. asset_type is missing/UNKNOWN after deterministic passes
    2. NO_CMDB AND NO_IDP AND entity is about to affect findings (shadow/governance gap)
    3. vendor is missing/ambiguous (vendor/product/brand confusion)
    
    Returns: (should_trigger, trigger_reason)
    """
    if asset_type is None or asset_type.upper() == "UNKNOWN":
        return True, "asset_type_unknown"
    
    if not cmdb_matched and not idp_matched:
        return True, "governance_gap"
    
    if vendor is None or vendor.strip() == "":
        return True, "vendor_missing"
    
    return False, ""


def build_fringe_input_from_entity(
    entity: Any,
    cmdb_candidates: list[dict],
    idp_candidates: list[dict],
) -> FringeInput:
    """Build FringeInput from a CandidateEntity"""
    observed_names = list(entity.observed_names) if hasattr(entity, 'observed_names') else []
    
    sources = set()
    if hasattr(entity, 'sources'):
        sources = entity.sources
    
    recent_activity = False
    if hasattr(entity, 'last_seen'):
        if entity.last_seen:
            days_since = (datetime.utcnow() - entity.last_seen).days
            recent_activity = days_since <= 90
    
    return FringeInput(
        entity_key=entity.entity_id,
        domain=entity.domain if hasattr(entity, 'domain') else None,
        canonical_name=entity.canonical_name if hasattr(entity, 'canonical_name') else "",
        observed_names=observed_names[:5],
        vendor_hint=entity.vendor if hasattr(entity, 'vendor') else None,
        sources=sources,
        recent_activity=recent_activity,
        cmdb_candidates=cmdb_candidates[:10],
        idp_candidates=idp_candidates[:10],
    )


async def apply_fringe_resolution(
    entity_key: str,
    tenant_id: str,
    correlation_result: Any,
    db: Any,
    cmdb_candidates: Optional[list[dict]] = None,
    idp_candidates: Optional[list[dict]] = None,
    enable_llm: Optional[bool] = None,
) -> tuple[Any, LLMExplainability]:
    """
    Apply fringe resolution to a correlation result.
    
    1. Check if fringe resolution is needed
    2. Check fact store for cached fact
    3. If no cached fact and LLM enabled (prod mode), call LLM
    4. Persist new fact
    5. Apply fact to correlation result
    
    LLM Mode (set via LLM_MODE env var):
    - "dev": No LLM calls, use cached facts only
    - "prod": Full LLM calls enabled
    
    Returns: (updated_correlation_result, explainability)
    """
    from ..pipeline.correlate_entities import MatchStatus, PlaneMatch
    
    explainability = LLMExplainability()
    
    llm_mode = get_llm_mode()
    llm_enabled = enable_llm if enable_llm is not None else is_llm_enabled()
    
    entity = correlation_result.entity
    cmdb_matched = correlation_result.cmdb.status == MatchStatus.MATCHED
    idp_matched = correlation_result.idp.status == MatchStatus.MATCHED
    
    asset_type = None
    if hasattr(entity, 'asset_type'):
        asset_type = entity.asset_type
    
    vendor = entity.vendor if hasattr(entity, 'vendor') else None
    
    should_trigger, trigger_reason = should_trigger_fringe(
        entity, cmdb_matched, idp_matched, asset_type, vendor
    )
    
    if not should_trigger:
        return correlation_result, explainability
    
    logger.debug(f"Fringe triggered for {entity_key}: {trigger_reason} (mode={llm_mode.value})")
    
    existing_fact = await db.get_llm_fact(tenant_id, entity_key)
    
    if existing_fact:
        logger.debug(f"Using cached LLM fact for {entity_key}")
        return _apply_fact_to_result(
            correlation_result, existing_fact, explainability, PlaneMatch, MatchStatus
        )
    
    if not llm_enabled:
        logger.debug(f"LLM disabled (mode={llm_mode.value}), skipping fringe resolution for {entity_key}")
        return correlation_result, explainability
    
    gemini_client = None
    openai_client = None
    
    if os.environ.get("GEMINI_API_KEY"):
        gemini_client = GeminiClient()
    if os.environ.get("OPENAI_API_KEY"):
        openai_client = OpenAIClient()
    
    if not gemini_client and not openai_client:
        logger.warning("No LLM clients available for fringe resolution")
        return correlation_result, explainability
    
    fringe_input = build_fringe_input_from_entity(
        entity,
        cmdb_candidates or [],
        idp_candidates or [],
    )
    
    try:
        resolution = await resolve_fringe(
            fringe_input,
            gemini_client=gemini_client,
            openai_client=openai_client,
        )
    except Exception as e:
        logger.error(f"Fringe resolution failed for {entity_key}: {e}")
        explainability.llm_used = True
        explainability.llm_reason = f"LLM_ERROR: {e}"
        return correlation_result, explainability
    
    explainability.llm_used = True
    explainability.llm_confidence = resolution.confidence
    explainability.llm_reason = resolution.reason
    explainability.llm_provider = resolution.llm_provider
    explainability.llm_model_id = resolution.llm_model_id
    
    if resolution.resolved:
        fact_id = f"llm-{uuid4().hex[:12]}"
        
        await db.upsert_llm_fact(
            fact_id=fact_id,
            tenant_id=tenant_id,
            entity_key=entity_key,
            asset_type=resolution.asset_type,
            entity_role=resolution.entity_role,
            canonical_vendor=resolution.canonical_vendor,
            canonical_product=resolution.canonical_product,
            cmdb_ci_id=resolution.cmdb_ci_id,
            idp_object_id=resolution.idp_object_id,
            confidence=resolution.confidence,
            reason=resolution.reason,
            llm_provider=resolution.llm_provider,
            llm_model_id=resolution.llm_model_id,
            created_at=datetime.utcnow(),
        )
        
        explainability.fact_id = fact_id
        explainability.llm_asset_type = resolution.asset_type
        explainability.llm_canonical_vendor = resolution.canonical_vendor
        
        fact_dict = {
            "fact_id": fact_id,
            "asset_type": resolution.asset_type,
            "cmdb_ci_id": resolution.cmdb_ci_id,
            "idp_object_id": resolution.idp_object_id,
            "canonical_vendor": resolution.canonical_vendor,
            "confidence": resolution.confidence,
        }
        
        return _apply_fact_to_result(
            correlation_result, fact_dict, explainability, PlaneMatch, MatchStatus
        )
    
    return correlation_result, explainability


def _apply_fact_to_result(
    correlation_result: Any,
    fact: dict,
    explainability: LLMExplainability,
    PlaneMatch: Any,
    MatchStatus: Any,
) -> tuple[Any, LLMExplainability]:
    """Apply LLM fact to correlation result"""
    
    explainability.llm_used = True
    explainability.llm_confidence = fact.get("confidence", 0.0)
    explainability.llm_asset_type = fact.get("asset_type")
    explainability.llm_canonical_vendor = fact.get("canonical_vendor")
    explainability.fact_id = fact.get("fact_id")
    
    if fact.get("cmdb_ci_id") and correlation_result.cmdb.status != MatchStatus.MATCHED:
        correlation_result.cmdb = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=[fact["cmdb_ci_id"]],
            match_method="llm_adjudicated",
            match_key=f"llm_fact:{fact.get('fact_id', 'unknown')}",
        )
        explainability.cmdb_match_method = "llm_adjudicated"
    
    if fact.get("idp_object_id") and correlation_result.idp.status != MatchStatus.MATCHED:
        correlation_result.idp = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=[fact["idp_object_id"]],
            match_method="llm_adjudicated",
            match_key=f"llm_fact:{fact.get('fact_id', 'unknown')}",
        )
        explainability.idp_match_method = "llm_adjudicated"
    
    asset_type = fact.get("asset_type")
    confidence = fact.get("confidence", 0.0)
    if asset_type == "INFRA_TECH" and confidence >= CONFIDENCE_THRESHOLD:
        explainability.exclusion_reason = "asset_type_infra_tech"
    
    return correlation_result, explainability


def is_infra_tech_excluded(explainability: LLMExplainability) -> bool:
    """Check if entity should be excluded from shadow/zombie due to INFRA_TECH classification"""
    return explainability.exclusion_reason == "asset_type_infra_tech"
