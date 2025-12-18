"""LLM client package for AOD fringe resolution"""

from .client import LLMClient, GeminiClient, OpenAIClient, get_llm_client
from .config import LLMMode, get_llm_mode, set_llm_mode, clear_llm_mode_override, is_llm_enabled
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
    "LLMMode",
    "get_llm_mode",
    "set_llm_mode",
    "clear_llm_mode_override",
    "is_llm_enabled",
    "resolve_fringe",
    "FringeResolution",
    "FringeInput",
    "apply_fringe_resolution",
    "should_trigger_fringe",
    "is_infra_tech_excluded",
    "LLMExplainability",
]
