"""Fringe resolver - LLM-based fallback for Stage 4 correlation"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .client import LLMClient, GeminiClient, OpenAIClient, LLMResponse

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.80

FRINGE_SCHEMA = {
    "type": "object",
    "required": ["asset_type", "entity_role", "confidence", "reason"],
    "properties": {
        "asset_type": {
            "type": "string",
            "enum": ["SAAS_APP", "INFRA_TECH", "UMBRELLA_WEB", "OSS_PROJECT", "UNKNOWN"]
        },
        "entity_role": {
            "type": "string",
            "enum": ["VENDOR", "PRODUCT", "BRAND", "UNKNOWN"]
        },
        "canonical_vendor": {"type": ["string", "null"]},
        "canonical_product": {"type": ["string", "null"]},
        "cmdb_ci_id": {"type": ["string", "null"]},
        "idp_object_id": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"}
    }
}


@dataclass
class FringeResolution:
    """Result from fringe resolution"""
    resolved: bool = False
    asset_type: Optional[str] = None
    entity_role: Optional[str] = None
    canonical_vendor: Optional[str] = None
    canonical_product: Optional[str] = None
    cmdb_ci_id: Optional[str] = None
    idp_object_id: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    llm_provider: str = ""
    llm_model_id: str = ""
    error: Optional[str] = None


@dataclass
class FringeInput:
    """Input data for fringe resolution"""
    entity_key: str
    domain: Optional[str] = None
    canonical_name: str = ""
    observed_names: list[str] = field(default_factory=list)
    vendor_hint: Optional[str] = None
    sources: set[str] = field(default_factory=set)
    recent_activity: bool = False
    cmdb_candidates: list[dict] = field(default_factory=list)
    idp_candidates: list[dict] = field(default_factory=list)


def build_fringe_prompt(fringe_input: FringeInput) -> str:
    """Build the prompt for fringe resolution"""
    prompt_parts = [
        "Analyze this enterprise IT entity and determine its classification.",
        "",
        f"Entity Key: {fringe_input.entity_key}",
        f"Domain: {fringe_input.domain or 'unknown'}",
        f"Canonical Name: {fringe_input.canonical_name}",
        f"Observed Names (top 5): {', '.join(fringe_input.observed_names[:5])}",
        f"Vendor Hint: {fringe_input.vendor_hint or 'none'}",
        f"Sources: {', '.join(fringe_input.sources) if fringe_input.sources else 'unknown'}",
        f"Recent Activity: {fringe_input.recent_activity}",
        "",
    ]
    
    if fringe_input.cmdb_candidates:
        prompt_parts.append("CMDB Candidates (top 10):")
        for ci in fringe_input.cmdb_candidates[:10]:
            prompt_parts.append(
                f"  - CI ID: {ci.get('ci_id')}, Name: {ci.get('name')}, "
                f"Type: {ci.get('ci_type')}, Lifecycle: {ci.get('lifecycle')}, "
                f"Vendor: {ci.get('vendor')}"
            )
        prompt_parts.append("")
    else:
        prompt_parts.append("CMDB Candidates: none")
        prompt_parts.append("")
    
    if fringe_input.idp_candidates:
        prompt_parts.append("IdP Candidates (top 10):")
        for idp in fringe_input.idp_candidates[:10]:
            prompt_parts.append(
                f"  - ID: {idp.get('id')}, Name: {idp.get('name')}, "
                f"Vendor: {idp.get('vendor')}, SSO: {idp.get('has_sso')}, "
                f"SCIM: {idp.get('has_scim')}"
            )
        prompt_parts.append("")
    else:
        prompt_parts.append("IdP Candidates: none")
        prompt_parts.append("")
    
    prompt_parts.extend([
        "Classification Guide:",
        "- SAAS_APP: Cloud-hosted software service (Slack, Salesforce, Zoom)",
        "- INFRA_TECH: Infrastructure technology (databases, caches, orchestration - Redis, PostgreSQL, Kubernetes)",
        "- UMBRELLA_WEB: Consumer web portal or content site",
        "- OSS_PROJECT: Open source project/library",
        "- UNKNOWN: Cannot determine with confidence",
        "",
        "If you can match this entity to a CMDB or IdP candidate, include the ci_id or object_id.",
        "Only include matches where you have high confidence (>= 0.80).",
        "Be conservative - when unsure, use UNKNOWN and lower confidence.",
    ])
    
    return "\n".join(prompt_parts)


async def resolve_fringe(
    fringe_input: FringeInput,
    gemini_client: Optional[GeminiClient] = None,
    openai_client: Optional[OpenAIClient] = None,
) -> FringeResolution:
    """
    Resolve fringe entity using LLM.
    
    Tries Gemini first, falls back to OpenAI on transient errors.
    Returns resolution only if confidence >= 0.80.
    """
    prompt = build_fringe_prompt(fringe_input)
    
    clients_to_try: list[LLMClient] = []
    if gemini_client:
        clients_to_try.append(gemini_client)
    if openai_client:
        clients_to_try.append(openai_client)
    
    if not clients_to_try:
        return FringeResolution(
            resolved=False,
            error="No LLM clients available",
            reason="LLM_NO_CLIENT"
        )
    
    last_error = None
    for client in clients_to_try:
        try:
            response = await client.generate_json(prompt, FRINGE_SCHEMA)
            
            if response.success and response.data:
                data = response.data
                confidence = float(data.get("confidence", 0))
                
                if confidence < CONFIDENCE_THRESHOLD:
                    return FringeResolution(
                        resolved=False,
                        asset_type=data.get("asset_type"),
                        confidence=confidence,
                        reason=f"LLM_INCONCLUSIVE: {data.get('reason', 'low confidence')}",
                        llm_provider=response.provider,
                        llm_model_id=response.model_id,
                    )
                
                return FringeResolution(
                    resolved=True,
                    asset_type=data.get("asset_type"),
                    entity_role=data.get("entity_role"),
                    canonical_vendor=data.get("canonical_vendor"),
                    canonical_product=data.get("canonical_product"),
                    cmdb_ci_id=data.get("cmdb_ci_id"),
                    idp_object_id=data.get("idp_object_id"),
                    confidence=confidence,
                    reason=data.get("reason", ""),
                    llm_provider=response.provider,
                    llm_model_id=response.model_id,
                )
            else:
                last_error = response.error
                logger.warning(f"LLM {client.provider} failed: {response.error}, trying fallback")
                continue
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"LLM {client.provider} exception: {e}, trying fallback")
            continue
    
    return FringeResolution(
        resolved=False,
        error=last_error,
        reason=f"LLM_ERROR: {last_error}"
    )
