"""LLM client package for AOD fringe resolution"""

from .client import LLMClient, GeminiClient, OpenAIClient, get_llm_client
from .fringe_resolver import resolve_fringe, FringeResolution, FringeInput
from .fringe_integration import (
    apply_fringe_resolution,
    should_trigger_fringe,
    is_infra_tech_excluded,
    LLMExplainability,
)

__all__ = [
    "LLMClient",
    "GeminiClient", 
    "OpenAIClient",
    "get_llm_client",
    "resolve_fringe",
    "FringeResolution",
    "FringeInput",
    "apply_fringe_resolution",
    "should_trigger_fringe",
    "is_infra_tech_excluded",
    "LLMExplainability",
]
