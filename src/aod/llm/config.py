"""LLM configuration - dev/prod mode switch with runtime override"""

import os
from enum import Enum
from typing import Optional


class LLMMode(str, Enum):
    """LLM execution mode"""
    DEV = "dev"
    PROD = "prod"


_runtime_mode: Optional[LLMMode] = None


def get_llm_mode() -> LLMMode:
    """
    Get the current LLM execution mode.
    
    Priority:
    1. Runtime override (set via UI toggle)
    2. LLM_MODE environment variable
    3. Default to DEV
    
    Mode values:
    - "dev" or "development": No LLM calls, use cached facts only
    - "prod" or "production": Full LLM calls enabled
    """
    global _runtime_mode
    
    if _runtime_mode is not None:
        return _runtime_mode
    
    mode_str = os.environ.get("LLM_MODE", "dev").lower().strip()
    
    if mode_str in ("prod", "production"):
        return LLMMode.PROD
    
    return LLMMode.DEV


def set_llm_mode(mode: LLMMode) -> None:
    """Set the runtime LLM mode (overrides environment variable)"""
    global _runtime_mode
    _runtime_mode = mode


def clear_llm_mode_override() -> None:
    """Clear the runtime override, falling back to environment variable"""
    global _runtime_mode
    _runtime_mode = None


def is_llm_enabled() -> bool:
    """Check if LLM calls are enabled based on current mode"""
    return get_llm_mode() == LLMMode.PROD
